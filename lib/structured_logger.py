"""JSON-formatted structured logger.

Every log line is one JSON object on one line. Required fields per
CLAUDE.md §3.1: ``app_name``, ``region``, ``execution_id`` (when applicable),
``event``, ``severity``. Additional context is merged into the same line.

Usage:

    from lib.structured_logger import get_logger
    log = get_logger(__name__)
    log.info("decision_evaluated", quorum_red=2, dwell_held=True)

Event names are restricted to the vocabulary in CLAUDE.md §3.3; the logger
emits a warning if a new event name is used. SPEC updates are required to
add new events.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any, Final

# Vocabulary from CLAUDE.md §3.3. Updated only via SPEC change.
ALLOWED_EVENTS: Final[frozenset[str]] = frozenset(
    {
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
)


class _JsonFormatter(logging.Formatter):
    """Emit each record as a single JSON line."""

    def __init__(self) -> None:
        super().__init__()
        # Standard LogRecord attributes we don't want to leak into the payload
        self._reserved = {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "taskName",
        }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "severity": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in self._reserved and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


class _OrchestratorLoggerAdapter(logging.LoggerAdapter[logging.Logger]):
    """Inject ``app_name`` and ``region`` into every record from env."""

    def process(
        self,
        msg: object,
        kwargs: dict[str, Any],  # type: ignore[override]
    ) -> tuple[object, dict[str, Any]]:
        extra: dict[str, Any] = {}
        if self.extra:
            extra.update(self.extra)
        extra.setdefault("app_name", os.environ.get("APP_NAME", "<unset>"))
        extra.setdefault("region", os.environ.get("AWS_REGION", "<unset>"))
        if "extra" in kwargs:
            extra.update(kwargs.pop("extra"))
        if isinstance(msg, str) and msg not in ALLOWED_EVENTS:
            extra.setdefault("unknown_event_warning", msg)
        merged = dict(kwargs)
        kw_extra = merged.pop("extra", {})
        if isinstance(kw_extra, dict):
            extra.update(kw_extra)
        merged["extra"] = extra
        return msg, merged


_handler_installed = False


def _install_handler() -> None:
    global _handler_installed  # noqa: PLW0603 — module-level handler is by design
    if _handler_installed:
        return
    root = logging.getLogger()
    # Lambda runtime installs its own handler; we only add ours if none exist
    # OR if AWS_LAMBDA_FUNCTION_NAME is set (force replace, since the default
    # text formatter would otherwise also emit alongside our JSON).
    in_lambda = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    if in_lambda:
        for h in list(root.handlers):
            root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root.addHandler(handler)
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
    _handler_installed = True


def get_logger(name: str, **default_extra: Any) -> _OrchestratorLoggerAdapter:
    """Return a logger that emits JSON lines.

    ``default_extra`` is merged into every log line (e.g. pass
    ``execution_id=...`` once at the top of a Lambda handler).
    """
    _install_handler()
    return _OrchestratorLoggerAdapter(logging.getLogger(name), default_extra)


def reset_for_tests() -> None:
    """Tear down the handler so tests can reinstall with their own captures."""
    global _handler_installed  # noqa: PLW0603 — same module-level handler
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    _handler_installed = False


__all__ = ["ALLOWED_EVENTS", "get_logger", "reset_for_tests"]
