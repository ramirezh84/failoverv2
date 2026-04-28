"""Emit the CloudWatch metric value that flips (or restores) the primary
region's failover-control alarm.

SPEC §3.2 / §5.1 step 5: Lambda emits CW metric → alarm → Route 53 health
check. This Lambda owns the single emit; nothing else writes the
``Failover/<app>/PrimaryHealthControl`` metric.

Input shape:
    {
        "app_name": "test-app",
        "primary_region": "us-east-1",     # which region's alarm to flip
        "value": 0.0 | 1.0,                # 0 = trip, 1 = clear
        "dry_run": false
    }
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from lib import aws_clients
from lib.structured_logger import get_logger

log = get_logger(__name__)


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    del context
    app_name = str(event["app_name"])
    region = str(event["primary_region"])
    value = float(event["value"])
    dry_run = bool(event.get("dry_run", False))

    if value not in {0.0, 1.0}:
        raise ValueError(f"value must be 0.0 or 1.0, got {value!r}")

    if dry_run:
        log.info(
            "dry_run_action_skipped",
            extra={"action": "emit_failover_control", "value": value, "region": region},
        )
        return {"ok": True, "dry_run": True, "value": value}

    aws_clients.cloudwatch().put_metric_data(
        Namespace=f"Failover/{app_name}",
        MetricData=[
            {
                "MetricName": "PrimaryHealthControl",
                "Value": value,
                "Unit": "None",
                "Dimensions": [{"Name": "Region", "Value": region}],
                "Timestamp": datetime.now(UTC),
            }
        ],
    )
    log.info(
        "r53_control_metric_emitted",
        extra={"value": value, "region": region, "namespace": f"Failover/{app_name}"},
    )
    return {"ok": True, "value": value, **event}
