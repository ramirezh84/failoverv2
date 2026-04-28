from __future__ import annotations

import io
import json
import logging

import pytest

from lib import structured_logger


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    """Replace the JSON handler's stream with a StringIO."""
    structured_logger.reset_for_tests()
    monkeypatch.setenv("APP_NAME", "test-app")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "test-lambda")
    buf = io.StringIO()
    log = structured_logger.get_logger("test")
    # Replace the handler stream after install
    root = logging.getLogger()
    handler = root.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    handler.stream = buf
    log.info("decision_evaluated", extra={"quorum_red": 2, "dwell_held": True})
    return buf


def test_emits_one_json_line_with_required_fields(captured: io.StringIO) -> None:
    line = captured.getvalue().strip()
    assert line, "no line emitted"
    record = json.loads(line)
    assert record["event"] == "decision_evaluated"
    assert record["app_name"] == "test-app"
    assert record["region"] == "us-east-1"
    assert record["severity"] == "INFO"
    assert record["quorum_red"] == 2
    assert record["dwell_held"] is True
    assert "ts" in record


def test_unknown_event_name_records_warning_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    structured_logger.reset_for_tests()
    monkeypatch.setenv("APP_NAME", "test-app")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "test-lambda")
    buf = io.StringIO()
    log = structured_logger.get_logger("test")
    handler = logging.getLogger().handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    handler.stream = buf
    log.info("not_in_vocabulary", extra={})
    rec = json.loads(buf.getvalue().strip())
    assert rec["unknown_event_warning"] == "not_in_vocabulary"


def test_handler_install_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    structured_logger.reset_for_tests()
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    structured_logger.get_logger("a")
    n_first = len(logging.getLogger().handlers)
    structured_logger.get_logger("b")
    n_second = len(logging.getLogger().handlers)
    assert n_first == n_second


def test_allowed_events_matches_claude_md_vocabulary() -> None:
    expected = {
        "signal_collected",
        "signal_red",
        "signal_recovered",
        "decision_evaluated",
        "decision_changed",
        "failover_authorized",
        "state_machine_started",
        "state_machine_step_entered",
        "state_machine_step_completed",
        "state_machine_step_failed",
        "aurora_gate_paused",
        "aurora_gate_approved",
        "aurora_gate_aborted",
        "aurora_writer_confirmed",
        "r53_control_metric_emitted",
        "indicator_updated",
        "dry_run_action_skipped",
    }
    assert expected == structured_logger.ALLOWED_EVENTS
