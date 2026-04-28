from __future__ import annotations

import pytest

from lambdas.executor_aurora_confirm.handler import lambda_handler


def test_handler_advances_when_writer_in_target(monkeypatch: pytest.MonkeyPatch) -> None:
    from lambdas.executor_aurora_confirm import handler

    monkeypatch.setattr(handler, "aurora_writer_in", lambda _: "us-east-2")
    monkeypatch.setattr(handler, "aurora_replica_lag_seconds", lambda _: 0.5)
    out = lambda_handler(
        {
            "failover_id": "fid-1",
            "app_name": "test-app",
            "target_region": "us-east-2",
            "global_cluster_id": "test-app-global",
            "iteration": 0,
        },
        None,
    )
    assert out["confirmed"] is True
    assert out["iteration"] == 1


def test_handler_loops_when_writer_still_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    from lambdas.executor_aurora_confirm import handler

    monkeypatch.setattr(handler, "aurora_writer_in", lambda _: "us-east-1")
    monkeypatch.setattr(handler, "aurora_replica_lag_seconds", lambda _: 0.5)
    out = lambda_handler(
        {
            "failover_id": "fid-1",
            "app_name": "test-app",
            "target_region": "us-east-2",
            "global_cluster_id": "test-app-global",
        },
        None,
    )
    assert out["confirmed"] is False
    assert "writer_in_us-east-1_not_us-east-2" in out["reason"]
