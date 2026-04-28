from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime

import boto3
import pytest
from moto import mock_aws

from lib import state_store

# All tests use moto + the lib.aws_clients factories. Endpoints come from
# the vpc_endpoints fixture; moto ignores the URL and intercepts at the
# botocore level.

APP = "test-app"
REGION = "us-east-1"
BUCKET = "audit-bucket"


@pytest.fixture
def aws_world(
    aws_credentials: None,
    vpc_endpoints: None,
) -> Iterator[None]:
    with mock_aws():
        # Pre-create the S3 audit bucket
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        yield


def _record(state: state_store.DecisionState = "GREEN") -> state_store.DecisionRecord:
    return state_store.DecisionRecord(
        state=state,
        reason="all signals green",
        timestamp=datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC),
        tier1_red_signals=(),
        quorum_held=False,
        dwell_held=False,
        hysteresis_held=True,
        secondary_safe=True,
        profile_version="abc123",
        extra={"profile_loaded_at": "2026-04-27T11:59:50Z"},
    )


def test_decision_record_round_trips_through_json() -> None:
    rec = _record(state="WATCHING")
    j = rec.to_json()
    rec2 = state_store.DecisionRecord.from_json(j)
    assert rec2 == rec


def test_write_and_read_decision(aws_world: None) -> None:
    state_store.write_decision(APP, REGION, _record(), BUCKET)
    fetched = state_store.read_latest_decision(APP, REGION)
    assert fetched is not None
    assert fetched.state == "GREEN"
    assert fetched.profile_version == "abc123"


def test_read_latest_decision_returns_none_when_unset(aws_world: None) -> None:
    fetched = state_store.read_latest_decision(APP, REGION)
    assert fetched is None


def test_observation_snapshot_lands_in_s3(aws_world: None) -> None:
    ts = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
    state_store.write_observation(APP, REGION, {"canary_pct": 100, "nlb_unhealthy": 0}, BUCKET, ts)
    s3 = boto3.client("s3", region_name="us-east-1")
    keys = [obj["Key"] for obj in s3.list_objects_v2(Bucket=BUCKET)["Contents"]]
    assert any(k.startswith(f"{APP}/{REGION}/observations/") for k in keys)


def test_executor_run_record_is_idempotent_per_failover_id(aws_world: None) -> None:
    failover_id = "failover-test-app-20260427-failover-001-abc1"
    state_store.write_executor_run(APP, REGION, failover_id, {"path": ["EVALUATE"]}, BUCKET)
    state_store.write_executor_run(
        APP, REGION, failover_id, {"path": ["EVALUATE", "PRECHECK"]}, BUCKET
    )
    s3 = boto3.client("s3", region_name="us-east-1")
    objs = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{APP}/{REGION}/executor-runs/")
    assert objs["KeyCount"] == 1
    body = json.loads(s3.get_object(Bucket=BUCKET, Key=objs["Contents"][0]["Key"])["Body"].read())
    assert body == {"path": ["EVALUATE", "PRECHECK"]}


def test_claim_in_flight_grants_then_blocks_other(aws_world: None) -> None:
    a = state_store.claim_in_flight(APP, REGION, "id-A")
    b = state_store.claim_in_flight(APP, REGION, "id-B")
    assert a is True
    assert b is False
    # Same id can re-claim
    same = state_store.claim_in_flight(APP, REGION, "id-A")
    assert same is True


def test_release_in_flight_is_safe_when_unset(aws_world: None) -> None:
    state_store.release_in_flight(APP, REGION)  # should not raise


def test_release_then_other_can_claim(aws_world: None) -> None:
    assert state_store.claim_in_flight(APP, REGION, "id-A") is True
    state_store.release_in_flight(APP, REGION)
    assert state_store.claim_in_flight(APP, REGION, "id-B") is True
