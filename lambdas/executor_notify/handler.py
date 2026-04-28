"""Notify Lambda — single-purpose: publish one SNS event with the supplied
event name and detail. Used by NOTIFY_INITIATED, NOTIFY_STEP_COMPLETED,
NOTIFY_COMPLETED, NOTIFY_FAILED across both state machines."""

from __future__ import annotations

import os
from typing import Any, cast

from lib.profile_loader import EventName
from lib.sns_publisher import publish_event
from lib.structured_logger import get_logger

log = get_logger(__name__)

_VALID_EVENTS: set[str] = {
    "failover_initiated",
    "failover_step_completed",
    "failover_completed",
    "failover_failed",
    "failback_initiated",
    "failback_completed",
    "failback_failed",
    "signal_red",
    "signal_recovered",
    "failover_authorized",
}


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    del context
    event_name = str(event["event_name"])
    if event_name not in _VALID_EVENTS:
        raise ValueError(f"event_name not in vocabulary: {event_name}")
    severity = str(event.get("severity", "INFO"))
    detail = dict(event.get("detail", {}))
    detail.setdefault("failover_id", event.get("failover_id"))
    detail.setdefault("app_name", event.get("app_name"))
    detail.setdefault("step", event.get("step"))
    dry_run = bool(event.get("dry_run", False))
    topic_arn = event.get("topic_arn") or os.environ["SNS_TOPIC_ARN"]
    app_name = str(event["app_name"])

    if dry_run:
        log.info(
            "dry_run_action_skipped",
            extra={"action": "publish_event", "event_name": event_name},
        )
        return {"ok": True, "dry_run": True, "event_name": event_name}

    result = publish_event(
        topic_arn=topic_arn,
        app_name=app_name,
        event=cast(EventName, event_name),
        detail=detail,
        severity=severity,
        dry_run=False,
    )
    log.info("state_machine_step_completed", extra={"step": "NOTIFY", "event_name": event_name})
    return {"ok": True, "message_id": result.message_id, "event_name": event_name, **event}
