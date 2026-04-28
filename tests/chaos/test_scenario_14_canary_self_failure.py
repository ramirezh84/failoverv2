"""Scenario 14: non-mutating signal injection — verify no failover was triggered.

See ``docs/scenarios/scenario-14-canary-self-failure.md`` for the walkthrough.
This test runs against a deployed test harness (``make harness-up`` first).
"""

from __future__ import annotations

import pytest

from tests.chaos import framework as fw

pytestmark = pytest.mark.chaos


def test_scenario_14() -> None:
    def setup() -> None:
        fw.reset_orchestrator_state()
        fw.force_signal_red("canary_failure", 1.0)

    def assertions() -> dict[str, callable]:
        return {
            "no_failover_started": lambda: fw.assert_no_failover_started(since_seconds=180),
            "primary_alarm_ok": lambda: fw.assert_alarm_state(
                f"{fw.APP}-PrimaryHealthControl-use1", fw.PRIMARY_REGION, "OK"
            ),
        }

    def cleanup() -> None:
        fw.reset_orchestrator_state()

    result = fw.run_scenario(
        name="scenario-14-canary-self-failure",
        setup=setup,
        wait_seconds=90,
        assertions=assertions,
        cleanup=cleanup,
    )
    assert result.passed, "\n".join(result.failures)
