from __future__ import annotations

from lambdas.executor_precheck.logic import evaluate


def test_ok_when_warm_standby_healthy() -> None:
    r = evaluate(
        "us-east-2",
        ecs_running_task_count=lambda _: 2,
        target_tier1_red=lambda _: [],
    )
    assert r.ok is True
    assert r.ecs_running_tasks == 2


def test_fails_when_no_tasks_running() -> None:
    r = evaluate(
        "us-east-2",
        ecs_running_task_count=lambda _: 0,
        target_tier1_red=lambda _: [],
    )
    assert r.ok is False
    assert any("ecs_running_tasks=0" in f for f in r.failures)


def test_fails_when_target_tier1_red() -> None:
    r = evaluate(
        "us-east-2",
        ecs_running_task_count=lambda _: 1,
        target_tier1_red=lambda _: ["nlb_unhealthy"],
    )
    assert r.ok is False
    assert any("target_tier1_red" in f for f in r.failures)
