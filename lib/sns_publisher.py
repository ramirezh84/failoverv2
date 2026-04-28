"""SNS publisher with the account-level topic + per-app message attribute.

SPEC §2 constraint #15: one SNS topic per AWS account. The orchestrator
publishes to the account-level topic with ``app_name`` as a message
attribute; subscribers filter accordingly.

Message format (humans + machines):
- **Subject:** `[<SEVERITY>] <human title>: <app> (<context>)` — short and
  immediately readable in email/SMS/Slack subject lines.
- **Body:** human-readable summary at the top (what + why + next steps),
  followed by `--- raw event payload ---` and the original JSON for
  programmatic consumers. Email/Slack subscribers see the human text first;
  Lambda/SQS subscribers can still json.loads the second block.
- **MessageAttributes:** unchanged — `app_name`, `event`, `severity`,
  `dry_run`. Programmatic filters (subscription policies, event router)
  use these.
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

# Body separator between the human-readable summary and the raw JSON payload.
_PAYLOAD_SEPARATOR: Final[str] = "\n\n--- raw event payload (JSON) ---\n"

# Human title per event — keeps SNS subjects readable. Falls back to the
# raw event name for any not listed.
_TITLES: Final[dict[str, str]] = {
    "failover_initiated": "Failover started",
    "failover_step_completed": "Failover step completed",
    "failover_completed": "Failover COMPLETED",
    "failover_failed": "Failover FAILED",
    "failback_initiated": "Failback started",
    "failback_completed": "Failback COMPLETED",
    "failback_failed": "Failback FAILED",
    "signal_red": "Signal degraded",
    "signal_recovered": "Signal recovered",
    "failover_authorized": "Failover authorized (decision engine)",
    "aurora_gate_paused": "OPERATOR ACTION REQUIRED: approve Aurora promotion",
}

# Per-event "next steps" block — actionable text shown to humans after the
# what/why summary. Keys not present here render no next-steps section.
_NEXT_STEPS: Final[dict[str, str]] = {
    "failover_initiated": (
        "1. Confirm the failover is intentional — if not, run "
        "`failoverctl abort --execution-id <id>` immediately.\n"
        "2. Stand by for the AURORA APPROVAL REQUIRED notification "
        "(if Aurora is in scope for this app)."
    ),
    "failover_completed": (
        "1. Verify traffic is healthy on the new region.\n"
        "2. Plan failback for when the original region is healed — "
        "see runbooks/RUNBOOK-failback.md."
    ),
    "failover_failed": (
        "1. Open runbooks/RUNBOOK-failover-failed.md.\n"
        "2. Inspect the failed step in the Step Functions console.\n"
        "3. Decide: retry, abort, or escalate."
    ),
    "aurora_gate_paused": (
        "1. Manually promote the Aurora secondary cluster to writer in the "
        "target region (RDS console → Failover Global Database).\n"
        "2. Run `failoverctl approve --execution-id <id>` to resume the "
        "state machine.\n"
        "3. To roll back instead, run `failoverctl abort --execution-id <id>`."
    ),
    "failback_initiated": (
        "1. Confirm failback is intentional — primary region must be "
        "healed before this is safe.\n"
        "2. Stand by for the AURORA APPROVAL REQUIRED notification."
    ),
    "failback_failed": (
        "1. Open runbooks/RUNBOOK-failback-failed.md.\n"
        "2. Verify which region currently holds the Aurora writer."
    ),
}


def _subject_context(detail: dict[str, Any]) -> str:
    """Short context phrase appended to the subject in parens."""
    src = detail.get("source_region")
    tgt = detail.get("target_region")
    if src and tgt:
        return f"{src} → {tgt}"
    if tgt:
        return f"target {tgt}"
    if "signal" in detail:
        return f"signal {detail['signal']}"
    return ""


def _detail_lines(detail: dict[str, Any]) -> list[str]:
    """Render the optional 'detail' fields that may appear in the body."""
    fields: list[tuple[str, str]] = [
        ("source_region", "Source"),
        ("target_region", "Target"),
        ("operator", "Operator"),
        ("failover_id", "Failover ID"),
        ("error", "Error"),
        ("signal", "Signal"),
        ("value", "Value"),
        ("threshold", "Threshold"),
    ]
    return [
        f"{label}:{' ' * (12 - len(label))}{detail[key]}" for key, label in fields if key in detail
    ]


def _render_human_summary(
    *,
    app_name: str,
    event: EventName,
    severity: str,
    dry_run: bool,
    detail: dict[str, Any],
) -> tuple[str, str]:
    """Return (subject, body_summary). The full SNS body is summary +
    separator + raw JSON; this helper produces the human half."""
    title = _TITLES.get(event, event.replace("_", " ").title())
    prefix = DRY_RUN_PREFIX if dry_run else ""

    context = _subject_context(detail)
    subject = f"[{severity}] {prefix}{title}: {app_name}"
    if context:
        subject = f"{subject} ({context})"
    subject = subject[:100]  # SNS cap

    lines: list[str] = [
        f"{prefix}{title.upper()}",
        "",
        f"App:        {app_name}",
        f"Severity:   {severity}",
    ]
    if dry_run:
        lines.append("Mode:       DRY-RUN (no real changes; this is a drill)")
    lines.append(f"Event:      {event}")
    lines.extend(_detail_lines(detail))

    next_steps = _NEXT_STEPS.get(event)
    if next_steps:
        lines.append("")
        lines.append("Next steps:")
        lines.extend(f"  {step}" for step in next_steps.split("\n"))

    return subject, "\n".join(lines)


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

    Body has two sections so the same SNS message serves humans and machines:
    a plain-prose summary first (what/why/next-steps), then the raw JSON
    payload after a `--- raw event payload ---` separator. MessageAttributes
    are unchanged for filter compatibility.
    """
    payload = {
        "app_name": app_name,
        "event": event,
        "severity": severity,
        "dry_run": dry_run,
        "detail": detail,
    }
    subject, summary = _render_human_summary(
        app_name=app_name, event=event, severity=severity, dry_run=dry_run, detail=detail
    )
    body = summary + _PAYLOAD_SEPARATOR + json.dumps(payload, indent=2, sort_keys=True, default=str)
    resp = sns().publish(
        TopicArn=topic_arn,
        Subject=subject,
        Message=body,
        MessageAttributes={
            "app_name": {"DataType": "String", "StringValue": app_name},
            "event": {"DataType": "String", "StringValue": event},
            "severity": {"DataType": "String", "StringValue": severity},
            "dry_run": {"DataType": "String", "StringValue": "true" if dry_run else "false"},
        },
    )
    return PublishResult(message_id=resp["MessageId"], topic_arn=topic_arn)


__all__ = ["DRY_RUN_PREFIX", "PublishResult", "publish_event"]
