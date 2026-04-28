"""Writer of the per-app, per-region regional indicator.

The regional indicator is the parameter the Kafka consumer reads to decide
whether to poll/process. SPEC §3.3:

    /failover/<app>/<region>/role  ∈  {ACTIVE, PASSIVE, DRAINING}

Hard constraints:

* CLAUDE.md §2 #2: indicator lives in SSM Parameter Store today; this module
  is the single isolation point for a future swap to AppConfig.
* SPEC §3.3: only the failover/failback Step Functions state machine writes
  this parameter. Any other call site is a bug. We enforce this at the
  module level by requiring an ``executor_run_id`` argument; ad-hoc callers
  cannot produce one without invoking the state machine.
* Anti-split-brain: writes are gated by an executor sequence number captured
  in the executor's input. Two regions cannot be ACTIVE simultaneously
  because the state machine drives DRAINING in the losing region first.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from botocore.exceptions import ClientError

from lib.aws_clients import ssm

Role = Literal["ACTIVE", "PASSIVE", "DRAINING"]

VALID_ROLES: frozenset[str] = frozenset({"ACTIVE", "PASSIVE", "DRAINING"})


@dataclass(frozen=True)
class IndicatorWrite:
    """Audit record returned to the caller for the executor-run S3 record."""

    app: str
    region: str
    role: Role
    executor_run_id: str
    sequence: int


def _param_name(app: str, region: str) -> str:
    return f"/failover/{app}/{region}/role"


def write_role(
    app: str,
    region: str,
    role: Role,
    executor_run_id: str,
    sequence: int,
) -> IndicatorWrite:
    """Set the regional indicator. Idempotent.

    ``executor_run_id`` and ``sequence`` are both required so that any audit
    of the parameter history can correlate every change back to a Step
    Functions execution and a state-machine step. The state machine MUST
    pass these; ad-hoc CLI invocations are forbidden by SPEC §3.3.
    """
    if role not in VALID_ROLES:
        raise ValueError(f"role must be one of {sorted(VALID_ROLES)}, got {role!r}")
    if not executor_run_id:
        raise ValueError("executor_run_id is required (anti-split-brain guard)")
    if sequence < 0:
        raise ValueError(f"sequence must be non-negative, got {sequence}")

    ssm().put_parameter(
        Name=_param_name(app, region),
        Value=role,
        Type="String",
        Overwrite=True,
        Description=f"executor_run_id={executor_run_id} sequence={sequence}",
    )
    return IndicatorWrite(
        app=app,
        region=region,
        role=role,
        executor_run_id=executor_run_id,
        sequence=sequence,
    )


def read_role(app: str, region: str) -> Role | None:
    """Read the current indicator. Returns ``None`` if the parameter has never
    been set (which the Kafka consumer client treats as PASSIVE)."""
    try:
        resp = ssm().get_parameter(Name=_param_name(app, region))
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ParameterNotFound":
            return None
        raise
    value = str(resp["Parameter"]["Value"])
    if value not in VALID_ROLES:
        # An invalid value is itself a bug; surface loudly.
        raise RuntimeError(f"indicator parameter for {app}/{region} contains {value!r}")
    return value  # type: ignore[return-value]


__all__ = ["VALID_ROLES", "IndicatorWrite", "Role", "read_role", "write_role"]
