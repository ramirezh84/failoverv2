from __future__ import annotations

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

from lambdas.signal_collector import aws as collector_aws
from lambdas.signal_collector.handler import lambda_handler


@pytest.fixture
def harness(
    aws_credentials: None,
    vpc_endpoints: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
) -> Iterator[None]:
    del aws_credentials, vpc_endpoints
    monkeypatch.setenv("APP_NAME", "test-app")
    monkeypatch.setenv("PROFILE_BUCKET", "profile-bucket")
    monkeypatch.setenv("PROFILE_KEY", "test-app/profile.yaml")
    monkeypatch.setenv("AUDIT_BUCKET", "audit-bucket")
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="profile-bucket")
        s3.create_bucket(Bucket="audit-bucket")
        with open("profiles/test-app.yaml", "rb") as f:
            s3.put_object(Bucket="profile-bucket", Key="test-app/profile.yaml", Body=f.read())
        # Stub out the AWS readers; we only want to exercise the wiring.
        for name in (
            "nlb_unhealthy_count",
            "vpc_endpoint_errors",
            "alb_unhealthy_count",
        ):
            monkeypatch.setattr(collector_aws, name, lambda _: 0)
        monkeypatch.setattr(collector_aws, "canary_failure_pct", lambda _u, _t: 0.0)
        monkeypatch.setattr(collector_aws, "aws_health_open_events", lambda _: [])
        monkeypatch.setattr(collector_aws, "aurora_writer_in", lambda _: "us-east-1")
        monkeypatch.setattr(collector_aws, "aurora_replica_lag_seconds", lambda _: 0.0)
        monkeypatch.setattr(collector_aws, "elasticache_replication_healthy", lambda _: True)
        monkeypatch.setattr(collector_aws, "api_gw_5xx_pct", lambda _: 0.0)
        yield


def test_handler_emits_metrics_and_audit(harness: None) -> None:
    out = lambda_handler({}, None)
    assert out["ok"] is True
    assert out["tier1_red"] == []
    s3 = boto3.client("s3", region_name="us-east-1")
    objs = s3.list_objects_v2(Bucket="audit-bucket", Prefix="test-app/us-east-1/observations/")
    assert objs["KeyCount"] >= 1
