"""Signal collection — pure logic; no boto3 imports here per CLAUDE.md §3.2.

The collectors below take an injected ``aws`` callable for each AWS read so
unit tests can substitute fakes without mocking boto3.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal, TypedDict

from lib.profile_loader import Profile

Tier = Literal["1", "2", "3"]


class Signal(TypedDict):
    tier: Tier
    red: bool
    detail: dict[str, Any]


def _nlb_target_health_red(unhealthy_count: int) -> bool:
    return unhealthy_count > 0  # all targets unhealthy is red; >0 is conservative


def _canary_red(failure_pct: float, threshold_pct: int) -> bool:
    return failure_pct >= threshold_pct


def _aurora_replica_lag_red(lag_seconds: float, max_seconds: float = 60.0) -> bool:
    return lag_seconds > max_seconds


def _vpc_endpoint_red(error_count: int) -> bool:
    return error_count > 0


def _alb_unhealthy_red(unhealthy_count: int) -> bool:
    return unhealthy_count > 0


def _api_gw_5xx_red(rate_pct: float, threshold_pct: float = 5.0) -> bool:
    return rate_pct >= threshold_pct


# ---------------------------------------------------------------------------
# Collector functions take a single injectable reader callable and a profile.
# ---------------------------------------------------------------------------


def collect_tier1(
    profile: Profile,
    region: str,
    *,
    nlb_unhealthy_count: Callable[[str], int],
    canary_failure_pct: Callable[[str, int], float],
    aws_health_open_events: Callable[[str], list[str]],
    vpc_endpoint_errors: Callable[[str], int],
) -> dict[str, Signal]:
    """Collect Tier 1 (infrastructure) signals."""
    signals: dict[str, Signal] = {}
    nlb_arn = (
        profile.network.outer_nlb_arn_primary
        if region == profile.primary_region
        else profile.network.outer_nlb_arn_secondary
    )
    nlb_unhealthy = nlb_unhealthy_count(nlb_arn)
    signals["outer_nlb_unhealthy"] = {
        "tier": "1",
        "red": _nlb_target_health_red(nlb_unhealthy),
        "detail": {"unhealthy_count": nlb_unhealthy, "nlb_arn": nlb_arn},
    }

    # Canary in opposite region probes this region.
    routable_url = (
        profile.network.routable_url_primary
        if region == profile.primary_region
        else profile.network.routable_url_secondary
    )
    canary_pct = canary_failure_pct(routable_url, profile.signals.canary_failure_rate_pct)
    signals["cross_region_canary_fail"] = {
        "tier": "1",
        "red": _canary_red(canary_pct, profile.signals.canary_failure_rate_pct),
        "detail": {"failure_pct": canary_pct, "url": routable_url},
    }

    health_events = aws_health_open_events(region)
    signals["aws_health_open"] = {
        "tier": "1",
        "red": bool(health_events),
        "detail": {"events": health_events},
    }

    endpoint_errors = vpc_endpoint_errors(region)
    signals["vpc_endpoint_errors"] = {
        "tier": "1",
        "red": _vpc_endpoint_red(endpoint_errors),
        "detail": {"error_count": endpoint_errors},
    }
    return signals


def collect_tier2(
    profile: Profile,
    region: str,
    *,
    aurora_writer_in: Callable[[str], str | None],
    aurora_replica_lag_seconds: Callable[[str], float],
    elasticache_replication_healthy: Callable[[str], bool],
) -> dict[str, Signal]:
    """Collect Tier 2 (data tier) signals."""
    signals: dict[str, Signal] = {}
    if profile.aurora is not None:
        writer = aurora_writer_in(profile.aurora.global_cluster_id)
        lag = aurora_replica_lag_seconds(profile.aurora.global_cluster_id)
        signals["aurora_writer_location"] = {
            "tier": "2",
            "red": False,
            "detail": {"writer_region": writer},
        }
        signals["aurora_replica_lag_high"] = {
            "tier": "2",
            "red": _aurora_replica_lag_red(lag),
            "detail": {"lag_seconds": lag},
        }
    if profile.elasticache is not None:
        healthy = elasticache_replication_healthy(profile.elasticache.global_replication_group_id)
        signals["elasticache_replication"] = {
            "tier": "2",
            "red": not healthy,
            "detail": {"healthy": healthy},
        }
    del region
    return signals


def collect_tier3(
    profile: Profile,
    region: str,
    *,
    alb_unhealthy_count: Callable[[str], int],
    api_gw_5xx_pct: Callable[[str], float],
) -> dict[str, Signal]:
    """Collect Tier 3 (application) signals — informational only."""
    signals: dict[str, Signal] = {}
    alb_arn = (
        profile.network.alb_arn_primary
        if region == profile.primary_region
        else profile.network.alb_arn_secondary
    )
    alb_unhealthy = alb_unhealthy_count(alb_arn)
    signals["alb_unhealthy"] = {
        "tier": "3",
        "red": _alb_unhealthy_red(alb_unhealthy),
        "detail": {"unhealthy_count": alb_unhealthy, "alb_arn": alb_arn},
    }
    if profile.components.api_gateway:
        api_id = (
            profile.network.api_gw_id_primary
            if region == profile.primary_region
            else profile.network.api_gw_id_secondary
        )
        if api_id:
            pct = api_gw_5xx_pct(api_id)
            signals["api_gw_5xx"] = {
                "tier": "3",
                "red": _api_gw_5xx_red(pct),
                "detail": {"rate_pct": pct, "api_id": api_id},
            }
    return signals


def collect_all(
    *,
    profile: Profile,
    region: str,
    now: datetime,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Collect all tiers using the production AWS readers.

    The boto3-backed readers are imported lazily so unit tests can replace
    ``collect_tier1/2/3`` directly without instantiating clients.
    """
    from lambdas.signal_collector.aws import (  # noqa: PLC0415 — keep boto3 out of pure logic
        alb_unhealthy_count,
        api_gw_5xx_pct,
        aurora_replica_lag_seconds,
        aurora_writer_in,
        aws_health_open_events,
        canary_failure_pct,
        elasticache_replication_healthy,
        nlb_unhealthy_count,
        vpc_endpoint_errors,
    )

    tier1 = collect_tier1(
        profile,
        region,
        nlb_unhealthy_count=nlb_unhealthy_count,
        canary_failure_pct=canary_failure_pct,
        aws_health_open_events=aws_health_open_events,
        vpc_endpoint_errors=vpc_endpoint_errors,
    )
    tier2 = collect_tier2(
        profile,
        region,
        aurora_writer_in=aurora_writer_in,
        aurora_replica_lag_seconds=aurora_replica_lag_seconds,
        elasticache_replication_healthy=elasticache_replication_healthy,
    )
    tier3 = collect_tier3(
        profile,
        region,
        alb_unhealthy_count=alb_unhealthy_count,
        api_gw_5xx_pct=api_gw_5xx_pct,
    )
    signals: dict[str, Signal] = {**tier1, **tier2, **tier3}
    return {
        "timestamp": now.isoformat(),
        "region": region,
        "tier1_red": [n for n, s in tier1.items() if s["red"]],
        "tier2_red": [n for n, s in tier2.items() if s["red"]],
        "tier3_red": [n for n, s in tier3.items() if s["red"]],
        "signals": signals,
        "dry_run": dry_run,
    }


__all__ = ["collect_all", "collect_tier1", "collect_tier2", "collect_tier3"]
