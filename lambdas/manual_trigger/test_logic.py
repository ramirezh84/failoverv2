from __future__ import annotations

from datetime import UTC, datetime

import pytest

from lambdas.manual_trigger.logic import build_execution_input
from lib.profile_loader import load_from_path

PROFILE = load_from_path("profiles/test-app.yaml")
NOW = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)


def test_failover_direction_targets_secondary() -> None:
    out = build_execution_input(
        profile=PROFILE,
        direction="failover",
        requested_target_region=None,
        operator="ramirezh84",
        now=NOW,
        dry_run=False,
    )
    assert out["input"]["source_region"] == "us-east-1"
    assert out["input"]["target_region"] == "us-east-2"
    assert out["input"]["direction"] == "failover"
    assert out["input"]["dry_run"] is False
    assert out["execution_name"].startswith("failover-test-app-")


def test_failback_direction_targets_primary() -> None:
    out = build_execution_input(
        profile=PROFILE,
        direction="failback",
        requested_target_region=None,
        operator="ramirezh84",
        now=NOW,
        dry_run=False,
    )
    assert out["input"]["source_region"] == "us-east-2"
    assert out["input"]["target_region"] == "us-east-1"


def test_explicit_wrong_target_rejected() -> None:
    with pytest.raises(ValueError, match="Failover target must be us-east-2"):
        build_execution_input(
            profile=PROFILE,
            direction="failover",
            requested_target_region="us-east-1",
            operator="x",
            now=NOW,
            dry_run=False,
        )


def test_dryrun_direction_marks_dry_run_true() -> None:
    out = build_execution_input(
        profile=PROFILE,
        direction="dryrun",
        requested_target_region=None,
        operator="x",
        now=NOW,
        dry_run=False,
    )
    assert out["input"]["dry_run"] is True


def test_profile_snapshot_carries_aurora_settings() -> None:
    out = build_execution_input(
        profile=PROFILE,
        direction="failover",
        requested_target_region=None,
        operator="x",
        now=NOW,
        dry_run=False,
    )
    snap = out["input"]["profile_snapshot"]
    assert snap["aurora_manual_approval_required"] is True
    assert snap["dns_first_failover"] is True
    assert snap["aurora_confirm_timeout_minutes"] == 30
