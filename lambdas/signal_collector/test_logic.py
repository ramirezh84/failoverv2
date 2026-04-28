from __future__ import annotations

from datetime import UTC, datetime

import pytest

from lambdas.signal_collector import logic
from lib.profile_loader import load_from_path

PROFILE = load_from_path("profiles/test-app.yaml")


def test_collect_tier1_marks_red_when_unhealthy() -> None:
    signals = logic.collect_tier1(
        PROFILE,
        "us-east-1",
        nlb_unhealthy_count=lambda _: 3,
        canary_failure_pct=lambda _u, _t: 90.0,
        aws_health_open_events=lambda _: ["arn:aws:health:event-1"],
        vpc_endpoint_errors=lambda _: 5,
    )
    for name in (
        "outer_nlb_unhealthy",
        "cross_region_canary_fail",
        "aws_health_open",
        "vpc_endpoint_errors",
    ):
        assert signals[name]["red"], f"{name} should be red"


def test_collect_tier1_green_under_threshold() -> None:
    signals = logic.collect_tier1(
        PROFILE,
        "us-east-1",
        nlb_unhealthy_count=lambda _: 0,
        canary_failure_pct=lambda _u, _t: 10.0,
        aws_health_open_events=lambda _: [],
        vpc_endpoint_errors=lambda _: 0,
    )
    for sig in signals.values():
        assert sig["red"] is False


def test_collect_tier2_includes_aurora_when_present() -> None:
    signals = logic.collect_tier2(
        PROFILE,
        "us-east-1",
        aurora_writer_in=lambda _: "us-east-1",
        aurora_replica_lag_seconds=lambda _: 0.5,
        elasticache_replication_healthy=lambda _: True,
    )
    assert "aurora_writer_location" in signals
    assert "aurora_replica_lag_high" in signals
    assert signals["aurora_replica_lag_high"]["red"] is False


def test_collect_tier2_high_lag_red() -> None:
    signals = logic.collect_tier2(
        PROFILE,
        "us-east-1",
        aurora_writer_in=lambda _: "us-east-1",
        aurora_replica_lag_seconds=lambda _: 200.0,
        elasticache_replication_healthy=lambda _: True,
    )
    assert signals["aurora_replica_lag_high"]["red"] is True


def test_collect_tier3_includes_alb_and_api_gw() -> None:
    signals = logic.collect_tier3(
        PROFILE,
        "us-east-1",
        alb_unhealthy_count=lambda _: 0,
        api_gw_5xx_pct=lambda _: 0.0,
    )
    assert "alb_unhealthy" in signals
    assert "api_gw_5xx" in signals


def test_collect_all_uses_secondary_region_arns() -> None:
    seen_nlbs: list[str] = []

    def fake_nlb(arn: str) -> int:
        seen_nlbs.append(arn)
        return 0

    logic.collect_tier1(
        PROFILE,
        "us-east-2",
        nlb_unhealthy_count=fake_nlb,
        canary_failure_pct=lambda _u, _t: 0.0,
        aws_health_open_events=lambda _: [],
        vpc_endpoint_errors=lambda _: 0,
    )
    assert "us-east-2" in seen_nlbs[0]


def test_collect_all_aggregates_red_lists(
    monkeypatch: pytest.MonkeyPatch,
    aws_credentials: None,
    vpc_endpoints: None,
) -> None:
    del aws_credentials, vpc_endpoints
    """``collect_all`` wires together the three tiers and returns the expected shape."""
    from lambdas.signal_collector import aws as collector_aws  # noqa: PLC0415 — local mock import

    monkeypatch.setattr(collector_aws, "nlb_unhealthy_count", lambda _: 0)
    monkeypatch.setattr(collector_aws, "canary_failure_pct", lambda _u, _t: 10.0)
    monkeypatch.setattr(collector_aws, "aws_health_open_events", lambda _: [])
    monkeypatch.setattr(collector_aws, "vpc_endpoint_errors", lambda _: 0)
    monkeypatch.setattr(collector_aws, "aurora_writer_in", lambda _: "us-east-1")
    monkeypatch.setattr(collector_aws, "aurora_replica_lag_seconds", lambda _: 0.5)
    monkeypatch.setattr(collector_aws, "elasticache_replication_healthy", lambda _: True)
    monkeypatch.setattr(collector_aws, "alb_unhealthy_count", lambda _: 0)
    monkeypatch.setattr(collector_aws, "api_gw_5xx_pct", lambda _: 0.0)

    snapshot = logic.collect_all(
        profile=PROFILE,
        region="us-east-1",
        now=datetime(2026, 4, 27, tzinfo=UTC),
        dry_run=True,
    )
    assert snapshot["tier1_red"] == []
    assert snapshot["tier2_red"] == []
    assert snapshot["tier3_red"] == []
    assert snapshot["dry_run"] is True
    assert snapshot["region"] == "us-east-1"
    assert "outer_nlb_unhealthy" in snapshot["signals"]


@pytest.mark.parametrize(
    ("fn", "args", "expected"),
    [
        (logic._nlb_target_health_red, (1,), True),
        (logic._nlb_target_health_red, (0,), False),
        (logic._canary_red, (90.0, 80), True),
        (logic._canary_red, (50.0, 80), False),
        (logic._aurora_replica_lag_red, (61.0,), True),
        (logic._aurora_replica_lag_red, (10.0,), False),
        (logic._vpc_endpoint_red, (1,), True),
        (logic._alb_unhealthy_red, (5,), True),
        (logic._api_gw_5xx_red, (10.0,), True),
        (logic._api_gw_5xx_red, (1.0,), False),
    ],
)
def test_threshold_helpers(fn: object, args: tuple[float, ...], expected: bool) -> None:
    assert fn(*args) is expected  # type: ignore[operator]
