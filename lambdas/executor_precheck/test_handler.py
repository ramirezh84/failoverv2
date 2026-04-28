from __future__ import annotations

import pytest

from lambdas.executor_precheck import handler as precheck_handler
from lambdas.executor_precheck.handler import lambda_handler


def test_handler_returns_event_with_precheck_payload() -> None:
    out = lambda_handler(
        {
            "failover_id": "fid-1",
            "app_name": "test-app",
            "target_region": "us-east-2",
        },
        None,
    )
    assert out["precheck"]["ok"] is True
    assert out["precheck"]["target_region"] == "us-east-2"


def test_handler_raises_when_target_unhealthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(precheck_handler, "_ecs_running", lambda _: 0)
    with pytest.raises(RuntimeError, match=r"PRECHECK failed"):
        lambda_handler(
            {"failover_id": "fid-1", "app_name": "test-app", "target_region": "us-east-2"},
            None,
        )
