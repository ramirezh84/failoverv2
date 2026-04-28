from __future__ import annotations

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

from lambdas.decision_engine import handler as de_handler
from lambdas.decision_engine.handler import lambda_handler


@pytest.fixture
def harness(
    aws_credentials: None,
    vpc_endpoints: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[str]:
    del aws_credentials, vpc_endpoints
    monkeypatch.setenv("APP_NAME", "test-app")
    monkeypatch.setenv("PROFILE_BUCKET", "profile-bucket")
    monkeypatch.setenv("PROFILE_KEY", "test-app/profile.yaml")
    monkeypatch.setenv("AUDIT_BUCKET", "audit-bucket")
    with mock_aws():
        sns = boto3.client("sns", region_name="us-east-1")
        topic_arn = sns.create_topic(Name="failover-events")["TopicArn"]
        monkeypatch.setenv("SNS_TOPIC_ARN", topic_arn)
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="profile-bucket")
        s3.create_bucket(Bucket="audit-bucket")
        with open("profiles/test-app.yaml", "rb") as f:
            s3.put_object(Bucket="profile-bucket", Key="test-app/profile.yaml", Body=f.read())
        # Quiet the AWS readers
        monkeypatch.setattr(de_handler, "fetch_current_red_signals", lambda *_: [])
        monkeypatch.setattr(de_handler, "fetch_signal_red_history", lambda *_, **__: [])
        monkeypatch.setattr(de_handler, "secondary_warm_standby_ready", lambda _: True)
        monkeypatch.setattr(de_handler, "emit_quorum_red_metric", lambda *_, **__: None)
        monkeypatch.setattr(de_handler, "emit_failover_control_metric", lambda *_, **__: None)
        yield topic_arn


def test_handler_writes_decision_when_green(harness: str) -> None:
    out = lambda_handler({"profile_version": "v1"}, None)
    assert out["ok"] is True
    assert out["state"] == "GREEN"
    assert out["failover_authorized"] is False


def test_handler_records_failover_authorized(monkeypatch: pytest.MonkeyPatch, harness: str) -> None:
    monkeypatch.setattr(de_handler, "fetch_current_red_signals", lambda *_: ["nlb", "canary"])
    monkeypatch.setattr(de_handler, "fetch_signal_red_history", lambda *_, **__: [True] * 10)
    out = lambda_handler({"profile_version": "v1"}, None)
    # auto_failover defaults to false in the test profile, so we get the
    # alert-only state, but the authorization flag is True.
    assert out["state"] == "FAILOVER_AUTHORIZED_BUT_NOT_AUTO"
    assert out["failover_authorized"] is True
