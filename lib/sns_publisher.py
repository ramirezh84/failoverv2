"""SNS publisher with the account-level topic + per-app message attribute.

SPEC §2 constraint #15: one SNS topic per AWS account. The orchestrator
publishes to the account-level topic with ``app_name`` as a message
attribute; subscribers filter accordingly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final

from lib.aws_clients import sns
from lib.profile_loader import EventName

# Subject prefixes mark dry-run events so subscribers never confuse them with
# real ones. SPEC §10 scenario 7.
DRY_RUN_PREFIX: Final[str] = "[DRY-RUN] "


@dataclass(frozen=True)
class PublishResult:
    message_id: str
    topic_arn: str


def publish_event(
    *,
    topic_arn: str,
    app_name: str,
    event: EventName,
    detail: dict[str, Any],
    severity: str = "INFO",
    dry_run: bool = False,
) -> PublishResult:
    """Publish a single orchestrator event to ``topic_arn``.

    Message attributes always include ``app_name``, ``event``, ``severity``,
    and ``dry_run``. The body is a JSON-encoded ``detail`` plus the same
    metadata, so subscribers that don't filter by attribute can still
    discriminate.
    """
    body = {
        "app_name": app_name,
        "event": event,
        "severity": severity,
        "dry_run": dry_run,
        "detail": detail,
    }
    subject = f"{DRY_RUN_PREFIX if dry_run else ''}failover/{app_name}/{event}"
    # SNS Subject is capped at 100 chars; the body always carries the full event.
    subject = subject[:100]
    resp = sns().publish(
        TopicArn=topic_arn,
        Subject=subject,
        Message=json.dumps(body, separators=(",", ":"), sort_keys=True, default=str),
        MessageAttributes={
            "app_name": {"DataType": "String", "StringValue": app_name},
            "event": {"DataType": "String", "StringValue": event},
            "severity": {"DataType": "String", "StringValue": severity},
            "dry_run": {"DataType": "String", "StringValue": "true" if dry_run else "false"},
        },
    )
    return PublishResult(message_id=resp["MessageId"], topic_arn=topic_arn)


__all__ = ["DRY_RUN_PREFIX", "PublishResult", "publish_event"]
