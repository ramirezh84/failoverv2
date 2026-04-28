"""boto3 wrappers for the Decision Engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lib import aws_clients


def fetch_signal_red_history(
    app_name: str,
    region: str,
    *,
    minutes: int,
) -> list[bool]:
    """Return the per-minute red/green history of the Tier 1 quorum metric.

    The Signal Collector emits one CW datapoint per signal per minute; we
    derive the boolean by querying the count of red signals via SUM stat.
    """
    end = datetime.now(UTC)
    start = end - timedelta(minutes=minutes + 1)
    cw = aws_clients.cloudwatch()
    resp = cw.get_metric_statistics(
        Namespace=f"Failover/{app_name}/Signals",
        MetricName="tier1_quorum_red",
        Dimensions=[{"Name": "Region", "Value": region}],
        StartTime=start,
        EndTime=end,
        Period=60,
        Statistics=["Sum"],
    )
    points = sorted(resp.get("Datapoints", []), key=lambda p: p["Timestamp"])
    return [p["Sum"] >= 1 for p in points]


def fetch_current_red_signals(app_name: str, region: str) -> list[str]:
    """Return the names of Tier 1 signals currently red."""
    end = datetime.now(UTC)
    start = end - timedelta(minutes=2)
    namespace = f"Failover/{app_name}/Signals"
    cw = aws_clients.cloudwatch()
    resp = cw.list_metrics(
        Namespace=namespace,
        Dimensions=[
            {"Name": "Region", "Value": region},
            {"Name": "Tier", "Value": "1"},
        ],
    )
    red: list[str] = []
    for m in resp.get("Metrics", []):
        name = m["MetricName"]
        latest = cw.get_metric_statistics(
            Namespace=namespace,
            MetricName=name,
            Dimensions=m["Dimensions"],
            StartTime=start,
            EndTime=end,
            Period=60,
            Statistics=["Maximum"],
        )
        points = latest.get("Datapoints", [])
        if points and max(p["Maximum"] for p in points) > 0:
            red.append(name)
    return red


def emit_quorum_red_metric(app_name: str, region: str, red_count: int) -> None:
    """Emit a single derived metric the dwell window can read in one query."""
    aws_clients.cloudwatch().put_metric_data(
        Namespace=f"Failover/{app_name}/Signals",
        MetricData=[
            {
                "MetricName": "tier1_quorum_red",
                "Value": float(red_count),
                "Unit": "Count",
                "Dimensions": [{"Name": "Region", "Value": region}],
                "Timestamp": datetime.now(UTC),
            }
        ],
    )


def emit_failover_control_metric(app_name: str, region: str, value: float) -> None:
    """Emit the metric Route 53 health-check alarm watches.

    SPEC §3.2: Lambda emits a CloudWatch metric; an alarm watches the
    metric; an R53 health check is bound to the alarm. value=0.0 => trip
    the primary's health check (route to secondary). value=1.0 => clear.
    """
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


def secondary_warm_standby_ready(_secondary_region: str) -> bool:
    """Best-effort secondary readiness check.

    Production check: secondary ECS service has running task count >= 1
    AND target health > 0 on secondary ALB AND VPC endpoints reachable.
    For the POC we surface a single boolean; tests can stub it.
    """
    return True


__all__ = [
    "emit_failover_control_metric",
    "emit_quorum_red_metric",
    "fetch_current_red_signals",
    "fetch_signal_red_history",
    "secondary_warm_standby_ready",
]
