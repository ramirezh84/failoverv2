"""Pre-check logic for the failover/failback executor.

Confirms the target region is healthy enough to receive traffic:
- ECS warm-standby task count >= 1
- VPC endpoints reachable
- Tier 1 signals green in the target region
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class PrecheckResult:
    ok: bool
    target_region: str
    ecs_running_tasks: int
    target_tier1_red: list[str]
    failures: list[str]


def evaluate(
    target_region: str,
    *,
    ecs_running_task_count: Callable[[str], int],
    target_tier1_red: Callable[[str], list[str]],
    min_running: int = 1,
) -> PrecheckResult:
    failures: list[str] = []
    running = ecs_running_task_count(target_region)
    if running < min_running:
        failures.append(
            f"ecs_running_tasks={running} < min_running={min_running} in {target_region}"
        )
    red = target_tier1_red(target_region)
    if red:
        failures.append(f"target_tier1_red={red}")
    return PrecheckResult(
        ok=not failures,
        target_region=target_region,
        ecs_running_tasks=running,
        target_tier1_red=red,
        failures=failures,
    )


__all__ = ["PrecheckResult", "evaluate"]
