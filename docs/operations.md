# Operations

**Audience:** SRE on-call.

This is your day-to-day reference. For incident-specific procedures see
[`../runbooks/`](../runbooks/).

## 1. Where things live

| What | Where |
|---|---|
| Live decision state | SSM `/failover/{app}/{region}/decision` |
| Regional indicator | SSM `/failover/{app}/{region}/role` |
| In-flight execution id | SSM `/failover/{app}/{region}/in_flight` |
| Decision history | `s3://<audit-bucket>/<app>/<region>/decisions/` |
| Observation snapshots | `s3://<audit-bucket>/<app>/<region>/observations/` |
| Executor run records | `s3://<audit-bucket>/<app>/<region>/executor-runs/` |
| Step Functions execution history | AWS console + GetExecutionHistory API |
| SNS events | account-level topic `failover-events` per region |
| Lambda logs | `/aws/lambda/{app}-{lambda}-use{1,2}` |

## 2. Reading the dashboard

(Dashboard is created by `terraform/modules/orchestrator-runtime` and
named `failover-{app}`.)

Widgets, in reading order:

1. **Tier 1 signal status grid** — green/red for each signal in each
   region, last 24h. If anything is red here, look at the timestamp; if
   sustained, expect a `failover_authorized` SNS.
2. **Tier 2 data tier** — Aurora writer location, replica lag, ElastiCache
   replication state. Aurora writer should be in the region where R53 is
   sending traffic.
3. **Tier 3 app health** — informational only. ALB unhealthy and API GW
   5xx live here. These rarely call for action by themselves.
4. **Active region indicator** — value of the SSM `role` parameter per
   region. Should be exactly one ACTIVE; never two.
5. **Last 10 decisions** — pulled from S3 audit. Decision state +
   reason + which signals were red.
6. **Last failover/failback executions** — Step Functions execution list.
7. **PrimaryHealthControl metric and bound alarm state** — the R53
   control surface. Value=1.0 means primary is healthy; value=0.0 means
   tripped.
8. **Cross-region canary results** — Synthetics canary success rate.

## 3. Common operational tasks

### 3.1 Status check

```bash
export AWS_PROFILE=tbed
failoverctl status test-app
```

Returns SSM state + recent Step Functions executions as JSON.

### 3.2 Manual failover

```bash
failoverctl failover test-app --operator $USER
```

Returns the Step Functions execution ARN. Watch progress in the console
or via `failoverctl history test-app`.

### 3.3 Approve Aurora gate

When the executor pauses, an SNS message goes out with a task token. After
promoting Aurora secondary in the console (see `RUNBOOK-aurora-promotion.md`):

```bash
failoverctl approve test-app --task-token <token-from-sns> --reason "Aurora promoted via console"
```

### 3.4 Failback

```bash
failoverctl failback test-app --operator $USER
```

### 3.5 Dry run

```bash
failoverctl dryrun test-app --operator $USER
```

Runs the full state machine with `dry_run: true`. SNS subjects are prefixed
`[DRY-RUN]`. No SSM/R53/Aurora changes happen.

## 4. SNS event vocabulary

Subscribers filter by message attribute `event`. Allowed values
(SPEC §7 + CLAUDE.md §3.3):

```
failover_authorized   failover_initiated   failover_step_completed
failover_completed    failover_failed      failback_initiated
failback_completed    failback_failed      signal_red
signal_recovered      aurora_gate_paused
```

`severity` attribute: `INFO` | `HIGH` | `CRITICAL`. PagerDuty (or
equivalent) should fire on CRITICAL only.

## 5. Common diagnostic queries

### Decision Engine evaluation history (last hour)

```
fields @timestamp, state, reason, red_signals
| filter event = "decision_evaluated"
| sort @timestamp desc
| limit 60
```

### When did the last failover fire?

```
fields @timestamp, app_name, region, reason
| filter event = "failover_authorized"
| sort @timestamp desc
| limit 5
```

### Indicator transitions in the last 24h

```
fields @timestamp, role, region, executor_run_id, sequence
| filter event = "indicator_updated"
| sort @timestamp desc
| limit 50
```

## 6. When things go wrong

| Symptom | Where to look first | Runbook |
|---|---|---|
| Failover fires unexpectedly | `decision_evaluated` logs in the primary's `decision_engine` | [`RUNBOOK-stuck-state-machine.md`](../runbooks/RUNBOOK-stuck-state-machine.md) |
| Stuck Step Functions execution | Step Functions console + `failoverctl status` | [`RUNBOOK-stuck-state-machine.md`](../runbooks/RUNBOOK-stuck-state-machine.md) |
| Both regions show ACTIVE indicator | `indicator_updated` log timeline | [`RUNBOOK-split-brain-recovery.md`](../runbooks/RUNBOOK-split-brain-recovery.md) |
| Aurora writer in wrong region after promotion | `aurora_gate_*` logs + RDS console | [`RUNBOOK-aurora-promotion.md`](../runbooks/RUNBOOK-aurora-promotion.md) |
| App's Kafka consumer running in PASSIVE region | App's regional indicator client logs | App's repo |

_Last reviewed: 2026-04-27._
