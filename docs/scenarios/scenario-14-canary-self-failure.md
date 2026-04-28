# Scenario 14 — Canary self-failure

**Audience:** Engineers + SREs.
**Summary:** The Synthetics canary itself crashes (canary infra, not target).

## Setup

Profile: `profiles/test-app.yaml` defaults (auto_failover=false unless
otherwise noted; tier1_quorum=2; dwell_minutes=5; hysteresis_minutes=3).

Initial state: `make harness-up` complete; both regions GREEN; primary
indicator ACTIVE; secondary indicator unset.

## Sequence of events

| t (min) | Layer | Event |
|---|---|---|
| 0 | Test driver | Inject the scenario condition (see `tests/chaos/test_scenario_14_canary_self_failure.py`). |
| 1 | Signal Collector | Emits the affected signal value to CW. |
| 1+ | Decision Engine | Evaluates the rule per §4.2. |

## Signal state at each tick

(See `docs/decision-engine.md` §2 for signal definitions.)

## Decision evaluation

The rule from `docs/decision-engine.md` §1 fires (or does not fire) based on
which gates are held. The expected outcome for this scenario:

> **cross_region_canary_fail goes red. Quorum = 1 < 2. No failover. SNS canary degraded alert.**

## Operator actions

For non-mutating scenarios (1, 2, 3, 5, 13, 14): none. SRE on-call sees
SNS alerts but does not act.

For mutating scenarios with manual gates (4, 8, 10): see
[`runbooks/RUNBOOK-manual-failover.md`](../../runbooks/RUNBOOK-manual-failover.md)
and [`runbooks/RUNBOOK-aurora-promotion.md`](../../runbooks/RUNBOOK-aurora-promotion.md).

## Final outcome

cross_region_canary_fail goes red. Quorum = 1 < 2. No failover. SNS canary degraded alert.

## What this proves

A single-signal failure does not trigger; canary infra is not a single point of failure for the rule.

## Sequence diagram

```mermaid
sequenceDiagram
  participant Test as Test driver
  participant SC as Signal Collector
  participant DE as Decision Engine
  participant SF as Step Functions
  participant Operator
  participant Sec as Secondary region

  Test->>SC: inject scenario condition
  SC->>DE: signal red (via CW)
  DE->>DE: evaluate §4.2
  alt scenario triggers
    DE->>SF: start failover
    SF->>Operator: SNS aurora_gate_paused
    Operator->>SF: SendTaskSuccess
    SF->>Sec: PROMOTE_SECONDARY_INDICATOR ACTIVE
  else scenario does NOT trigger
    DE->>DE: state=GREEN/WATCHING
  end
```

_Last reviewed: 2026-04-27._
