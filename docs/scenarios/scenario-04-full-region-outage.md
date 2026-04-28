# Scenario 04 — Full primary region outage

**Audience:** Engineers + SREs.
**Summary:** All NLB targets unhealthy + canary failing + AWS Health event open in primary.

## Setup

Profile: `profiles/test-app.yaml` defaults (auto_failover=false unless
otherwise noted; tier1_quorum=2; dwell_minutes=5; hysteresis_minutes=3).

Initial state: `make harness-up` complete; both regions GREEN; primary
indicator ACTIVE; secondary indicator unset.

## Sequence of events

| t (min) | Layer | Event |
|---|---|---|
| 0 | Test driver | Inject the scenario condition (see `tests/chaos/test_scenario_04_full_region_outage.py`). |
| 1 | Signal Collector | Emits the affected signal value to CW. |
| 1+ | Decision Engine | Evaluates the rule per §4.2. |

## Signal state at each tick

(See `docs/decision-engine.md` §2 for signal definitions.)

## Decision evaluation

The rule from `docs/decision-engine.md` §1 fires (or does not fire) based on
which gates are held. The expected outcome for this scenario:

> **FAILOVER_AUTHORIZED; Step Functions runs DNS-first failover; Aurora gate pauses; operator approves; STABLE_SECONDARY; failback in cleanup.**

## Operator actions

For non-mutating scenarios (1, 2, 3, 5, 13, 14): none. SRE on-call sees
SNS alerts but does not act.

For mutating scenarios with manual gates (4, 8, 10): see
[`runbooks/RUNBOOK-manual-failover.md`](../../runbooks/RUNBOOK-manual-failover.md)
and [`runbooks/RUNBOOK-aurora-promotion.md`](../../runbooks/RUNBOOK-aurora-promotion.md).

## Final outcome

FAILOVER_AUTHORIZED; Step Functions runs DNS-first failover; Aurora gate pauses; operator approves; STABLE_SECONDARY; failback in cleanup.

## What this proves

End-to-end automatic failover with manual Aurora gate, full audit trail.

## Sequence diagram

```mermaid
sequenceDiagram
  participant Test
  participant SC as SignalCollector
  participant DE as DecisionEngine
  participant SF as StepFunctions
  participant Operator
  participant Sec

  Test->>SC: inject scenario condition
  SC->>DE: signal red via CW
  DE->>DE: evaluate rule
  alt scenario triggers
    DE->>SF: start failover
    SF->>Operator: SNS aurora_gate_paused
    Operator->>SF: SendTaskSuccess
    SF->>Sec: PROMOTE secondary ACTIVE
  else scenario does NOT trigger
    DE->>DE: state GREEN or WATCHING
  end
```

_Last reviewed: 2026-04-27._
