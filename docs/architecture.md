# Architecture

**Audience:** Engineers building or operating the orchestrator.

This document expands every box in [`SPEC.md`](../SPEC.md) §3 with the
component boundaries, where state lives, and the contracts between modules.

## 1. Layout per region

Both regions are mirrored. The components below exist in both `us-east-1`
and `us-east-2`.

```mermaid
flowchart LR
  subgraph Region [Region us-east-1 OR us-east-2]
    direction LR
    EB[EventBridge\n1-min schedule] --> SC[Signal Collector\nLambda]
    EB --> DE[Decision Engine\nLambda]
    SC -->|put_metric_data| CW[CloudWatch\nFailover/{app}/Signals]
    SC -->|put_object| S3A[(S3 Audit\nObservations)]
    DE -->|get_metric_data| CW
    DE -->|put_metric_data| CWAlarm[(PrimaryHealthControl\nMetric)]
    DE -->|put_parameter| SSM[(SSM Parameter Store\n/failover/{app}/{region}/decision)]
    DE -->|publish| SNS[(SNS Account-level Topic)]
    SF[Step Functions\nfailover/failback] --> Lambdas[Lambda task handlers]
    Lambdas --> SSMRole[(SSM\n/failover/{app}/{region}/role)]
    Lambdas --> CWAlarm
    SyntheticsCanary[CW Synthetics\nProbes opposite region] --> CW
  end
  CWAlarm --> R53Alarm[CW Alarm]
  R53Alarm --> R53HC[R53 Health Check]
  R53HC --> R53[Route 53 Failover Record]
```

## 2. Cross-region coordination

Per SPEC §3.2, the orchestrator does NOT use DynamoDB or any private
cross-region channel. Coordination is via:

- **Per-region SSM** for runtime state. Each region writes its own
  `/failover/{app}/{region}/{decision,role,in_flight}` parameters.
- **S3 with CRR** for the profile bucket and audit bucket. CRR carries
  the latest profile from primary to secondary so the secondary's Decision
  Engine reads the same configuration even when primary is down. (Profile
  delivery is pluggable: see [`profile-delivery-modes.md`](profile-delivery-modes.md)
  for the env-var alternative when runtime S3 reads aren't acceptable.)
- **SNS account-level topics** in each region with cross-region subscribers
  for operator alerting.
- **CloudWatch metrics** as the R53 control surface. `Failover/{app}/PrimaryHealthControl`
  is emitted by `decision_engine` and `executor_flip_r53_metric`. A
  CloudWatch alarm watches it; an R53 health check is bound to the alarm.
  This isolates Lambda from R53 API errors.

## 3. The regional indicator

`/failover/{app}/{region}/role` ∈ {`ACTIVE`, `PASSIVE`, `DRAINING`}. The
application's Kafka consumer polls this every 15 seconds and gates polling
on `role == ACTIVE`. The contract — including last-known-good caching and
fail-safe-to-PASSIVE on SSM error after 2 min — is documented in
`docs/decision-engine.md` and exercised by the synthetic ECS app in the
test harness.

The parameter is **only ever written by the Step Functions state machine**,
gated by the executor's sequence number. Two regions cannot be simultaneously
ACTIVE because the state machine drives DRAINING in the losing region first.

## 4. Why Step Functions

Three properties of the workflow disqualify simpler alternatives:

- Pause indefinitely for manual Aurora approval (Lambda 15-min cap rules
  out a single Lambda).
- Idempotent re-entry on Lambda crash mid-flight (SSM-state-machine custom
  logic re-implements what Step Functions gives us natively).
- Audit trail of every transition with retained execution history.

`waitForTaskToken` is used for the Aurora approval gate; `Retry`/`Catch`
declaratively for transient AWS errors; `Wait` states for drain/quiesce/R53
propagation windows. Standard workflow only — Express does not support
`waitForTaskToken` cleanly.

## 5. Lambda boundaries

| Lambda | Trigger | Purpose |
|---|---|---|
| `signal_collector` | EventBridge 1m | Tier 1/2/3 signals → CW metrics + S3 audit |
| `decision_engine` | EventBridge 1m | Apply §4.2 rule → SSM/SNS/control metric |
| `manual_trigger` | Operator (CLI) | Start failover/failback Step Functions execution |
| `approval_callback` | Operator (CLI) | `SendTaskSuccess`/`SendTaskFailure` on Aurora gate |
| `indicator_updater` | Step Functions | Write DRAINING/ACTIVE/PASSIVE with sequence guard |
| `executor_precheck` | Step Functions | PRECHECK_SECONDARY / PRECHECK_PRIMARY |
| `executor_notify` | Step Functions | Publish one SNS event by name |
| `executor_flip_r53_metric` | Step Functions | Emit `PrimaryHealthControl` metric value |
| `executor_aurora_confirm` | Step Functions (looped) | Poll DescribeDBClusters for writer flip |
| `executor_postcheck` | Step Functions | Confirm new primary healthy |

Each Lambda follows CLAUDE.md §3.2: `handler.py` (entrypoint), `logic.py`
(pure Python, unit-testable), `aws.py` (boto3 calls only).

## 6. Boundaries we will not redesign

These are non-negotiable per CLAUDE.md §2:

- No Aurora auto-promotion. The orchestrator confirms; it never initiates.
- No auto-failback.
- No DynamoDB / AppConfig / R53 ARC at runtime.
- No internet egress from any Lambda.
- No IAM `*` actions; every action enumerated.
- All deploys manual local `terraform apply` with profile `tbed`. No CI to AWS.

_Last reviewed: 2026-04-27._
