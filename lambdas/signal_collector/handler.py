"""Signal Collector Lambda — runs every minute via EventBridge.

SPEC §3.1: polls Tier 1, 2, 3 signals for the region; writes raw observations
to CloudWatch custom metrics namespace ``Failover/{app}/Signals``; appends a
structured snapshot to S3 (audit) per CLAUDE.md §3.2.

Handler is a thin entrypoint: parse event → call logic.run → return.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from lambdas.signal_collector.aws import emit_metric, write_observation_snapshot
from lambdas.signal_collector.logic import collect_all
from lib.profile_loader import load_profile
from lib.structured_logger import get_logger

log = get_logger(__name__)


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    del context  # unused; entrypoint signature contract
    app_name = os.environ["APP_NAME"]
    region = os.environ["AWS_REGION"]
    audit_bucket = os.environ["AUDIT_BUCKET"]

    profile = load_profile()
    now = datetime.now(UTC)

    snapshot = collect_all(
        profile=profile, region=region, now=now, dry_run=event.get("dry_run", False)
    )
    log.info(
        "signal_collected",
        extra={
            "tier1_red": snapshot["tier1_red"],
            "tier2_red": snapshot["tier2_red"],
            "tier3_red": snapshot["tier3_red"],
            "snapshot_keys": list(snapshot["signals"].keys()),
        },
    )

    # Emit one CW metric per signal so the Decision Engine can read via
    # GetMetricData with proper aggregation/dwell windows.
    for signal_name, signal in snapshot["signals"].items():
        emit_metric(
            namespace=f"Failover/{app_name}/Signals",
            metric_name=signal_name,
            value=1.0 if signal["red"] else 0.0,
            unit="Count",
            dimensions=[
                {"Name": "Region", "Value": region},
                {"Name": "Tier", "Value": signal["tier"]},
            ],
        )
    write_observation_snapshot(audit_bucket, app_name, region, now, snapshot)
    return {"ok": True, **{k: v for k, v in snapshot.items() if k != "signals"}}
