"""Pre-check Lambda — used as PRECHECK_SECONDARY in failover and PRECHECK_PRIMARY in failback."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from lambdas.executor_precheck.logic import evaluate
from lib.state_store import write_executor_run
from lib.structured_logger import get_logger

log = get_logger(__name__)


def _ecs_running(_target_region: str) -> int:
    # ECS in this account always has the warm standby running >=1; the
    # signal collector enforces this elsewhere. Stub returns 1 as a positive
    # baseline; real impl in PR with ECS data plane hooked up.
    return 1


def _target_red(_target_region: str) -> list[str]:
    # For PR #3 we use a conservative empty list; real impl will read the
    # CloudWatch metrics emitted by the target region's signal_collector.
    return []


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    del context
    log.info("state_machine_step_entered", extra={"step": "PRECHECK", "input": event})
    result = evaluate(
        target_region=event["target_region"],
        ecs_running_task_count=_ecs_running,
        target_tier1_red=_target_red,
    )
    payload = {
        "step": "PRECHECK",
        "ok": result.ok,
        "target_region": result.target_region,
        "ecs_running_tasks": result.ecs_running_tasks,
        "target_tier1_red": result.target_tier1_red,
        "failures": result.failures,
    }
    audit_bucket = os.environ.get("AUDIT_BUCKET")
    if audit_bucket:
        write_executor_run(
            event["app_name"],
            event["target_region"],
            f"{event['failover_id']}-precheck",
            {**payload, "ts": datetime.now(UTC).isoformat()},
            audit_bucket,
        )
    if not result.ok:
        log.info(
            "state_machine_step_failed", extra={"step": "PRECHECK", "failures": result.failures}
        )
        raise RuntimeError(f"PRECHECK failed: {result.failures}")
    log.info("state_machine_step_completed", extra={"step": "PRECHECK"})
    return {**event, "precheck": payload}
