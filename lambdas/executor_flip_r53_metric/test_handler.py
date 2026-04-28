from __future__ import annotations

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

from lambdas.executor_flip_r53_metric.handler import lambda_handler


@pytest.fixture
def aws_world(
    aws_credentials: None,
    vpc_endpoints: None,
) -> Iterator[None]:
    with mock_aws():
        yield


def test_trip_emits_zero(aws_world: None) -> None:
    out = lambda_handler(
        {"app_name": "test-app", "primary_region": "us-east-1", "value": 0.0},
        None,
    )
    assert out["value"] == 0.0
    cw = boto3.client("cloudwatch", region_name="us-east-1")
    metrics = cw.list_metrics(Namespace="Failover/test-app")["Metrics"]
    assert any(m["MetricName"] == "PrimaryHealthControl" for m in metrics)


def test_dry_run_does_not_emit(aws_world: None) -> None:
    out = lambda_handler(
        {
            "app_name": "test-app",
            "primary_region": "us-east-1",
            "value": 0.0,
            "dry_run": True,
        },
        None,
    )
    assert out["dry_run"] is True
    cw = boto3.client("cloudwatch", region_name="us-east-1")
    metrics = cw.list_metrics(Namespace="Failover/test-app")["Metrics"]
    assert not metrics


def test_invalid_value_rejected() -> None:
    with pytest.raises(ValueError, match=r"value must be 0\.0 or 1\.0"):
        lambda_handler(
            {"app_name": "test-app", "primary_region": "us-east-1", "value": 0.5},
            None,
        )
