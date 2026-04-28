from __future__ import annotations

import pytest

from lambdas.approval_callback.handler import lambda_handler
from lib import aws_clients


class _FakeStepFunctions:
    def __init__(self) -> None:
        self.success: list[dict[str, str]] = []
        self.failure: list[dict[str, str]] = []

    def send_task_success(self, **kwargs: str) -> None:
        self.success.append(kwargs)

    def send_task_failure(self, **kwargs: str) -> None:
        self.failure.append(kwargs)


@pytest.fixture
def fake_sfn(monkeypatch: pytest.MonkeyPatch) -> _FakeStepFunctions:
    fake = _FakeStepFunctions()
    monkeypatch.setattr(aws_clients, "stepfunctions", lambda: fake)
    return fake


def test_approve_calls_send_task_success(fake_sfn: _FakeStepFunctions) -> None:
    out = lambda_handler(
        {
            "task_token": "TOKEN",
            "decision": "approve",
            "operator": "ramirezh84",
            "reason": "promoted",
        },
        None,
    )
    assert out["decision"] == "approve"
    assert fake_sfn.success
    assert fake_sfn.success[0]["taskToken"] == "TOKEN"
    assert "approved_by" in fake_sfn.success[0]["output"]
    assert not fake_sfn.failure


def test_abort_calls_send_task_failure(fake_sfn: _FakeStepFunctions) -> None:
    out = lambda_handler(
        {
            "task_token": "TOKEN",
            "decision": "abort",
            "operator": "ramirezh84",
            "reason": "rolling back",
        },
        None,
    )
    assert out["decision"] == "abort"
    assert fake_sfn.failure
    assert fake_sfn.failure[0]["error"] == "OperatorAbort"
    assert not fake_sfn.success


def test_unknown_decision_rejected(fake_sfn: _FakeStepFunctions) -> None:
    del fake_sfn
    with pytest.raises(ValueError, match=r"decision must be approve\|abort"):
        lambda_handler(
            {"task_token": "T", "decision": "skip", "operator": "x"},
            None,
        )
