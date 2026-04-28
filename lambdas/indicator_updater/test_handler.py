from __future__ import annotations

from collections.abc import Iterator

import pytest
from moto import mock_aws

from lambdas.indicator_updater.handler import lambda_handler
from lib import indicator_writer


@pytest.fixture
def aws_world(
    aws_credentials: None,
    vpc_endpoints: None,
) -> Iterator[None]:
    with mock_aws():
        yield


def test_writes_role_and_emits_audit(aws_world: None) -> None:
    out = lambda_handler(
        {
            "app_name": "test-app",
            "region": "us-east-1",
            "role": "DRAINING",
            "executor_run_id": "exec-A",
            "sequence": 4,
        },
        None,
    )
    assert out == {
        "ok": True,
        "role": "DRAINING",
        "region": "us-east-1",
        "executor_run_id": "exec-A",
        "sequence": 4,
    }
    assert indicator_writer.read_role("test-app", "us-east-1") == "DRAINING"


def test_dry_run_does_not_write(aws_world: None) -> None:
    out = lambda_handler(
        {
            "app_name": "test-app",
            "region": "us-east-1",
            "role": "ACTIVE",
            "executor_run_id": "exec-A",
            "sequence": 4,
            "dry_run": True,
        },
        None,
    )
    assert out["dry_run"] is True
    assert indicator_writer.read_role("test-app", "us-east-1") is None
