"""Unit tests for aws_health_open_events fail-open behavior."""

from __future__ import annotations

import pytest

from lambdas.signal_collector import aws as collector_aws


def test_returns_empty_when_endpoint_health_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the org doesn't provision a Health VPCE, signal_collector treats
    the signal as permanently green (no events) without attempting any
    network call."""
    monkeypatch.delenv("ENDPOINT_HEALTH", raising=False)
    assert collector_aws.aws_health_open_events("us-east-1") == []


def test_endpoint_health_empty_string_treated_as_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENDPOINT_HEALTH", "")
    assert collector_aws.aws_health_open_events("us-east-1") == []
