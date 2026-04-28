"""Aurora confirmation logic.

After the operator promotes the Aurora secondary cluster to writer (manually
in the console/CLI), the executor calls this Lambda once per Step Functions
poll iteration to check whether the writer has flipped to ``target_region``
and replication lag is reasonable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class AuroraConfirmResult:
    confirmed: bool
    writer_region: str | None
    replica_lag_seconds: float
    reason: str


def evaluate(
    *,
    target_region: str,
    writer_region: Callable[[], str | None],
    replica_lag_seconds: Callable[[], float],
    max_acceptable_lag: float = 5.0,
) -> AuroraConfirmResult:
    current = writer_region()
    if current is None:
        return AuroraConfirmResult(
            confirmed=False,
            writer_region=None,
            replica_lag_seconds=0.0,
            reason="no_writer_yet",
        )
    if current != target_region:
        return AuroraConfirmResult(
            confirmed=False,
            writer_region=current,
            replica_lag_seconds=0.0,
            reason=f"writer_in_{current}_not_{target_region}",
        )
    lag = replica_lag_seconds()
    if lag > max_acceptable_lag:
        return AuroraConfirmResult(
            confirmed=False,
            writer_region=current,
            replica_lag_seconds=lag,
            reason=f"replica_lag_{lag:.2f}s_above_threshold",
        )
    return AuroraConfirmResult(
        confirmed=True,
        writer_region=current,
        replica_lag_seconds=lag,
        reason="confirmed",
    )


__all__ = ["AuroraConfirmResult", "evaluate"]
