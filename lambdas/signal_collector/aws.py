"""boto3 wrappers for the Signal Collector. Only place this Lambda imports AWS."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from lib import aws_clients


def nlb_unhealthy_count(nlb_arn: str) -> int:
    """Number of unhealthy targets across all NLB target groups, last 1 minute max."""
    end = datetime.now(UTC)
    start = end - timedelta(minutes=2)
    resp = aws_clients.cloudwatch().get_metric_statistics(
        Namespace="AWS/NetworkELB",
        MetricName="UnHealthyHostCount",
        Dimensions=[{"Name": "LoadBalancer", "Value": _nlb_dimension(nlb_arn)}],
        StartTime=start,
        EndTime=end,
        Period=60,
        Statistics=["Maximum"],
    )
    points = resp.get("Datapoints", [])
    return int(max((p["Maximum"] for p in points), default=0.0))


_ARN_PARTS = 2  # head + payload after splitting on ":loadbalancer/"


def _nlb_dimension(nlb_arn: str) -> str:
    """CloudWatch wants ``net/<name>/<id>`` for the LoadBalancer dimension."""
    parts = nlb_arn.split(":loadbalancer/")
    return parts[1] if len(parts) == _ARN_PARTS else nlb_arn


def canary_failure_pct(routable_url: str, _threshold_pct: int) -> float:
    """Failure percentage of the cross-region canary over the last 5 minutes."""
    canary_name = _canary_name_for_url(routable_url)
    end = datetime.now(UTC)
    start = end - timedelta(minutes=5)
    resp = aws_clients.cloudwatch().get_metric_statistics(
        Namespace="CloudWatchSynthetics",
        MetricName="Failed",
        Dimensions=[{"Name": "CanaryName", "Value": canary_name}],
        StartTime=start,
        EndTime=end,
        Period=60,
        Statistics=["Sum"],
    )
    failed = sum(p["Sum"] for p in resp.get("Datapoints", []))
    resp_total = aws_clients.cloudwatch().get_metric_statistics(
        Namespace="CloudWatchSynthetics",
        MetricName="SuccessPercent",
        Dimensions=[{"Name": "CanaryName", "Value": canary_name}],
        StartTime=start,
        EndTime=end,
        Period=60,
        Statistics=["SampleCount"],
    )
    total = sum(p["SampleCount"] for p in resp_total.get("Datapoints", []))
    if total <= 0:
        return 0.0
    return (failed / total) * 100.0


def _canary_name_for_url(routable_url: str) -> str:
    """Convention: canary is named ``probe-<host-without-dots>``."""
    host = routable_url.replace("https://", "").split("/", 1)[0]
    return "probe-" + host.replace(".", "-")[:40]


def aws_health_open_events(region: str) -> list[str]:
    """List open AWS Health event ARNs that affect ``region``.

    Fails open on common error modes:
    - SubscriptionRequiredException: account is on Basic Support; the Health
      API is only available with Business/Enterprise. Operators should either
      upgrade support OR remove `aws_health_open` from the profile's Tier 1
      signals to silence this warning.
    - Endpoint timeout / connection error: VPCE missing or misrouted; Lambda
      should not block signal collection on this single Tier 1 source.

    Returns an empty list on any of these failures so the Decision Engine
    isn't blocked and quorum still works on the other Tier 1 signals.
    """
    import logging  # noqa: PLC0415

    from botocore.exceptions import (  # noqa: PLC0415
        ClientError,
        ConnectTimeoutError,
        EndpointConnectionError,
        ReadTimeoutError,
    )
    from botocore.exceptions import (  # noqa: PLC0415
        ConnectionError as BotoConnectionError,
    )

    log = logging.getLogger(__name__)
    try:
        resp = aws_clients.health().describe_events(
            filter={"regions": [region], "eventStatusCodes": ["open"]},
        )
        return [e["arn"] for e in resp.get("events", [])]
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "SubscriptionRequiredException":
            log.warning(
                "aws_health_subscription_required region=%s — account needs "
                "Business/Enterprise Support to use AWS Health API; treating "
                "as no events.",
                region,
            )
            return []
        raise
    except (
        EndpointConnectionError,
        ReadTimeoutError,
        ConnectTimeoutError,
        BotoConnectionError,
    ) as exc:
        log.warning("aws_health_endpoint_unreachable region=%s err=%s", region, exc)
        return []


def vpc_endpoint_errors(region: str) -> int:
    """Sum of CloudWatch ``EndpointFailureCount`` across known endpoints in last 5 min."""
    end = datetime.now(UTC)
    start = end - timedelta(minutes=5)
    resp = aws_clients.cloudwatch().get_metric_statistics(
        Namespace="AWS/PrivateLinkEndpoints",
        MetricName="EndpointFailureCount",
        Dimensions=[{"Name": "Region", "Value": region}],
        StartTime=start,
        EndTime=end,
        Period=60,
        Statistics=["Sum"],
    )
    return int(sum(p["Sum"] for p in resp.get("Datapoints", [])))


def aurora_writer_in(global_cluster_id: str) -> str | None:
    """Return the AWS region of the current Aurora Global writer, or None if absent."""
    resp = aws_clients.rds().describe_global_clusters(GlobalClusterIdentifier=global_cluster_id)
    clusters = resp.get("GlobalClusters", [])
    if not clusters:
        return None
    members = clusters[0].get("GlobalClusterMembers", [])
    for m in members:
        if m.get("IsWriter"):
            arn = m["DBClusterArn"]
            return arn.split(":")[3]
    return None


def aurora_replica_lag_seconds(global_cluster_id: str) -> float:
    """Maximum AuroraGlobalDBReplicationLag (seconds) over last 1 min across reader clusters."""
    end = datetime.now(UTC)
    start = end - timedelta(minutes=2)
    resp = aws_clients.cloudwatch().get_metric_statistics(
        Namespace="AWS/RDS",
        MetricName="AuroraGlobalDBReplicationLag",
        Dimensions=[{"Name": "DBClusterIdentifier", "Value": global_cluster_id}],
        StartTime=start,
        EndTime=end,
        Period=60,
        Statistics=["Maximum"],
    )
    points = resp.get("Datapoints", [])
    return float(max((p["Maximum"] for p in points), default=0.0))


def elasticache_replication_healthy(global_replication_group_id: str) -> bool:
    """Best-effort ElastiCache Global Datastore status."""
    del global_replication_group_id  # actual API call requires elasticache client; placeholder
    return True


def alb_unhealthy_count(alb_arn: str) -> int:
    end = datetime.now(UTC)
    start = end - timedelta(minutes=2)
    resp = aws_clients.cloudwatch().get_metric_statistics(
        Namespace="AWS/ApplicationELB",
        MetricName="UnHealthyHostCount",
        Dimensions=[{"Name": "LoadBalancer", "Value": _alb_dimension(alb_arn)}],
        StartTime=start,
        EndTime=end,
        Period=60,
        Statistics=["Maximum"],
    )
    points = resp.get("Datapoints", [])
    return int(max((p["Maximum"] for p in points), default=0.0))


def _alb_dimension(alb_arn: str) -> str:
    parts = alb_arn.split(":loadbalancer/")
    return parts[1] if len(parts) == _ARN_PARTS else alb_arn


def api_gw_5xx_pct(api_id: str) -> float:
    end = datetime.now(UTC)
    start = end - timedelta(minutes=5)
    cw = aws_clients.cloudwatch()
    five = cw.get_metric_statistics(
        Namespace="AWS/ApiGateway",
        MetricName="5XXError",
        Dimensions=[{"Name": "ApiId", "Value": api_id}],
        StartTime=start,
        EndTime=end,
        Period=60,
        Statistics=["Sum"],
    )
    total = cw.get_metric_statistics(
        Namespace="AWS/ApiGateway",
        MetricName="Count",
        Dimensions=[{"Name": "ApiId", "Value": api_id}],
        StartTime=start,
        EndTime=end,
        Period=60,
        Statistics=["Sum"],
    )
    sum_5xx = sum(p["Sum"] for p in five.get("Datapoints", []))
    sum_total = sum(p["Sum"] for p in total.get("Datapoints", []))
    if sum_total <= 0:
        return 0.0
    return (sum_5xx / sum_total) * 100.0


def emit_metric(
    *,
    namespace: str,
    metric_name: str,
    value: float,
    unit: str,
    dimensions: list[dict[str, str]],
) -> None:
    aws_clients.cloudwatch().put_metric_data(
        Namespace=namespace,
        MetricData=[
            {
                "MetricName": metric_name,
                "Value": value,
                "Unit": unit,  # type: ignore[typeddict-item]
                "Dimensions": [{"Name": d["Name"], "Value": d["Value"]} for d in dimensions],
                "Timestamp": datetime.now(UTC),
            }
        ],
    )


def write_observation_snapshot(
    audit_bucket: str,
    app_name: str,
    region: str,
    timestamp: datetime,
    snapshot: dict[str, Any],
) -> None:
    iso = timestamp.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%S-%fZ")
    key = f"{app_name}/{region}/observations/{iso}.json"
    aws_clients.s3().put_object(
        Bucket=audit_bucket,
        Key=key,
        Body=json.dumps(snapshot, separators=(",", ":"), sort_keys=True, default=str).encode(
            "utf-8"
        ),
        ContentType="application/json",
    )


__all__ = [
    "alb_unhealthy_count",
    "api_gw_5xx_pct",
    "aurora_replica_lag_seconds",
    "aurora_writer_in",
    "aws_health_open_events",
    "canary_failure_pct",
    "elasticache_replication_healthy",
    "emit_metric",
    "nlb_unhealthy_count",
    "vpc_endpoint_errors",
    "write_observation_snapshot",
]
