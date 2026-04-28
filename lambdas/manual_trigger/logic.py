"""Pure logic for manual_trigger: validate input, build state-machine input."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from lib.identifiers import make_failover_id
from lib.profile_loader import Profile

Direction = Literal["failover", "failback", "dryrun"]


def build_execution_input(
    *,
    profile: Profile,
    direction: Direction,
    requested_target_region: str | None,
    operator: str,
    now: datetime,
    dry_run: bool,
) -> dict[str, Any]:
    """Validate and assemble the Step Functions execution input."""
    if direction == "failover":
        target = profile.secondary_region
        if requested_target_region and requested_target_region != target:
            raise ValueError(f"Failover target must be {target}, got {requested_target_region!r}")
        source = profile.primary_region
    elif direction == "failback":
        target = profile.primary_region
        if requested_target_region and requested_target_region != target:
            raise ValueError(f"Failback target must be {target}, got {requested_target_region!r}")
        source = profile.secondary_region
    else:  # dryrun
        target = profile.secondary_region
        source = profile.primary_region

    failover_id = make_failover_id(app=profile.app_name, direction=direction, timestamp=now)
    return {
        "execution_name": failover_id,
        "input": {
            "failover_id": failover_id,
            "app_name": profile.app_name,
            "direction": direction,
            "source_region": source,
            "target_region": target,
            "operator": operator,
            "requested_at": now.isoformat(),
            "dry_run": dry_run or direction == "dryrun",
            "profile_snapshot": {
                "components": profile.components.model_dump(),
                "aurora_manual_approval_required": (
                    profile.aurora.manual_approval_required if profile.aurora else False
                ),
                "dns_first_failover": (
                    profile.aurora.dns_first_failover if profile.aurora else True
                ),
                "drain_seconds": profile.failover.drain_seconds,
                "quiesce_seconds": profile.failover.quiesce_seconds,
                "r53_propagation_seconds": profile.failover.r53_propagation_seconds,
                "aurora_confirm_timeout_minutes": (
                    profile.aurora.aurora_confirm_timeout_minutes if profile.aurora else 30
                ),
            },
        },
    }


__all__ = ["Direction", "build_execution_input"]
