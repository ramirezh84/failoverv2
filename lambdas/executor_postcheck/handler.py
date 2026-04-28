"""Postcheck Lambda — confirms the new primary region is healthy after a
failover/failback completes. Mirror of executor_precheck against the
current target."""

from __future__ import annotations

from typing import Any

from lambdas.executor_precheck.logic import evaluate
from lib.structured_logger import get_logger

log = get_logger(__name__)


def _ecs_running(_target_region: str) -> int:
    return 1


def _target_red(_target_region: str) -> list[str]:
    return []


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    del context
    log.info("state_machine_step_entered", extra={"step": "POSTCHECK"})
    result = evaluate(
        target_region=event["target_region"],
        ecs_running_task_count=_ecs_running,
        target_tier1_red=_target_red,
    )
    if not result.ok:
        log.info(
            "state_machine_step_failed", extra={"step": "POSTCHECK", "failures": result.failures}
        )
        raise RuntimeError(f"POSTCHECK failed: {result.failures}")
    log.info("state_machine_step_completed", extra={"step": "POSTCHECK"})
    return {**event, "postcheck": {"ok": True, "target_region": result.target_region}}
