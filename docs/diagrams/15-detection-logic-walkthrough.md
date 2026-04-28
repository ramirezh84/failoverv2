# Diagram 15 — Detection Logic Walkthrough

**Audience:** Customer engineering, SRE, anyone asking "but how does it
know it's a real outage and not just my deploy?"

This is the missing visual: how a raw signal becomes (or doesn't become)
a failover, with **specific scenarios traced through each filter**.

---

## Part A — The signal-to-decision pipeline

Every minute, both regions independently:

1. Collect signals from three tiers of sources
2. Run them through four sequential gates
3. Emit a verdict (`GREEN`, `WATCHING`, `AUTHORIZED_*`, or `EXECUTE`)

```mermaid
flowchart TD
  classDef trigger fill:#fee,stroke:#c00,color:#000
  classDef nontrig fill:#eef,stroke:#06c,color:#000
  classDef info fill:#fff8e0,stroke:#cc8400,color:#000
  classDef gate fill:#fff,stroke:#333,stroke-width:2px,color:#000
  classDef green fill:#d4edda,stroke:#155724,color:#000
  classDef yellow fill:#fff3cd,stroke:#856404,color:#000
  classDef red fill:#f8d7da,stroke:#721c24,color:#000

  subgraph Sources["Inputs (every minute, both regions)"]
    direction TB
    T1["TIER 1 — can trigger<br/>• outer_nlb_unhealthy<br/>• cross_region_canary_fail<br/>• aws_health_open<br/>• vpc_endpoint_errors"]:::trigger
    T2["TIER 2 — gates safety only<br/>• aurora_writer_location<br/>• aurora_replica_lag<br/>• elasticache_replication"]:::nontrig
    T3["TIER 3 — informational<br/>• alb_unhealthy<br/>• api_gw_5xx"]:::info
  end

  T1 --> G1
  T2 -.gates safety check.-> G5
  T3 -.never triggers.-> Discarded[/"Logged + visible on dashboards<br/>NEVER drives a decision"/]:::info

  G1{"GATE 1 — QUORUM<br/>≥2 of N Tier 1 red?"}:::gate
  G1 -- "no (only 1 red)" --> V_Green1["GREEN<br/>or WATCHING_quorum_not_met"]:::green
  G1 -- "yes" --> G2

  G2{"GATE 2 — DWELL<br/>red ≥ 5 min consecutively?"}:::gate
  G2 -- "no (transient)" --> V_Green2["WATCHING_dwell_not_held"]:::green
  G2 -- "yes" --> G3

  G3{"GATE 3 — HYSTERESIS<br/>≥3 min since last decision change?"}:::gate
  G3 -- "no (still in cooldown)" --> V_Yellow1["WATCHING_hysteresis_blocked"]:::yellow
  G3 -- "yes" --> G4

  G4{"GATE 4 — AUTO_FAILOVER FLAG<br/>profile.auto_failover == true?"}:::gate
  G4 -- "no (default first 30 days)" --> V_Yellow2["FAILOVER_AUTHORIZED_BUT_NOT_AUTO<br/>SNS HIGH — operator decides"]:::yellow
  G4 -- "yes" --> G5

  G5{"GATE 5 — SAFETY<br/>secondary warm + Tier 2 ready?"}:::gate
  G5 -- "no (Aurora behind, secondary ECS empty, etc.)" --> V_Red1["FAILOVER_AUTHORIZED_BUT_UNSAFE<br/>SNS CRITICAL — operator must triage"]:::red
  G5 -- "yes" --> V_Red2["FAILOVER_AUTHORIZED<br/>control_metric=0.0 → R53 health check trips → DNS flips<br/>Step Functions failover starts"]:::red
```

**Key principle (read top to bottom):** each gate is **deliberately
suspicious of its inputs**. The gates aren't AND-ed in parallel — they're
chained, and each one is designed to **discard** the next class of false
positive. By the time a signal reaches the bottom, four independent
heuristics have agreed it's real.

---

## Part B — Scenario-by-scenario walkthrough

The same flowchart, with **specific incident types annotated** so you can
see which gate kills which kind of false positive:

```mermaid
flowchart TD
  classDef nonimpact fill:#d4edda,stroke:#155724,color:#000
  classDef impact fill:#f8d7da,stroke:#721c24,color:#000
  classDef gate fill:#fff,stroke:#333,stroke-width:2px,color:#000

  Inc["Incident occurs in primary region"] --> SC[Signal Collector reads CW + AWS APIs<br/>1-minute cadence]
  SC --> G1

  G1{"GATE 1 — QUORUM<br/>≥2 distinct Tier 1 red?"}:::gate
  G1 -- "STOPPED HERE: deploy 503 blip<br/>only Tier 3 alb_unhealthy red,<br/>Tier 1 untouched" --> O1["Verdict: GREEN<br/>NO failover"]:::nonimpact
  G1 -- "STOPPED HERE: ALB unhealthy only<br/>Tier 3 only, NLB sees healthy targets at LB level" --> O1
  G1 -- "STOPPED HERE: API GW 5xx storm<br/>Tier 3 only" --> O1
  G1 -- "STOPPED HERE: single-AZ outage<br/>NLB cross-zone keeps overall healthy_count ≥1<br/>only one signal red, not quorum" --> O1
  G1 -- "STOPPED HERE: app cant reach Aurora<br/>Tier 2 informational, never triggers" --> O1
  G1 -- "STOPPED HERE: VPC endpoint hiccup<br/>1 of 4 Tier 1, doesn't make quorum" --> O1
  G1 -- "passes" --> G2

  G2{"GATE 2 — DWELL<br/>red sustained ≥ 5 min?"}:::gate
  G2 -- "STOPPED HERE: 3-minute deploy blip<br/>2 Tier 1 signals briefly red, recovered before dwell" --> O2["Verdict: WATCHING<br/>NO failover"]:::nonimpact
  G2 -- "STOPPED HERE: transient AZ flap<br/>red for 90s, healed before dwell" --> O2
  G2 -- "passes" --> G3

  G3{"GATE 3 — HYSTERESIS<br/>≥3 min since last decision?"}:::gate
  G3 -- "STOPPED HERE: oscillating signal<br/>just changed verdict in last 90s, hold steady" --> O3["Verdict: WATCHING<br/>NO failover (this tick)"]:::nonimpact
  G3 -- "passes" --> G4

  G4{"GATE 4 — AUTO_FAILOVER FLAG<br/>operator opted in?"}:::gate
  G4 -- "STOPPED HERE: first 30 days per app<br/>auto_failover defaults to false<br/>operator runs `failoverctl failover` after triage" --> O4["Verdict: AUTHORIZED_BUT_NOT_AUTO<br/>SNS HIGH alert, operator decides"]:::impact
  G4 -- "passes (auto on, mature)" --> G5

  G5{"GATE 5 — SAFETY<br/>secondary actually ready?"}:::gate
  G5 -- "STOPPED HERE: Aurora replica behind<br/>RPO budget exceeded, would lose data" --> O5["Verdict: AUTHORIZED_BUT_UNSAFE<br/>SNS CRITICAL — operator triage"]:::impact
  G5 -- "STOPPED HERE: secondary ECS at 0 tasks<br/>warm standby cold for some reason" --> O5
  G5 -- "passes (warm + tier 2 ok)" --> Trigger

  Trigger["Verdict: FAILOVER_AUTHORIZED<br/>publish PrimaryHealthControl=0.0<br/>R53 health check trips within 90s<br/>SFN failover execution starts"]:::impact

  subgraph Examples_that_reach_here["Incident types that REACH the trigger"]
    Trigger --> Outage1["Full region outage:<br/>NLB unhealthy + canary failing + AWS Health open + VPCE errors<br/>= 4 of 4 Tier 1 red, sustained ≥5 min"]
    Trigger --> Outage2["Sustained NLB + cross-region canary failure:<br/>≥2 of 4 Tier 1 red, sustained, secondary healthy"]
    Trigger --> Outage3["Region-level data plane impairment:<br/>VPCE errors + canary failing across multiple boundaries"]
  end
```

**How to read this:** start at the top, follow the path your specific
incident takes. Wherever the chart says "STOPPED HERE: <your incident>",
that's the gate that prevents an over-trigger. Eight kinds of non-impacting
issues are filtered out before any action; only sustained, multi-signal,
infrastructure-level failures with a healthy secondary reach the bottom.

---

## Part C — Verdict matrix (every scenario, what gate it hits)

The 14 SPEC scenarios mapped to the gate that determines their outcome:

| # | Scenario | Tier(s) red | Stopped at | Verdict | Operator action |
|---|---|---|---|---|---|
| 01 | Deployment 503 blip | Tier 3 only | Quorum (Tier 1 untouched) | GREEN | None |
| 02 | ALB unhealthy only | Tier 3 only | Quorum | GREEN | None |
| 03 | Single-AZ outage | 1 Tier 1 | Quorum (only 1 red) | GREEN | In-region recovery |
| 04 | Full region outage | 4 Tier 1 | Reaches bottom | AUTHORIZED → executes | Approve Aurora |
| 05 | API GW 5xx storm | Tier 3 only | Quorum | GREEN | None |
| 06 | App can't reach Aurora | Tier 2 only | Tier 2 doesn't trigger | GREEN | SRE alerted, separate path |
| 07 | Operator dry-run | n/a | Bypasses gates entirely (operator-initiated) | EXECUTE (dry) | Validate |
| 08 | Manual failover w/ Aurora gate | n/a (operator) | Bypasses gates | AUTHORIZED → paused at gate | Approve Aurora |
| 09 | Aurora confirmation timeout | n/a | Aurora gate timeout | FAIL state | Triage Aurora |
| 10 | Failback | n/a (operator) | Bypasses gates | EXECUTE | Approve Aurora |
| 11 | Mid-failover Lambda crash | n/a | SFN Catch+Retry handles | EXECUTE | None (auto-recovered) |
| 12 | Split-brain attempt | n/a | SFN execution-name uniqueness | First wins, second rejected | None |
| 13 | Profile change mid-incident | depends | New profile picked up next tick | Same as new profile says | Confirm profile applied |
| 14 | Canary self-failure | 1 Tier 1 (canary) | Quorum (only 1 red, ignored after canary recovers) | GREEN | Canary infra fix |

**The split:** scenarios 1, 2, 3, 5, 6, 14 are exactly the kinds of
"non-impacting issues" the orchestrator must NOT act on. Notice every
single one is killed at **Gate 1 (Quorum)** — the first filter in the
chain, costing nothing to evaluate.

Scenario 4 is the canonical "real outage" — only scenario where everything
aligns to actually trigger.

Scenarios 7-12 are operator/process scenarios (manual triggers, idempotency,
recovery) — they bypass the detection gates because the operator has already
made the decision.

---

## Part D — Why this design

The four gates aren't arbitrary. Each one targets a specific class of
false positive that operators have learned to fear:

| Gate | Targets which historical false-positive class |
|---|---|
| Quorum (≥2 Tier 1) | Single-source noise — one canary, one VPCE error, one Health event scoped to a different service |
| Dwell (≥5 min) | Deploy-induced blips, transient retries, intra-AZ failover events |
| Hysteresis (≥3 min) | Signal flapping causing decision oscillation between WATCHING and AUTHORIZED |
| Auto-failover flag | New apps without enough operating data for safe automation |
| Safety (Tier 2 + warm) | "Trigger but lose data" — failover that would corrupt or lose Aurora writes |

This is **failover-cost-aware design**: a false-positive failover costs
real money (cross-region traffic, Aurora promotion downtime, operator hours
to fail back). The asymmetry between false-positive cost (high) and
false-negative cost (handled by the on-call rotation seeing the alarm and
triggering manually) drives the bias toward "miss rather than over-trip."

Profile owners can tune the gates per-app:

- App with high noise floor → raise `tier1_quorum` to 3
- Slow-recovering app → raise `dwell_minutes` to 10
- Stable, trusted automation → flip `auto_failover: true`

See [`docs/decision-engine.md`](../decision-engine.md) §4 for the full
tunable list and [`docs/profile-reference.md`](../profile-reference.md)
for syntax.

---

_Last reviewed: 2026-04-28._
