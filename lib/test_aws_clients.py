from __future__ import annotations

import os

import pytest

from lib import aws_clients


@pytest.mark.usefixtures("aws_credentials", "vpc_endpoints")
def test_every_factory_passes_endpoint_url() -> None:
    """Every factory must wire endpoint_url through to the boto3 client.

    The ``vpc_endpoints`` test fixture sets ``ENDPOINT_*`` to standard regional
    AWS hosts so moto can intercept; the production factories simply pass
    those values through to ``boto3.client(endpoint_url=...)``.
    """
    factories_to_env = {
        aws_clients.ssm: "ENDPOINT_SSM",
        aws_clients.sns: "ENDPOINT_SNS",
        aws_clients.s3: "ENDPOINT_S3",
        aws_clients.cloudwatch: "ENDPOINT_CLOUDWATCH",
        aws_clients.cloudwatch_logs: "ENDPOINT_LOGS",
        aws_clients.rds: "ENDPOINT_RDS",
        aws_clients.stepfunctions: "ENDPOINT_STEPFUNCTIONS",
        aws_clients.synthetics: "ENDPOINT_SYNTHETICS",
        aws_clients.health: "ENDPOINT_HEALTH",
        aws_clients.events: "ENDPOINT_EVENTS",
        aws_clients.lambda_: "ENDPOINT_LAMBDA",
    }
    for factory, env_key in factories_to_env.items():
        client = factory()
        expected = os.environ[env_key]
        assert client.meta.endpoint_url == expected, f"{factory.__name__} did not honor {env_key}"


@pytest.mark.usefixtures("aws_credentials", "vpc_endpoints")
def test_factory_caches_client_instance() -> None:
    a = aws_clients.ssm()
    b = aws_clients.ssm()
    assert a is b
    aws_clients.reset_caches()
    c = aws_clients.ssm()
    assert c is not a


@pytest.mark.usefixtures("aws_credentials")
def test_missing_endpoint_env_raises_clear_error() -> None:
    """A Lambda missing an ENDPOINT_ env var must fail loudly at cold start."""
    os.environ.pop("ENDPOINT_SSM", None)
    aws_clients.reset_caches()
    with pytest.raises(RuntimeError, match="ENDPOINT_SSM not set"):
        aws_clients.ssm()


@pytest.mark.usefixtures("aws_credentials", "vpc_endpoints")
def test_health_client_pinned_to_us_east_1() -> None:
    # The Health control plane only exists in us-east-1; the factory pins it.
    os.environ["AWS_REGION"] = "us-east-2"
    aws_clients.reset_caches()
    client = aws_clients.health()
    assert client.meta.region_name == "us-east-1"
