"""boto3 wrappers for manual_trigger."""

from __future__ import annotations

import json

from lib import aws_clients


def start_failover_execution(
    state_machine_arn: str,
    execution_name: str,
    payload: dict[str, object],
) -> str:
    """Start a Step Functions Standard execution; return its ARN.

    Step Functions guarantees that two executions with the same name on the
    same state machine within 90 days are rejected (ExecutionAlreadyExists),
    which we use as the dedupe key per CLAUDE.md §11 #3.
    """
    resp = aws_clients.stepfunctions().start_execution(
        stateMachineArn=state_machine_arn,
        name=execution_name,
        input=json.dumps(payload, separators=(",", ":")),
    )
    return str(resp["executionArn"])


__all__ = ["start_failover_execution"]
