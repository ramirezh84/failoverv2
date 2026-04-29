"""Shared pytest fixtures.

Lives at repo root so it applies to all test files (lib/, lambdas/, cli/, tests/).
Every test that touches AWS uses moto via the ``aws_credentials`` and
``vpc_endpoints`` fixtures, plus the ``reset_aws_clients`` autouse fixture
to drop any cached boto3 client between tests.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from lib import aws_clients, structured_logger

# Standard regional AWS service hosts. Moto intercepts requests matching
# these hostnames; passing them as the lib.aws_clients endpoint_url keeps
# production code paths exercised while letting moto answer.
_REGION_FOR_TESTS = "us-east-1"
_AWS_HOSTS_USE1: dict[str, str] = {
    "ENDPOINT_SSM": f"https://ssm.{_REGION_FOR_TESTS}.amazonaws.com",
    "ENDPOINT_SNS": f"https://sns.{_REGION_FOR_TESTS}.amazonaws.com",
    "ENDPOINT_S3": "https://s3.amazonaws.com",
    "ENDPOINT_CLOUDWATCH": f"https://monitoring.{_REGION_FOR_TESTS}.amazonaws.com",
    "ENDPOINT_LOGS": f"https://logs.{_REGION_FOR_TESTS}.amazonaws.com",
    "ENDPOINT_RDS": f"https://rds.{_REGION_FOR_TESTS}.amazonaws.com",
    "ENDPOINT_STEPFUNCTIONS": f"https://states.{_REGION_FOR_TESTS}.amazonaws.com",
    "ENDPOINT_HEALTH": "https://health.us-east-1.amazonaws.com",
    "ENDPOINT_EVENTS": f"https://events.{_REGION_FOR_TESTS}.amazonaws.com",
    "ENDPOINT_LAMBDA": f"https://lambda.{_REGION_FOR_TESTS}.amazonaws.com",
}


@pytest.fixture
def aws_credentials() -> Iterator[None]:
    """Mocked AWS credentials and region for moto."""
    saved = {
        k: os.environ.get(k)
        for k in (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SECURITY_TOKEN",
            "AWS_SESSION_TOKEN",
            "AWS_DEFAULT_REGION",
            "AWS_REGION",
        )
    }
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"  # noqa: S105
    os.environ["AWS_SECURITY_TOKEN"] = "testing"  # noqa: S105
    os.environ["AWS_SESSION_TOKEN"] = "testing"  # noqa: S105
    os.environ["AWS_DEFAULT_REGION"] = _REGION_FOR_TESTS
    os.environ["AWS_REGION"] = _REGION_FOR_TESTS
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture
def vpc_endpoints() -> Iterator[None]:
    """Set ENDPOINT_* env vars to standard regional AWS hosts.

    Moto intercepts based on host pattern, so using the real AWS hostnames
    (rather than fake VPC endpoint URLs) lets moto answer while still
    exercising the production code path that passes ``endpoint_url=``.
    """
    saved = {k: os.environ.get(k) for k in _AWS_HOSTS_USE1}
    for k, v in _AWS_HOSTS_USE1.items():
        os.environ[k] = v
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture(autouse=True)
def reset_aws_clients() -> Iterator[None]:
    """Drop cached boto3 clients between tests so endpoint env changes apply."""
    aws_clients.reset_caches()
    yield
    aws_clients.reset_caches()


@pytest.fixture(autouse=True)
def reset_logger() -> Iterator[None]:
    """Reset the structured logger handler between tests."""
    structured_logger.reset_for_tests()
    yield
    structured_logger.reset_for_tests()


@pytest.fixture
def app_env() -> Iterator[None]:
    """Set APP_NAME so the structured logger has a value to inject."""
    saved = os.environ.get("APP_NAME")
    os.environ["APP_NAME"] = "test-app"
    yield
    if saved is None:
        os.environ.pop("APP_NAME", None)
    else:
        os.environ["APP_NAME"] = saved
