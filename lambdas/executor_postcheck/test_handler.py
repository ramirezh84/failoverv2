from __future__ import annotations

import pytest

from lambdas.executor_postcheck import handler as postcheck_handler
from lambdas.executor_postcheck.handler import lambda_handler


def test_handler_passes_when_target_healthy() -> None:
    out = lambda_handler(
        {
            "failover_id": "fid-1",
            "app_name": "test-app",
            "target_region": "us-east-2",
        },
        None,
    )
    assert out["postcheck"]["ok"] is True


def test_handler_raises_when_target_red(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(postcheck_handler, "_target_red", lambda _: ["nlb_unhealthy"])
    with pytest.raises(RuntimeError, match=r"POSTCHECK failed"):
        lambda_handler(
            {"failover_id": "fid-1", "app_name": "test-app", "target_region": "us-east-2"},
            None,
        )
