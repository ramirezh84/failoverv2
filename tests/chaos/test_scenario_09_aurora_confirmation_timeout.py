"""Scenario 09: Aurora confirmation gate timeout.

The full aurora-gate-timeout scenario requires real Aurora cluster
manipulation (failover_global_cluster + writer-region polling) which makes
the test 10+ min and needs cluster-level cleanup. We defer that variant.

Coverage in this POC: assert that the AURORA_GATE_PAUSE state in the
deployed failover SFN has a TimeoutSecondsPath setting and a Catch handler
for States.Timeout. This validates the contract without exercising the
gate end-to-end.

See ``docs/scenarios/scenario-09-aurora-confirmation-timeout.md``.
"""

from __future__ import annotations

import json

import boto3
import pytest

from tests.chaos import framework as fw

pytestmark = pytest.mark.chaos


def test_scenario_09() -> None:
    state: dict = {}

    def setup() -> None:
        session = boto3.Session(profile_name=fw.PROFILE)
        sfn = session.client("stepfunctions", region_name=fw.PRIMARY_REGION)
        sts = session.client("sts", region_name=fw.PRIMARY_REGION)
        account = sts.get_caller_identity()["Account"]
        arn = f"arn:aws:states:{fw.PRIMARY_REGION}:{account}:stateMachine:{fw.APP}-failover"
        defn = json.loads(sfn.describe_state_machine(stateMachineArn=arn)["definition"])
        state["aurora_gate"] = defn["States"].get("AURORA_GATE_PAUSE", {})

    def assertions() -> dict[str, callable]:
        return {
            "aurora_gate_has_timeout_path": lambda: (
                "TimeoutSecondsPath" in state["aurora_gate"],
                f"keys={list(state['aurora_gate'].keys())}",
            ),
            "aurora_gate_catches_timeout": lambda: (
                any(
                    "States.Timeout" in c.get("ErrorEquals", [])
                    for c in state["aurora_gate"].get("Catch", [])
                ),
                f"catches={state['aurora_gate'].get('Catch')}",
            ),
            "aurora_gate_publishes_with_task_token": lambda: (
                state["aurora_gate"].get("Resource", "").endswith("waitForTaskToken"),
                f"resource={state['aurora_gate'].get('Resource')}",
            ),
        }

    def cleanup() -> None:
        pass

    result = fw.run_scenario(
        name="scenario-09-aurora-confirmation-timeout",
        setup=setup,
        wait_seconds=0,
        assertions=assertions,
        cleanup=cleanup,
    )
    assert result.passed, "\n".join(result.failures)
