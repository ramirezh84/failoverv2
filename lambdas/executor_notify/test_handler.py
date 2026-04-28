from __future__ import annotations

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

from lambdas.executor_notify.handler import lambda_handler


@pytest.fixture
def topic(
    aws_credentials: None,
    vpc_endpoints: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[str]:
    with mock_aws():
        sns = boto3.client("sns", region_name="us-east-1")
        topic_arn = sns.create_topic(Name="failover-events")["TopicArn"]
        monkeypatch.setenv("SNS_TOPIC_ARN", topic_arn)
        yield topic_arn


def test_publishes_event_with_message_id(topic: str) -> None:
    out = lambda_handler(
        {
            "event_name": "failover_initiated",
            "app_name": "test-app",
            "failover_id": "id-1",
            "step": "NOTIFY_INITIATED",
            "detail": {"reason": "manual"},
        },
        None,
    )
    assert out["ok"] is True
    assert out["message_id"]
    assert out["event_name"] == "failover_initiated"


def test_dry_run_does_not_publish(topic: str) -> None:
    out = lambda_handler(
        {
            "event_name": "failover_completed",
            "app_name": "test-app",
            "failover_id": "id-1",
            "dry_run": True,
        },
        None,
    )
    assert out["dry_run"] is True
    assert "message_id" not in out


def test_unknown_event_name_rejected(topic: str) -> None:
    with pytest.raises(ValueError, match="event_name not in vocabulary"):
        lambda_handler({"event_name": "made_up", "app_name": "test-app"}, None)
