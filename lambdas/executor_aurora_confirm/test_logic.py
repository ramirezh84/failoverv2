from __future__ import annotations

from lambdas.executor_aurora_confirm.logic import evaluate


def test_not_confirmed_when_writer_unknown() -> None:
    r = evaluate(
        target_region="us-east-2",
        writer_region=lambda: None,
        replica_lag_seconds=lambda: 0.0,
    )
    assert r.confirmed is False
    assert r.reason == "no_writer_yet"


def test_not_confirmed_when_writer_still_in_primary() -> None:
    r = evaluate(
        target_region="us-east-2",
        writer_region=lambda: "us-east-1",
        replica_lag_seconds=lambda: 0.0,
    )
    assert r.confirmed is False
    assert "writer_in_us-east-1_not_us-east-2" in r.reason


def test_not_confirmed_when_lag_above_threshold() -> None:
    r = evaluate(
        target_region="us-east-2",
        writer_region=lambda: "us-east-2",
        replica_lag_seconds=lambda: 10.0,
        max_acceptable_lag=5.0,
    )
    assert r.confirmed is False
    assert "replica_lag" in r.reason


def test_confirmed_when_writer_target_lag_low() -> None:
    r = evaluate(
        target_region="us-east-2",
        writer_region=lambda: "us-east-2",
        replica_lag_seconds=lambda: 0.5,
    )
    assert r.confirmed is True
    assert r.reason == "confirmed"
