from __future__ import annotations

import json
from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

from lib import sns_publisher


@pytest.fixture
def topic(
    aws_credentials: None,
    vpc_endpoints: None,
) -> Iterator[str]:
    with mock_aws():
        sns = boto3.client("sns", region_name="us-east-1")
        topic_arn = sns.create_topic(Name="failover-events")["TopicArn"]
        sqs = boto3.client("sqs", region_name="us-east-1")
        q = sqs.create_queue(QueueName="test-q")["QueueUrl"]
        q_arn = sqs.get_queue_attributes(QueueUrl=q, AttributeNames=["QueueArn"])["Attributes"][
            "QueueArn"
        ]
        sns.subscribe(TopicArn=topic_arn, Protocol="sqs", Endpoint=q_arn)
        yield topic_arn


def _drain_subject(topic_arn: str) -> str:
    sqs = boto3.client("sqs", region_name="us-east-1")
    q_url = sqs.get_queue_url(QueueName="test-q")["QueueUrl"]
    msgs = sqs.receive_message(QueueUrl=q_url, MaxNumberOfMessages=10).get("Messages", [])
    if not msgs:
        return ""
    body = json.loads(msgs[0]["Body"])
    subject_value = body.get("Subject", "")
    return str(subject_value)


def test_publish_event_round_trip(topic: str) -> None:
    result = sns_publisher.publish_event(
        topic_arn=topic,
        app_name="test-app",
        event="failover_authorized",
        detail={"reason": "tier1_quorum_held"},
    )
    assert result.message_id
    assert result.topic_arn == topic
    subject = _drain_subject(topic)
    # Human-readable subject: [SEVERITY] <title>: <app>
    assert subject.startswith("[INFO] ")
    assert "test-app" in subject


def test_dry_run_marks_subject(topic: str) -> None:
    sns_publisher.publish_event(
        topic_arn=topic,
        app_name="test-app",
        event="failover_initiated",
        detail={},
        dry_run=True,
    )
    subject = _drain_subject(topic)
    assert "[DRY-RUN]" in subject


def test_body_contains_human_summary_and_raw_json(topic: str) -> None:
    sns_publisher.publish_event(
        topic_arn=topic,
        app_name="test-app",
        event="failover_initiated",
        detail={"source_region": "us-east-1", "target_region": "us-east-2", "operator": "sre"},
        severity="CRITICAL",
    )
    sqs = boto3.client("sqs", region_name="us-east-1")
    q_url = sqs.get_queue_url(QueueName="test-q")["QueueUrl"]
    msgs = sqs.receive_message(QueueUrl=q_url, MaxNumberOfMessages=10).get("Messages", [])
    sns_msg = json.loads(msgs[0]["Body"])["Message"]
    # Human summary first.
    assert "FAILOVER STARTED" in sns_msg
    assert "us-east-1" in sns_msg
    assert "us-east-2" in sns_msg
    assert "Operator:" in sns_msg
    assert "Next steps:" in sns_msg
    # Raw JSON after the separator — programmatic consumers split here.
    assert "--- raw event payload (JSON) ---" in sns_msg
    raw_json = sns_msg.split("--- raw event payload (JSON) ---", 1)[1].strip()
    payload = json.loads(raw_json)
    assert payload["app_name"] == "test-app"
    assert payload["event"] == "failover_initiated"
    assert payload["detail"]["target_region"] == "us-east-2"


def test_message_attributes_include_app_name_and_event(topic: str) -> None:
    sns_publisher.publish_event(
        topic_arn=topic,
        app_name="test-app",
        event="failover_step_completed",
        detail={"step": "FLIP_R53_CONTROL_METRIC"},
        severity="INFO",
    )
    sqs = boto3.client("sqs", region_name="us-east-1")
    q_url = sqs.get_queue_url(QueueName="test-q")["QueueUrl"]
    msgs = sqs.receive_message(QueueUrl=q_url, MaxNumberOfMessages=10).get("Messages", [])
    body = json.loads(msgs[0]["Body"])
    attrs = body.get("MessageAttributes", {})
    assert attrs["app_name"]["Value"] == "test-app"
    assert attrs["event"]["Value"] == "failover_step_completed"
    assert attrs["severity"]["Value"] == "INFO"
    assert attrs["dry_run"]["Value"] == "false"
