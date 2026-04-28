"""Aurora confirm Lambda — polled by the AURORA_CONFIRM Step Functions state
between Wait iterations. Returns ``confirmed: true`` to advance, false to
loop, raises to abort."""

from __future__ import annotations

from typing import Any

from lambdas.executor_aurora_confirm.logic import evaluate
from lambdas.signal_collector.aws import aurora_replica_lag_seconds, aurora_writer_in
from lib.structured_logger import get_logger

log = get_logger(__name__)


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    del context
    target_region = str(event["target_region"])
    global_cluster_id = str(event["global_cluster_id"])
    iteration = int(event.get("iteration", 0)) + 1

    result = evaluate(
        target_region=target_region,
        writer_region=lambda: aurora_writer_in(global_cluster_id),
        replica_lag_seconds=lambda: aurora_replica_lag_seconds(global_cluster_id),
    )
    log.info(
        "aurora_writer_confirmed" if result.confirmed else "state_machine_step_entered",
        extra={
            "step": "AURORA_CONFIRM",
            "iteration": iteration,
            "writer_region": result.writer_region,
            "replica_lag_seconds": result.replica_lag_seconds,
            "reason": result.reason,
        },
    )
    return {
        **event,
        "iteration": iteration,
        "confirmed": result.confirmed,
        "writer_region": result.writer_region,
        "replica_lag_seconds": result.replica_lag_seconds,
        "reason": result.reason,
    }
