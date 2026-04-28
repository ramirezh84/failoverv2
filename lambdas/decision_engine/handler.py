"""Decision Engine Lambda — runs every minute via EventBridge.

SPEC §3.1: applies the rule in §4.2; writes ``decision_state`` to local SSM,
publishes events to local SNS, emits the failover-control metric that drives
the R53 health check.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from lambdas.decision_engine.aws import (
    emit_failover_control_metric,
    emit_quorum_red_metric,
    fetch_current_red_signals,
    fetch_signal_red_history,
    secondary_warm_standby_ready,
)
from lambdas.decision_engine.logic import evaluate
from lib.profile_loader import load_from_s3
from lib.sns_publisher import publish_event
from lib.state_store import DecisionRecord, read_latest_decision, write_decision
from lib.structured_logger import get_logger

log = get_logger(__name__)


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    del context
    app_name = os.environ["APP_NAME"]
    region = os.environ["AWS_REGION"]
    profile_bucket = os.environ["PROFILE_BUCKET"]
    profile_key = os.environ.get("PROFILE_KEY", f"{app_name}/profile.yaml")
    audit_bucket = os.environ["AUDIT_BUCKET"]
    sns_topic = os.environ["SNS_TOPIC_ARN"]
    profile_version = event.get("profile_version", "unknown")

    profile = load_from_s3(profile_bucket, profile_key)
    now = datetime.now(UTC)

    if region == profile.primary_region:
        red_signals = fetch_current_red_signals(app_name, region)
        emit_quorum_red_metric(app_name, region, len(red_signals))
        history = fetch_signal_red_history(
            app_name, region, minutes=profile.signals.dwell_minutes + 2
        )
        last = read_latest_decision(app_name, region)
        evaluation = evaluate(
            profile=profile,
            primary_red_signals=red_signals,
            primary_red_history=history,
            last_decision_at=last.timestamp if last else None,
            now=now,
            secondary_ready=lambda: secondary_warm_standby_ready(profile.secondary_region),
        )
    else:
        # Secondary's Decision Engine doesn't trigger failover; it simply
        # records GREEN state for symmetry/audit.
        evaluation = evaluate(
            profile=profile,
            primary_red_signals=[],
            primary_red_history=[],
            last_decision_at=None,
            now=now,
            secondary_ready=lambda: True,
        )

    log.info(
        "decision_evaluated",
        extra={
            "state": evaluation.state,
            "reason": evaluation.reason,
            "red_signals": list(evaluation.tier1_red_signals),
            "quorum_held": evaluation.quorum_held,
            "dwell_held": evaluation.dwell_held,
            "hysteresis_held": evaluation.hysteresis_held,
        },
    )

    record = DecisionRecord(
        state="FAILOVER_AUTHORIZED" if evaluation.failover_authorized else "GREEN",
        reason=evaluation.reason,
        timestamp=now,
        tier1_red_signals=evaluation.tier1_red_signals,
        quorum_held=evaluation.quorum_held,
        dwell_held=evaluation.dwell_held,
        hysteresis_held=evaluation.hysteresis_held,
        secondary_safe=evaluation.secondary_safe,
        profile_version=profile_version,
        extra={"engine_state": evaluation.state},
    )
    write_decision(app_name, region, record, audit_bucket)

    # Side effects driven by state
    last_state = (read_latest_decision(app_name, region) or record).state
    state_changed = (
        last is None or last.state != record.state
        if (last := read_latest_decision(app_name, region))
        else True
    )
    del last_state

    if evaluation.state == "FAILOVER_AUTHORIZED":
        emit_failover_control_metric(app_name, region, value=0.0)
        log.info("failover_authorized")
        publish_event(
            topic_arn=sns_topic,
            app_name=app_name,
            event="failover_authorized",
            detail={
                "reason": evaluation.reason,
                "red_signals": list(evaluation.tier1_red_signals),
            },
            severity="CRITICAL",
        )
    elif evaluation.state == "FAILOVER_AUTHORIZED_BUT_NOT_AUTO":
        log.info("failover_authorized")
        publish_event(
            topic_arn=sns_topic,
            app_name=app_name,
            event="failover_authorized",
            detail={
                "reason": "alert_only — auto_failover disabled in profile",
                "red_signals": list(evaluation.tier1_red_signals),
            },
            severity="HIGH",
        )
    elif evaluation.state == "FAILOVER_AUTHORIZED_BUT_UNSAFE":
        publish_event(
            topic_arn=sns_topic,
            app_name=app_name,
            event="failover_failed",
            detail={"reason": "secondary_not_ready", "evaluation": evaluation.reason},
            severity="CRITICAL",
        )
    elif state_changed and record.state == "GREEN" and evaluation.tier1_red_signals == ():
        emit_failover_control_metric(app_name, region, value=1.0)
        publish_event(
            topic_arn=sns_topic,
            app_name=app_name,
            event="signal_recovered",
            detail={"reason": evaluation.reason},
        )

    return {
        "ok": True,
        "state": evaluation.state,
        "failover_authorized": evaluation.failover_authorized,
        "red_signals": list(evaluation.tier1_red_signals),
    }
