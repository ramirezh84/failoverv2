"""Approval-callback Lambda. Operators invoke directly to deliver
``SendTaskSuccess`` / ``SendTaskFailure`` to a paused Step Functions execution
after Aurora promotion (or to abort the workflow). SPEC §8.1.

Input shape:
    {
        "task_token": "<base64 token from the Aurora gate SNS message>",
        "decision": "approve" | "abort",
        "operator": "ramirezh84",
        "reason": "Aurora secondary promoted via console; writer confirmed."
    }
"""

from __future__ import annotations

import json
from typing import Any

from lib import aws_clients
from lib.structured_logger import get_logger

log = get_logger(__name__)


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    del context
    task_token = str(event["task_token"])
    decision = str(event["decision"]).lower()
    operator = str(event.get("operator", "anonymous"))
    reason = str(event.get("reason", ""))

    if decision not in {"approve", "abort"}:
        raise ValueError(f"decision must be approve|abort, got {decision!r}")

    sfn = aws_clients.stepfunctions()
    if decision == "approve":
        sfn.send_task_success(
            taskToken=task_token,
            output=json.dumps({"approved_by": operator, "reason": reason}, separators=(",", ":")),
        )
        log.info(
            "aurora_gate_approved",
            extra={"operator": operator, "reason_len": len(reason)},
        )
        return {"ok": True, "decision": "approve", "operator": operator}

    sfn.send_task_failure(
        taskToken=task_token,
        error="OperatorAbort",
        cause=json.dumps({"aborted_by": operator, "reason": reason}, separators=(",", ":")),
    )
    log.info("aurora_gate_aborted", extra={"operator": operator, "reason_len": len(reason)})
    return {"ok": True, "decision": "abort", "operator": operator}
