# Scenario 12 — Split-brain attempt

**Audience:** Engineers + SREs.
**Summary:** Two executor runs concurrently try to set both regions to ACTIVE.

## Setup

Profile: `profiles/test-app.yaml` defaults (auto_failover=false unless
otherwise noted; tier1_quorum=2; dwell_minutes=5; hysteresis_minutes=3).

Initial state: `make harness-up` complete; both regions GREEN; primary
indicator ACTIVE; secondary indicator unset.

## Sequence of events

| t (min) | Layer | Event |
|---|---|---|
| 0 | Test driver | Inject the scenario condition (see `tests/chaos/test_scenario_12_split_brain_attempt.py`). |
| 1 | Signal Collector | Emits the affected signal value to CW. |
| 1+ | Decision Engine | Evaluates the rule per §4.2. |

## Signal state at each tick

(See `docs/decision-engine.md` §2 for signal definitions.)

## Decision evaluation

The rule from `docs/decision-engine.md` §1 fires (or does not fire) based on
which gates are held. The expected outcome for this scenario:

> **indicator_updater rejects writes with stale or out-of-sequence executor_run_id+sequence; only one region ends ACTIVE; the loser ends DRAINING then PASSIVE.**

## Operator actions

For non-mutating scenarios (1, 2, 3, 5, 13, 14): none. SRE on-call sees
SNS alerts but does not act.

For mutating scenarios with manual gates (4, 8, 10): see
[`runbooks/RUNBOOK-manual-failover.md`](../../runbooks/RUNBOOK-manual-failover.md)
and [`runbooks/RUNBOOK-aurora-promotion.md`](../../runbooks/RUNBOOK-aurora-promotion.md).

## Final outcome

indicator_updater rejects writes with stale or out-of-sequence executor_run_id+sequence; only one region ends ACTIVE; the loser ends DRAINING then PASSIVE.

## What this proves

Anti-split-brain guard works; two regions cannot be ACTIVE simultaneously.

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
