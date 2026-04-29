# Decision Engine

**Audience:** Engineers debugging false positives / negatives.

This document is the exhaustive reference for what makes the orchestrator
authorize a failover. Every signal, every threshold, every gate.

## 1. The rule (SPEC §4.2)

```
FAILOVER_AUTHORIZED = (
    count(Tier1 red signals) >= profile.tier1_quorum     # default 2 of N
    AND duration(red continuously) >= profile.dwell_minutes   # default 5
    AND time_since_last_decision >= profile.hysteresis_minutes  # default 3
    AND profile.auto_failover == true
)

FAILOVER_SAFE = secondary_warm_standby_healthy AND tier2_ready

EXECUTE_AUTO_FAILOVER = FAILOVER_AUTHORIZED AND FAILOVER_SAFE
```

`auto_failover=false` (the default for first 30 days per SPEC §4.3) means
the rule emits a HIGH-severity SNS event but does not trigger the
executor. Operators decide.

## 2. Signal taxonomy

### Tier 1 (the only tier that can *trigger*)

| Signal | Source | Red threshold |
|---|---|---|
| `outer_nlb_unhealthy` | CW `AWS/NetworkELB UnHealthyHostCount` | All targets unhealthy ≥ dwell |
| `cross_region_canary_fail` | CW Synthetics in opposite region | Failure rate ≥ `canary_failure_rate_pct` (default 80%) |
| `aws_health_open` | AWS Health API (regional VPCE; optional) | Open issue affecting region's services. **Requires Business+ Support tier AND a Health VPCE.** If `ENDPOINT_HEALTH` is unset, signal_collector treats this as permanently green and quorum operates over the remaining Tier 1 signals. |
| `vpc_endpoint_errors` | CW `AWS/PrivateLinkEndpoints EndpointFailureCount` | >0 errors in dwell window |

### Tier 2 (gates *whether* failover is safe; cannot trigger)

| Signal | Source |
|---|---|
| `aurora_writer_location` | RDS `DescribeGlobalClusters` |
| `aurora_replica_lag_high` | CW `AWS/RDS AuroraGlobalDBReplicationLag` |
| `elasticache_replication` | ElastiCache API + CW (when profile opts in) |

### Tier 3 (informational; never triggers)

| Signal | Source |
|---|---|
| `alb_unhealthy` | CW `AWS/ApplicationELB UnHealthyHostCount` |
| `api_gw_5xx` | CW `AWS/ApiGateway 5XXError` (when profile.api_gateway=true) |

## 3. The four gates

### 3.1 Quorum (`tier1_quorum`)

Default 2. Requires two distinct Tier 1 signals to be red simultaneously.
This is what makes a transient single-signal blip (e.g. one canary failure,
or one VPC endpoint hiccup) NOT trigger anything.

Tunable per app via `profile.signals.tier1_quorum`. Allowed range: 1–10.

### 3.2 Dwell (`dwell_minutes`)

Default 5 minutes. The quorum must be red for `dwell_minutes` of consecutive
1-minute samples. This is what makes a 3-minute deployment blip NOT trigger.

Computed from CW metric `Failover/{app}/Signals/tier1_quorum_red`, which the
Decision Engine emits each minute as a derived value (count of red Tier 1
signals at the current minute).

### 3.3 Hysteresis (`hysteresis_minutes`)

Default 3 minutes. The minimum time between successive decision changes.
Prevents oscillation when signals are flapping.

Implemented by reading the latest decision's timestamp from SSM and
short-circuiting if the gap is too small.

### 3.4 `auto_failover` flag

Default `false` (alerts-only) for the first 30 days of any new app, then
opt-in. CLAUDE.md §2 #8 + SPEC §4.3.

## 4. Worked examples

### 4.1 Deployment blip — NO failover

App deploys, `/actuator/health` returns 503 for 3 minutes. Tier 3 alarm
fires (`alb_unhealthy`). Tier 1 stays green (NLB targets still up;
canary still passing). `count(Tier1 red) = 0 < 2`. Decision: GREEN.

### 4.2 Single AZ outage — NO failover

`us-east-1a` becomes unhealthy. NLB targets in `us-east-1b` and `c` keep
the target group at `UnHealthyHostCount = 0`. Canary still passes.
`outer_nlb_unhealthy` stays green. `count(Tier1 red) = 0`. Decision: GREEN.

### 4.3 Region outage — failover

Primary NLB targets all unhealthy + canary failing + AWS Health event open.
`count(Tier1 red) = 3 ≥ 2`. After 5 minutes of continuous red, dwell holds.
If `auto_failover=true` and secondary is ready (Tier 2 + warm standby >0),
EXECUTE_AUTO_FAILOVER. Otherwise CRITICAL SNS, operator decides.

## 5. Failure modes the rule catches

- **Single signal flapping** — quorum gate.
- **Short-lived event** — dwell gate.
- **Oscillation** — hysteresis gate.
- **Operator wants alerts only** — `auto_failover=false`.
- **Secondary not ready** — `FAILOVER_SAFE` check; emits `failover_failed`
  SNS but does NOT initiate the state machine.

## 6. False positive / negative debugging

If a failover fires when it shouldn't:
1. Pull `tier1_quorum_red` metric history for the dwell window.
2. Decode the latest `DecisionRecord` from `s3://<audit-bucket>/<app>/<region>/decisions/`.
3. Check `tier1_red_signals` — which signals were red?
4. Cross-reference each signal's underlying CW metric.

If a failover should have fired and didn't:
1. Check `auto_failover` in profile.
2. Check Decision Engine CloudWatch logs for `decision_evaluated` events
   in the suspect window.
3. Check signal collector emit history.

_Last reviewed: 2026-04-27._
