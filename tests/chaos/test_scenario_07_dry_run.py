"""Scenario 07: Operator triggers a dry-run failover via manual_trigger.

The state machine should run end-to-end emitting SNS notifications with
``[DRY-RUN]`` markers and ``dry_run_action_skipped`` log events, but must NOT
mutate any indicator parameter, R53 control metric, or Aurora writer.

See ``docs/scenarios/scenario-07-dry-run.md`` for the full walkthrough.
This test runs against a deployed test harness (``make harness-up`` first).
"""

from __future__ import annotations

import json

import boto3
import pytest

from tests.chaos import framework as fw

pytestmark = pytest.mark.chaos


def _ssm_param_missing(region: str, name: str) -> tuple[bool, str]:
    session = boto3.Session(profile_name=fw.PROFILE)
    ssm = session.client("ssm", region_name=region)
    try:
        v = ssm.get_parameter(Name=name)["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        return True, "absent"
    return False, f"present={v}"


def _invoke_manual_trigger() -> dict:
    session = boto3.Session(profile_name=fw.PROFILE)
    lam = session.client("lambda", region_name=fw.PRIMARY_REGION)
    resp = lam.invoke(
        FunctionName=f"{fw.APP}-manual_trigger-use1",
        Payload=json.dumps(
            {"direction": "dryrun", "operator": "scenario-07", "dry_run": True}
        ).encode(),
    )
    return json.loads(resp["Payload"].read())


def test_scenario_07() -> None:
    invoke_result: dict = {}

    def setup() -> None:
        fw.reset_orchestrator_state()
        invoke_result.update(_invoke_manual_trigger())

    def assertions() -> dict[str, callable]:
        return {
            "trigger_returned_ok": lambda: (
                invoke_result.get("ok", False),
                f"trigger_response={invoke_result}",
            ),
            "primary_role_unset": lambda: _ssm_param_missing(
                fw.PRIMARY_REGION, f"/failover/{fw.APP}/{fw.PRIMARY_REGION}/role"
            ),
            "secondary_role_unset": lambda: _ssm_param_missing(
                fw.SECONDARY_REGION, f"/failover/{fw.APP}/{fw.SECONDARY_REGION}/role"
            ),
        }

    def cleanup() -> None:
        fw.reset_orchestrator_state()

    result = fw.run_scenario(
        name="scenario-07-dry-run",
        setup=setup,
        wait_seconds=120,
        assertions=assertions,
        cleanup=cleanup,
    )
    assert result.passed, "\n".join(result.failures)
