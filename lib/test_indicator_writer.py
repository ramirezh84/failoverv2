from __future__ import annotations

from collections.abc import Iterator

import pytest
from moto import mock_aws

from lib import indicator_writer

APP = "test-app"


@pytest.fixture
def aws_world(
    aws_credentials: None,
    vpc_endpoints: None,
) -> Iterator[None]:
    with mock_aws():
        yield


def test_write_role_round_trips(aws_world: None) -> None:
    write = indicator_writer.write_role(
        APP, "us-east-1", "ACTIVE", executor_run_id="exec-A", sequence=3
    )
    assert write.role == "ACTIVE"
    assert write.executor_run_id == "exec-A"
    assert write.sequence == 3
    assert indicator_writer.read_role(APP, "us-east-1") == "ACTIVE"


def test_read_role_returns_none_when_unset(aws_world: None) -> None:
    assert indicator_writer.read_role(APP, "us-east-2") is None


def test_invalid_role_rejected_at_write_time() -> None:
    with pytest.raises(ValueError, match="role must be one of"):
        indicator_writer.write_role(
            APP,
            "us-east-1",
            "QUIESCED",  # type: ignore[arg-type]
            executor_run_id="x",
            sequence=0,
        )


def test_missing_executor_run_id_rejected() -> None:
    with pytest.raises(ValueError, match="executor_run_id is required"):
        indicator_writer.write_role(APP, "us-east-1", "ACTIVE", executor_run_id="", sequence=0)


def test_negative_sequence_rejected() -> None:
    with pytest.raises(ValueError, match="sequence must be non-negative"):
        indicator_writer.write_role(APP, "us-east-1", "ACTIVE", executor_run_id="x", sequence=-1)


def test_role_transitions_active_draining_passive(aws_world: None) -> None:
    indicator_writer.write_role(APP, "us-east-1", "ACTIVE", executor_run_id="x", sequence=0)
    indicator_writer.write_role(APP, "us-east-1", "DRAINING", executor_run_id="x", sequence=1)
    indicator_writer.write_role(APP, "us-east-1", "PASSIVE", executor_run_id="x", sequence=2)
    assert indicator_writer.read_role(APP, "us-east-1") == "PASSIVE"


def test_corrupted_indicator_value_raises_runtime_error(aws_world: None) -> None:
    import boto3  # noqa: PLC0415 — moto-only test fixture

    boto3.client("ssm", region_name="us-east-1").put_parameter(
        Name="/failover/test-app/us-east-1/role",
        Value="WAT",
        Type="String",
    )
    with pytest.raises(RuntimeError, match="contains 'WAT'"):
        indicator_writer.read_role(APP, "us-east-1")
