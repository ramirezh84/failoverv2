"""Indicator Updater Lambda — invoked only by the failover/failback state
machine to write ``/failover/<app>/<region>/role`` (SPEC §3.3).

Input shape (from Step Functions):
    {
        "app_name": "test-app",
        "region": "us-east-1",
        "role": "DRAINING" | "ACTIVE" | "PASSIVE",
        "executor_run_id": "failover-...-...",
        "sequence": 4,
        "dry_run": false
    }

Returns the indicator-write audit record.
"""

from __future__ import annotations

from typing import Any

from lib.indicator_writer import Role, write_role
from lib.structured_logger import get_logger

log = get_logger(__name__)


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    del context
    app_name = str(event["app_name"])
    region = str(event["region"])
    role: Role = event["role"]
    executor_run_id = str(event["executor_run_id"])
    sequence = int(event["sequence"])
    dry_run = bool(event.get("dry_run", False))

    if dry_run:
        log.info(
            "dry_run_action_skipped",
            extra={"action": "write_role", "role": role, "region": region},
        )
        return {"ok": True, "dry_run": True, "role": role, "region": region}

    write = write_role(app_name, region, role, executor_run_id=executor_run_id, sequence=sequence)
    log.info(
        "indicator_updated",
        extra={
            "role": write.role,
            "region": write.region,
            "executor_run_id": write.executor_run_id,
            "sequence": write.sequence,
        },
    )
    return {
        "ok": True,
        "role": write.role,
        "region": write.region,
        "executor_run_id": write.executor_run_id,
        "sequence": write.sequence,
    }
