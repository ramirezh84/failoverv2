from __future__ import annotations

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

from lambdas.manual_trigger.handler import lambda_handler


@pytest.fixture
def harness(
    aws_credentials: None,
    vpc_endpoints: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    del aws_credentials, vpc_endpoints
    monkeypatch.setenv("APP_NAME", "test-app")
    monkeypatch.setenv("PROFILE_BUCKET", "profile-bucket")
    monkeypatch.setenv("PROFILE_KEY", "test-app/profile.yaml")
    monkeypatch.setenv(
        "FAILOVER_STATE_MACHINE_ARN",
        "arn:aws:states:us-east-1:000000000000:stateMachine:failover",
    )
    monkeypatch.setenv(
        "FAILBACK_STATE_MACHINE_ARN",
        "arn:aws:states:us-east-1:000000000000:stateMachine:failback",
    )
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="profile-bucket")
        with open("profiles/test-app.yaml", "rb") as f:
            s3.put_object(Bucket="profile-bucket", Key="test-app/profile.yaml", Body=f.read())
        # Patch the SFN start; moto's stepfunctions mock requires a defined SM
        # which is a lot of setup; we replace the wrapper.
        from lambdas.manual_trigger import handler as mt_handler  # noqa: PLC0415

        monkeypatch.setattr(
            mt_handler,
            "start_failover_execution",
            lambda **kwargs: (
                f"arn:aws:states:us-east-1:000000000000:execution:{kwargs['execution_name']}"
            ),
        )
        yield


def test_handler_returns_execution_arn(harness: None) -> None:
    out = lambda_handler(
        {"direction": "failover", "operator": "ramirezh84"},
        None,
    )
    assert out["ok"] is True
    assert out["execution_arn"].startswith("arn:aws:states:")
    assert out["input"]["direction"] == "failover"


def test_handler_dryrun_marks_dry_run(harness: None) -> None:
    out = lambda_handler({"direction": "dryrun", "operator": "x"}, None)
    assert out["input"]["dry_run"] is True


def test_handler_rejects_unknown_direction(harness: None) -> None:
    with pytest.raises(ValueError, match=r"direction must be"):
        lambda_handler({"direction": "rollback", "operator": "x"}, None)
