"""Manual-trigger Lambda. Operators invoke directly via ``aws lambda invoke``
(or ``failoverctl``) to start a failover/failback Step Functions execution.

Input shape:
    {
        "direction": "failover" | "failback" | "dryrun",
        "operator": "ramirezh84",
        "target_region": "us-east-2",     # optional; sanity-checked
        "dry_run": false                   # ignored for "dryrun"
    }
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError

from lambdas.manual_trigger.aws import start_failover_execution
from lambdas.manual_trigger.logic import build_execution_input
from lib.profile_loader import load_profile
from lib.structured_logger import get_logger

log = get_logger(__name__)


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    del context
    failover_arn = os.environ["FAILOVER_STATE_MACHINE_ARN"]
    failback_arn = os.environ["FAILBACK_STATE_MACHINE_ARN"]

    direction = str(event.get("direction", "")).lower()
    operator = str(event.get("operator", "anonymous"))
    target = event.get("target_region")
    dry_run = bool(event.get("dry_run", False))

    if direction not in {"failover", "failback", "dryrun"}:
        raise ValueError(f"direction must be failover|failback|dryrun, got {direction!r}")

    profile = load_profile()
    payload = build_execution_input(
        profile=profile,
        direction=direction,  # type: ignore[arg-type]
        requested_target_region=target,
        operator=operator,
        now=datetime.now(UTC),
        dry_run=dry_run,
    )
    state_machine_arn = failback_arn if direction == "failback" else failover_arn

    try:
        execution_arn = start_failover_execution(
            state_machine_arn=state_machine_arn,
            execution_name=payload["execution_name"],
            payload=payload["input"],
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ExecutionAlreadyExists":
            log.info(
                "state_machine_started",
                extra={
                    "execution_name": payload["execution_name"],
                    "result": "already_exists",
                },
            )
            return {
                "ok": True,
                "duplicate": True,
                "execution_name": payload["execution_name"],
                "message": "An execution with this name already exists; returning idempotently.",
            }
        raise
    log.info(
        "state_machine_started",
        extra={
            "execution_arn": execution_arn,
            "direction": direction,
            "operator": operator,
            "dry_run": payload["input"]["dry_run"],
        },
    )
    return {
        "ok": True,
        "execution_arn": execution_arn,
        "execution_name": payload["execution_name"],
        "input": payload["input"],
    }
