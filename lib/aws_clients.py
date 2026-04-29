"""boto3 client factories that always pass an explicit ``endpoint_url`` to the
in-region VPC interface endpoint.

CLAUDE.md §2 hard constraint #4: Lambdas have no internet egress; every AWS
call leaves through a VPC interface endpoint. The lib.aws_clients factories
are the only sanctioned construction site; the ``boto3-endpoint-check`` CI
job rejects any direct ``boto3.client(...)`` without ``endpoint_url=``.

The endpoint URL for each AWS service is read from environment variables
that the orchestrator's Terraform sets at deploy time. The pattern is:
``ENDPOINT_<SERVICE>``. Region is read from ``AWS_REGION`` (the standard
Lambda environment variable).

This module imports ``boto3`` once. Test code that mocks ``boto3`` should
patch ``lib.aws_clients.boto3`` rather than re-importing.
"""

from __future__ import annotations

import os
from functools import cache
from typing import TYPE_CHECKING, Any

import boto3
from botocore.config import Config

if TYPE_CHECKING:
    from mypy_boto3_cloudwatch import CloudWatchClient
    from mypy_boto3_events import EventBridgeClient
    from mypy_boto3_health import HealthClient
    from mypy_boto3_lambda import LambdaClient
    from mypy_boto3_logs import CloudWatchLogsClient
    from mypy_boto3_rds import RDSClient
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_sns import SNSClient
    from mypy_boto3_ssm import SSMClient
    from mypy_boto3_stepfunctions import SFNClient


_DEFAULT_CONFIG = Config(
    retries={"max_attempts": 3, "mode": "adaptive"},
    connect_timeout=5,
    read_timeout=10,
    user_agent_extra="failoverv2/0.1.0",
)


def _endpoint(service_env_key: str) -> str:
    """Return the VPC endpoint URL for ``service_env_key``.

    Raises ``RuntimeError`` (not LookupError) so callers can fail loudly during
    cold start rather than at first AWS call.
    """
    url = os.environ.get(service_env_key)
    if not url:
        raise RuntimeError(
            f"{service_env_key} not set; Lambda must be deployed with VPC "
            "endpoint URLs in env (CLAUDE.md §2 #4). Use the orchestrator-runtime "
            "Terraform module which wires these for every Lambda."
        )
    return url


def _region() -> str:
    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"


@cache
def ssm() -> SSMClient:
    return boto3.client(
        "ssm",
        region_name=_region(),
        endpoint_url=_endpoint("ENDPOINT_SSM"),
        config=_DEFAULT_CONFIG,
    )


@cache
def sns() -> SNSClient:
    return boto3.client(
        "sns",
        region_name=_region(),
        endpoint_url=_endpoint("ENDPOINT_SNS"),
        config=_DEFAULT_CONFIG,
    )


@cache
def s3() -> S3Client:
    return boto3.client(
        "s3",
        region_name=_region(),
        endpoint_url=_endpoint("ENDPOINT_S3"),
        config=_DEFAULT_CONFIG,
    )


@cache
def cloudwatch() -> CloudWatchClient:
    return boto3.client(
        "cloudwatch",
        region_name=_region(),
        endpoint_url=_endpoint("ENDPOINT_CLOUDWATCH"),
        config=_DEFAULT_CONFIG,
    )


@cache
def cloudwatch_logs() -> CloudWatchLogsClient:
    return boto3.client(
        "logs",
        region_name=_region(),
        endpoint_url=_endpoint("ENDPOINT_LOGS"),
        config=_DEFAULT_CONFIG,
    )


@cache
def rds() -> RDSClient:
    return boto3.client(
        "rds",
        region_name=_region(),
        endpoint_url=_endpoint("ENDPOINT_RDS"),
        config=_DEFAULT_CONFIG,
    )


@cache
def stepfunctions() -> SFNClient:
    return boto3.client(
        "stepfunctions",
        region_name=_region(),
        endpoint_url=_endpoint("ENDPOINT_STEPFUNCTIONS"),
        config=_DEFAULT_CONFIG,
    )


# Note: no synthetics() factory — Lambdas read canary results via the
# CloudWatchSynthetics metric namespace (cloudwatch() above), not via the
# Synthetics control-plane API. Canary management happens via the console
# with an operator role.


@cache
def health() -> HealthClient:
    # AWS Health Dashboard supports regional VPC interface endpoints since
    # 2022. Each region's Lambda uses its OWN region's Health endpoint —
    # callers pass `regions=[<target>]` filter when querying. Hardcoding
    # us-east-1 here from a us-east-2 Lambda would require cross-region
    # egress that doesn't exist (CLAUDE.md §11 #1).
    #
    # Health-specific config: 1 retry max, 5s read timeout. The Health API
    # is the only signal source whose failure modes (Basic Support →
    # SubscriptionRequiredException, control-plane outage during a real
    # incident) we expect to hit, and we don't want to burn the Lambda's
    # 30s budget retrying it.
    health_config = Config(
        retries={"max_attempts": 1, "mode": "standard"},
        connect_timeout=3,
        read_timeout=5,
        user_agent_extra="failoverv2/0.1.0",
    )
    return boto3.client(
        "health",
        region_name=_region(),
        endpoint_url=_endpoint("ENDPOINT_HEALTH"),
        config=health_config,
    )


@cache
def events() -> EventBridgeClient:
    return boto3.client(
        "events",
        region_name=_region(),
        endpoint_url=_endpoint("ENDPOINT_EVENTS"),
        config=_DEFAULT_CONFIG,
    )


@cache
def lambda_() -> LambdaClient:
    return boto3.client(
        "lambda",
        region_name=_region(),
        endpoint_url=_endpoint("ENDPOINT_LAMBDA"),
        config=_DEFAULT_CONFIG,
    )


def reset_caches() -> None:
    """Clear all cached clients. Used by tests; never called in production."""
    for fn in (
        ssm,
        sns,
        s3,
        cloudwatch,
        cloudwatch_logs,
        rds,
        stepfunctions,
        health,
        events,
        lambda_,
    ):
        fn.cache_clear()


__all__ = [
    "cloudwatch",
    "cloudwatch_logs",
    "events",
    "health",
    "lambda_",
    "rds",
    "reset_caches",
    "s3",
    "sns",
    "ssm",
    "stepfunctions",
]


# These attributes are intentionally module-level so test code can monkeypatch
# `lib.aws_clients.boto3` to swap in moto/mocks without touching the real one.
def _expose_for_tests() -> dict[str, Any]:
    return {"boto3": boto3, "Config": Config}
