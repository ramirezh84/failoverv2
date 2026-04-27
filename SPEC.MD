# Multi-Region Failover Orchestrator — Specification

**Status:** Ready to build
**Target consumers:** Critical ECS Fargate applications on the Domestic Deposits platform
**Build environment:** Claude Code
**Author:** Principal Engineer — Cloud Architecture & Strategy
**Last updated:** 2026-04-27 (rev 7 — two-tier Terraform split for fast iteration, validation framework with full observability assertions, stability = 3 consecutive full-suite passes)

---

## 1. Purpose

Build a **profile-driven, per-app, multi-region failover orchestrator** that fails over a critical ECS Fargate application from `us-east-1` to `us-east-2` (and back) **only when independent infrastructure and data-tier signals prove that moving traffic is safer than staying put**.

The framework is reused across many apps. Not every app has API Gateway, not every app has Aurora, not every app has ElastiCache. The behavior must be controlled entirely by a per-app YAML profile — no code changes between apps.

The framework must be rock-solid against a real region outage and **deliberately insensitive** to:
- Single-app deployments
- 3-minute response gaps
- Single-AZ events
- API Gateway transient 5xx
- Single-signal red flags

### 1.1 Build context

This first build is a **POC in the Principal Engineer's personal AWS account** (`tbed` AWS CLI profile), not in a JPMC account. The orchestrator framework is designed for eventual production deployment at JPMC, but the immediate deliverable is a working POC that exercises every code path against a representative test harness in the personal account.

**The POC must be a 100% topology mirror of the JPMC target environment.** Every component in the production path — outer NLB with TLS, private API Gateway, inner NLB, ALB, ECS Fargate, Aurora Global, VPC endpoints, cross-region canary, etc. — is present in the POC. The only POC-specific concessions are around credentials and process (self-signed TLS instead of internal CA, static AWS profile instead of federated SSO, single account instead of multi-account, manual local `terraform apply` instead of automated CD pipeline). Functional behavior is identical.

**Deployment model:** The Principal Engineer (or Claude Code on his behalf) runs `terraform apply` locally using AWS CLI profile `tbed`. There is no automated CD pipeline. CI on PRs runs code quality checks only (lint, types, tests, schema validation, `terraform validate`) so that broken code cannot land on `main`, but CI does not deploy anything. Automated deployment via GitHub OIDC + Actions is documented in §14 as a JPMC-port migration item — not part of the POC.

POC-specific simplifications versus the eventual JPMC production deployment are listed explicitly in §2.1. Everything not so marked applies to both POC and production.

---

## 2. Locked Constraints (do not redesign these)

1. **Topology is fixed:** `Outer NLB (routable subnet) → Private API Gateway → Inner NLB → ALB → ECS Fargate`. API Gateway is **optional per app** (profile flag); when absent the path is `Outer NLB → Inner NLB → ALB → ECS`.
2. **No Route 53 ARC.** Use standard Route 53 health-check-driven failover/weighted records.
3. **No DynamoDB (yet).** Coordination must work with SSM Parameter Store + S3 (CRR) + SNS only. Design must allow swapping the state layer to DynamoDB Global Tables later as an isolated change.
4. **No AppConfig (yet).** The regional indicator uses a **pull** mechanism via SSM Parameter Store. Design must allow swapping to AppConfig later as an isolated change.
5. **Lambda must be VPC-attached.** All AWS API calls leave Lambda via VPC endpoints. No internet egress from Lambda.
6. **No private cross-region connectivity.** Cross-region visibility is only via the publicly routable regional endpoints and via AWS service control planes (CloudWatch, SNS, S3, SSM).
7. **Aurora failover stays manual.** The orchestrator never promotes Aurora automatically.
8. **ElastiCache failover may be automated** if the profile opts in.
9. **Secondary ECS service runs warm-standby**, scaled to ≥1 task at all times. Failover never depends on a deployment.
10. **Notifications go through SNS.**
11. **One orchestrator stack per app.** Shared Terraform modules, isolated state.
12. **Net-new code.** Do not import or reference any prior failover orchestrator code.
13. **Kafka is on-prem**, reachable over the network. The app gates its consumer based on a regional indicator. When the indicator says ACTIVE, the app polls Kafka and processes messages. When PASSIVE, it does not. Containers stay up in both regions either way.
14. **Apps are read-tolerant during a writer flip.** Read traffic can be served from the secondary region's Aurora replica before the writer has been promoted. This means **DNS-first failover is allowed** for these apps — R53 may flip to the secondary on Tier 1 signal evaluation, before Aurora is manually promoted. Write attempts during the gap may fail, which is acceptable. The spec defaults to DNS-first for these apps and retains writer-first as a profile flag for any future app that is not read-tolerant.
15. **One SNS topic per AWS account**, not per app. The orchestrator publishes to the account-level topic with `app_name` in the message attributes; subscribers filter accordingly.
16. **CI/CD is GitHub + GitHub Actions.** The orchestrator lives in a net-new private GitHub repository. The full SDLC defined in §11 is mandatory for every change without exception.

### 2.1 POC: simplifications for the personal-account build

These overrides apply only to the POC build. Each is reverted when porting to JPMC production.

- **POC-A: TLS uses self-signed certs; canary disables TLS verification.** Outer NLB has a TLS listener using a self-signed certificate generated by Terraform and imported into ACM. The full topology — outer NLB → API Gateway → inner NLB → ALB → ECS — runs with TLS at the same termination points as JPMC production. The CloudWatch Synthetics canary runs with `ignoreHttpsErrors: true` (Puppeteer flag), controlled by profile field `canary.ignore_tls_errors`. JPMC port flips this to `false` and supplies the internal JPMC CA cert chain.
- **POC-B: No operator-facing API Gateway.** The operator interface is a single AWS Lambda (`failover-operator`) invoked directly via `aws lambda invoke --profile tbed`. IAM authenticates the caller via the user's AWS credentials. No mTLS, no Cognito, no Okta. Production at JPMC will front this with a Private API Gateway.
- **POC-C: Solo developer workflow.** PRs use CI for code quality only — no approving review required. Author can self-merge after CI passes. JPMC port adds mandatory second-reviewer approval and an approver-distinct-from-author rule.
- **POC-D: No external change-management integration.** No JIRA / ServiceNow ticket creation. Production at JPMC will add this gate.
- **POC-E: AWS account is the personal account; CLI profile `tbed` is used everywhere.** Both `us-east-1` and `us-east-2` are used.
- **POC-F: One target app for the test harness.** A representative synthetic ECS Fargate app (not a real deposits app) deployed by the `test-harness` Terraform module exercises the full pipeline. Real deposits apps onboard later as part of the JPMC port.
- **POC-G: Manual local `terraform apply`; no automated CD pipeline.** The Principal Engineer (or Claude Code) runs Terraform from a local environment with AWS CLI profile `tbed` configured. There is no GitHub OIDC federation, no automated test-harness deploy, no automated prod deploy, no approval gates, no release tagging automation. CI on PRs runs code quality checks (lint, types, tests, schema validation, `terraform validate`, `tflint`, `checkov`) — these prevent broken code from landing on `main` but do nothing to the AWS account. JPMC port adds the full automated CD pipeline; the migration is documented in §14.

---

## 3. Architecture

### 3.1 Components per region (mirrored in `us-east-1` and `us-east-2`)

All Lambdas are VPC-attached in private subnets. All AWS calls go through interface VPC endpoints.

| Component | Type | Purpose |
|---|---|---|
| **Signal Collector** | Lambda, EventBridge-scheduled (1 min) | Polls Tier 1, 2, 3 signals for the region. Writes raw observations to CloudWatch custom metrics namespace `Failover/{app}/Signals`. Writes structured snapshots to S3 (`s3://failover-state-{app}-{region}/observations/`) for audit. |
| **Decision Engine** | Lambda, EventBridge-scheduled (1 min) | Reads signal metrics, applies the decision rules in §4, writes the current `decision_state` to local SSM Parameter Store, publishes events to local SNS, and emits the **failover-control metric** that drives the Route 53 health check. |
| **Failover Executor** | Step Functions state machine, triggered manually OR by Decision Engine when `auto_failover=true` | Runs the failover/failback workflow in §5 and §6. Idempotent. Emits per-step SNS events. |
| **Indicator Updater** | Lambda, invoked only by the Step Functions state machine | Writes the regional indicator (`ACTIVE` / `PASSIVE` / `DRAINING`) to SSM Parameter Store under `/failover/{app}/{region}/role`. |
| **Health Probe (synthetic canary)** | CloudWatch Synthetics canary, deployed in the **opposite** region | Probes the routable endpoint of the *other* region end-to-end. The canary in `us-east-2` probes `us-east-1`, and vice versa. This is the most important Tier 1 signal. |
| **Profile Store** | S3 object versioned in each region, replicated via CRR | Per-app YAML profile. Source of truth in Git, deployed copy in S3. |
| **Audit Trail** | S3 bucket with CRR + versioning + Object Lock (governance mode, 90 days) | Immutable history of decisions, state changes, and executor runs. |
| **Operator interface** | Direct Lambda invoke + Step Functions `start-execution` via `aws` CLI / boto3 with profile `tbed` | Manual triggers for failover, failback, dry-run, drain, status, approval. No API Gateway during POC; IAM credentials are the auth. |

### 3.2 Cross-region coordination layer (no DynamoDB)

| Concern | Mechanism |
|---|---|
| Per-region runtime state | Each region writes only to **its own** SSM Parameter Store. No global write contention. |
| Cross-region event signalling | SNS topics in each region, subscribed cross-region. Used for "I see primary is down" / "I confirm secondary ready". |
| Audit / history | S3 with CRR ensures both regions can replay each other's decision history if one region is later down. |
| R53 control | Lambda **does not call `route53` directly**. Lambda emits a CloudWatch metric (`Failover/{app}/PrimaryHealthControl`); a CloudWatch alarm watches that metric; a Route 53 health check is bound to that alarm. R53 reacts to the alarm. This isolates Lambda from R53 API errors and makes the control surface a single, well-understood metric. |
| Profile distribution | Git → CI pipeline → upload to both regional S3 buckets → both Decision Engines re-read on schedule. |

### 3.3 The Regional Indicator (Kafka consumer gate)

- Stored in SSM Parameter Store: `/failover/{app}/{region}/role` with values `ACTIVE`, `PASSIVE`, `DRAINING`.
- Application library contract:
  - Polls every **15 seconds** via SSM VPC endpoint.
  - Caches last-known-good value in memory.
  - On SSM error, retains last-known-good for up to **2 minutes**, then **fails safe to PASSIVE**.
  - Exposes thread-safe `getRole()` to the Kafka consumer thread.
  - When `role != ACTIVE`, consumer pauses (does not poll the broker). When `role == ACTIVE`, consumer resumes.
- The framework writes the parameter; the application reads it. The contract is documented; an example client implementation is provided as a reference.
- **Anti-split-brain:** the parameter is written **only** by the Step Functions state machine, gated by the executor's sequence number. The state machine guarantees that only one region transitions to ACTIVE at a time, and that DRAINING precedes the other region becoming ACTIVE.

### 3.4 Why Step Functions for orchestration

Step Functions Standard is the orchestration engine because the failover workflow has three properties that disqualify simpler alternatives:

| Requirement | Why simpler alternatives fail |
|---|---|
| Pause indefinitely for manual Aurora approval (minutes to hours) | Single Lambda has 15-minute hard cap. EventBridge-chained Lambdas require building the pause/callback/timeout machinery yourself. |
| Idempotent re-entry on Lambda crash mid-flight | Self-built state machines in SSM require every action to be idempotent AND tracking which step the system was on AND determining whether the prior step completed before the crash — these are exactly the bugs Step Functions solves natively. |
| Audit trail of every state transition | Step Functions execution history retains 90 days of every input, output, retry, and timestamp; building equivalent logging in self-managed orchestration is meaningful effort. |

Specific Step Functions features used:
- **`waitForTaskToken`** for the Aurora manual approval gate. The state machine pauses, an SNS message carries a callback token, the operator calls `SendTaskSuccess`/`SendTaskFailure` after promoting the cluster.
- **`Retry`/`Catch`** declaratively for transient AWS API failures.
- **`Wait`** states for drain/quiesce/R53 propagation windows.
- **Express child workflows** are NOT used — the parent must be Standard for >5-minute total runtime.

Cost is negligible at expected execution rate (1–10 failovers per app per year, ~100 transitions per execution, ~$0.025 per 1,000 transitions).

Alternatives considered and rejected: single long-running Lambda (15-minute limit), Lambdas chained by EventBridge (re-implements Step Functions), state-in-SSM polled by EventBridge schedule (re-implements Step Functions, worse).

---

## 4. Decision Engine

### 4.1 Signal taxonomy

#### Tier 1 — Infrastructure (the only tier that can *trigger* failover)
| Signal | Source | Red condition |
|---|---|---|
| Outer NLB target health (primary region) | CloudWatch `AWS/NetworkELB UnHealthyHostCount` | All targets unhealthy ≥ dwell |
| Cross-region synthetic canary | CloudWatch Synthetics, deployed in **opposite** region, probes routable endpoint end-to-end every 1 min | Failure rate ≥ 80% over the dwell window |
| AWS Health API events | AWS Health API filtered by region + service set | Open issue affecting a service the app depends on |
| VPC endpoint health | CloudWatch metrics on interface endpoints used by the app's VPC | Endpoint failures over dwell |

#### Tier 2 — Data tier (gates *whether* failover is safe; cannot trigger on its own)
| Signal | Source |
|---|---|
| Aurora cluster topology (who is writer) | RDS `DescribeDBClusters` via VPC endpoint |
| Aurora replica lag | CloudWatch `AWS/RDS AuroraGlobalDBReplicationLag` |
| ElastiCache Global Datastore replication health | ElastiCache API + CloudWatch |

#### Tier 3 — Application (informational only — never triggers failover)
| Signal | Source |
|---|---|
| ALB target health | CloudWatch `AWS/ApplicationELB UnHealthyHostCount` |
| `/actuator/health` | ALB target health checks |
| API Gateway 5xx rate | CloudWatch `AWS/ApiGateway 5XXError` |

### 4.2 Decision rule (the heart of the system)

```
FAILOVER_AUTHORIZED = (
    count(Tier1 signals red) >= profile.tier1_quorum     # default 2 of N
    AND duration(red continuously) >= profile.dwell_minutes   # default 5
    AND time_since_last_decision >= profile.hysteresis_minutes  # default 3
    AND profile.auto_failover == true
)

FAILOVER_SAFE = (
    secondary_region_data_tier_ready (per Tier 2)
    AND secondary_ECS_warm_standby_healthy
)

EXECUTE_AUTO_FAILOVER = FAILOVER_AUTHORIZED AND FAILOVER_SAFE
```

If `FAILOVER_AUTHORIZED` but `auto_failover == false`: emit a high-priority SNS alert and stop. Operator decides.
If `FAILOVER_AUTHORIZED` but Aurora is configured `manual_approval_required: true`: the executor pauses at the Aurora step and waits for explicit approval (SNS + manual API call). This is the default for any app with Aurora.

### 4.3 Recommended starting profile values

| Field | Default | Rationale |
|---|---|---|
| `tier1_quorum` | 2 | Two independent infra signals must agree |
| `dwell_minutes` | 5 | Survives 3-min app deploy blips with margin |
| `hysteresis_minutes` | 3 | Prevents oscillation |
| `auto_failover` | `false` for first 30 days, then opt-in per app | Stage 1 = alerts only |
| `auto_failback` | `false` always | Failback is always operator-triggered |
| `aurora.manual_approval_required` | `true` always | Aurora promotion never auto |

---

## 5. Failover Workflow (Step Functions state machine)

States in order, each idempotent and resumable. The workflow has **two variants** controlled by `aurora.dns_first_failover`:

### 5.1 DNS-first failover (default for read-tolerant apps — recommended)

```
1.  EVALUATE                — Decision Engine signaled FAILOVER_AUTHORIZED.
2.  PRECHECK_SECONDARY      — Confirm secondary ECS warm-standby healthy, secondary VPC endpoints reachable, secondary Tier 1 signals green.
3.  NOTIFY_INITIATED        — SNS event with app_name attribute: "Failover initiated for {app} from {primary} to {secondary}".
4.  DRAIN_PRIMARY_INDICATOR — Set /failover/{app}/{primary}/role = DRAINING. Wait drain_seconds (default 60). Kafka consumer in primary stops.
5.  FLIP_R53_CONTROL_METRIC — Emit the CloudWatch metric value that flips the primary region's health-check alarm to ALARM. R53 begins routing to secondary.
6.  WAIT_R53_PROPAGATION    — Wait r53_propagation_seconds (default 90).
7.  PROMOTE_SECONDARY_INDICATOR — Set /failover/{app}/{secondary}/role = ACTIVE. Kafka consumer in secondary starts. Read traffic now served from secondary.
8.  AURORA_GATE             — If profile has Aurora:
                                if manual_approval_required: PAUSE (Wait-for-token via SNS + callback API).
                                else: skip.
                                Operator promotes Aurora secondary cluster to writer manually in console/CLI.
                                Executor confirms writer-in-secondary by polling DescribeDBClusters until cluster role flips and replica lag = 0 on the new writer.
                                If confirmation does not arrive within aurora_confirm_timeout (default 30 min), state machine emits CRITICAL SNS but does NOT roll back DNS.
                                Until Aurora is promoted, write attempts at secondary will fail — this is the acceptable contract for read-tolerant apps.
9.  ELASTICACHE_GATE        — If profile has ElastiCache:
                                if auto_failover: trigger ElastiCache Global Datastore failover via API.
                                else: PAUSE for manual.
                                Confirm replication topology.
10. POSTCHECK              — Confirm secondary canary, ALB targets, app health all green; confirm Aurora writer in secondary; confirm writes succeeding.
11. NOTIFY_COMPLETED       — SNS event with full decision trail. Update audit S3.
12. STABLE_SECONDARY       — Terminal success state.
```

### 5.2 Writer-first failover (legacy / strict-write profile)

For apps that set `aurora.dns_first_failover: false`, steps 5–9 are reordered: AURORA_GATE runs before FLIP_R53_CONTROL_METRIC. R53 never moves until Aurora writer is confirmed in secondary. This is the original behavior; retained for any future app that cannot tolerate write failures during the flip window.

Failure handling (both variants): any state failure routes to a `FAIL` state that emits CRITICAL SNS, writes an executor incident record to S3, and does not auto-rollback (rollback is operator-driven).

---

## 6. Failback Workflow (Step Functions state machine)

Triggered **only** by an operator (CLI / API). Same idempotency, same SNS at every step. Two variants mirror §5.

### 6.1 DNS-first failback (default for read-tolerant apps)

```
1.  PRECHECK_PRIMARY        — Confirm primary region Tier 1 signals all green for ≥ stable_minutes (default 30).
2.  NOTIFY_INITIATED        — SNS.
3.  DRAIN_SECONDARY_INDICATOR — Set /failover/{app}/{secondary}/role = DRAINING. Wait drain_seconds. Kafka consumer in secondary stops.
4.  QUIESCE                 — Wait quiesce_seconds (default 60) for in-flight requests at the secondary to complete.
5.  FLIP_R53_CONTROL_METRIC — Reset primary region's health-check metric to OK. R53 routes back to primary. Reads now served from primary's local Aurora replica.
6.  WAIT_R53_PROPAGATION    — Wait r53_propagation_seconds.
7.  PROMOTE_PRIMARY_INDICATOR — Set /failover/{app}/{primary}/role = ACTIVE. Kafka consumer in primary starts.
8.  AURORA_GATE             — Operator promotes Aurora primary cluster back to writer in primary region. Executor confirms writer-in-primary via polling.
                                Until Aurora is promoted, writes at primary will fail — acceptable contract.
9.  ELASTICACHE_GATE        — Mirror of failover gate.
10. POSTCHECK              — Confirm primary canary, ALB targets, app health green; confirm writes succeeding.
11. NOTIFY_COMPLETED       — SNS, audit S3.
12. STABLE_PRIMARY         — Terminal success state.
```

### 6.2 Writer-first failback (legacy / strict-write profile)

Mirrors §5.2: Aurora is promoted back to primary before R53 is flipped. Used only when `aurora.dns_first_failover: false`.

**Critical ordering invariant (writer-first variant only):** the region that owns the Aurora writer must be the same region that R53 sends traffic to. The state machine never flips R53 until Aurora confirmation; it never flips Aurora back until traffic is drained from the side losing the writer.

**Critical ordering invariant (DNS-first variant):** the region that R53 sends traffic to must reach Aurora writer state within `aurora_confirm_timeout_minutes`. If exceeded, CRITICAL SNS fires and operator must intervene; DNS does NOT roll back automatically because rolling back DNS to a region with a failed writer is worse than waiting in a known-degraded state.

For active/active apps that are **read-mostly**, profile flag `traffic_split_during_aurora_flip: true` allows reads to remain on both sides while the writer moves. Default `false`.

---

## 7. Profile Schema

Per-app YAML, stored in Git, deployed to S3 in both regions by CI. Validated by JSON Schema before deployment. Example:

```yaml
# profiles/deposits-account-service.yaml
app_name: deposits-account-service
pattern: active_passive            # active_passive | active_active
primary_region: us-east-1
secondary_region: us-east-2

components:
  api_gateway: true
  aurora: true
  elasticache: false
  kafka_consumer: true

network:
  outer_nlb_arn_primary:   arn:aws:elasticloadbalancing:us-east-1:...
  outer_nlb_arn_secondary: arn:aws:elasticloadbalancing:us-east-2:...
  alb_arn_primary:         arn:aws:elasticloadbalancing:us-east-1:...
  alb_arn_secondary:       arn:aws:elasticloadbalancing:us-east-2:...
  api_gw_id_primary:       abcd1234
  api_gw_id_secondary:     efgh5678
  routable_url_primary:    https://acct.us-east-1.deposits.internal.example.com/health
  routable_url_secondary:  https://acct.us-east-2.deposits.internal.example.com/health

dns:
  global_record_name: acct.deposits.internal.example.com
  hosted_zone_id:     Z0123456789ABCDEFG

aurora:
  cluster_id_primary:   deposits-acct-use1
  cluster_id_secondary: deposits-acct-use2
  global_cluster_id:    deposits-acct-global
  writer_policy: pin_primary       # pin_primary | follow_traffic
  manual_approval_required: true
  aurora_confirm_timeout_minutes: 30
  dns_first_failover: true         # DNS flips before writer promotion (read-tolerant apps).
                                   # Set false if writes must succeed during the entire flip window.

elasticache: null   # not used for this app

kafka:
  consumer_group: deposits-acct-consumer
  gate_on_indicator: true

signals:
  tier1_quorum: 2
  dwell_minutes: 5
  hysteresis_minutes: 3
  canary_failure_rate_pct: 80

canary:
  ignore_tls_errors: true          # POC: self-signed certs. Set false for JPMC production with internal CA.
  internal_ca_bundle_s3_uri: null  # JPMC production: s3://<bucket>/jpmc-internal-ca.pem

failover:
  auto_failover: false             # alerts-only until promoted
  auto_failback: false
  drain_seconds: 60
  quiesce_seconds: 60
  r53_propagation_seconds: 90
  stable_minutes_before_failback: 30

slo:
  rto_minutes: 15
  rpo_minutes: 5

notifications:
  # One SNS topic per account, shared across all apps in that account.
  # The app_name is included as a message attribute for subscriber filtering.
  sns_topic_arn_primary:   arn:aws:sns:us-east-1:<account-id>:failover-events
  sns_topic_arn_secondary: arn:aws:sns:us-east-2:<account-id>:failover-events
  events:
    - failover_authorized
    - failover_initiated
    - failover_step_completed
    - failover_completed
    - failover_failed
    - failback_initiated
    - failback_completed
    - failback_failed
    - signal_red
    - signal_recovered
```

A JSON Schema (`profile.schema.json`) MUST be enforced at CI time. Invalid profiles do not deploy.

---

## 8. Deliverables

### 8.1 Lambda code (Python 3.14)
- `signal_collector/` — Tier 1/2/3 collectors, one module per signal source.
- `decision_engine/` — Decision rule implementation, dwell/hysteresis tracking via CloudWatch metric math.
- `failover_executor/` — Step Functions Lambda task handlers (one Lambda per state for clear blast-radius and IAM scope).
- `failback_executor/` — Same shape as failover.
- `indicator_updater/` — SSM Parameter Store writer.
- `manual_trigger/` — Lambda(s) that operators invoke directly via `aws lambda invoke` to start the failover or failback Step Functions execution. Inputs validated, outputs include the execution ARN. No API Gateway in front.
- `approval_callback/` — Lambda that operators invoke directly to deliver `SendTaskSuccess` / `SendTaskFailure` to a paused Step Functions execution after Aurora promotion (or to abort).
- `lib/` — Shared utilities: profile loader, signal evaluator, metric math, structured logger, SNS publisher.
- All Lambdas use **boto3 with explicit VPC endpoint URLs** for the services they call (RDS, ElastiCache, CloudWatch, SSM, SNS, S3, Step Functions, Synthetics, Health). No internet egress.

### 8.2 Terraform (one root module per app, sharing reusable modules)

```
terraform/
  modules/
    failover-orchestrator/    # core stack: Lambdas, Step Functions, SNS, S3, SSM params, CW metrics/alarms, dashboards
    cross-region-canary/      # CW Synthetics canary deployed in opposite region
    r53-control/              # R53 record, health check, alarm-bound to control metric
    test-harness/             # synthetic ECS service + ALB + NLB + Aurora cluster (toggle on/off) for E2E tests
  apps/
    deposits-account-service/
      main.tf                 # uses modules above + reads profile YAML
      variables.tf
      profile.yaml            # symlink/copy of profiles/<app>.yaml
      backend.tf              # remote state per app
```

### 8.3 CloudWatch dashboard (one per app)
Required widgets:
- Tier 1 signal status grid (per signal, per region, current + last 24h)
- Tier 2 data-tier health (Aurora writer location, replica lag, ElastiCache state)
- Tier 3 app health (informational)
- Active region indicator (from SSM)
- Last 10 decisions (from S3 audit)
- Last failover/failback executions (from Step Functions)
- Failover-control metric and bound alarm state
- Cross-region canary results

### 8.4 Runbooks (Markdown, one per scenario)
- `RUNBOOK-manual-failover.md`
- `RUNBOOK-manual-failback.md`
- `RUNBOOK-aurora-promotion.md` — exact steps the operator runs in the Aurora console/CLI when the executor pauses at the Aurora gate
- `RUNBOOK-stuck-state-machine.md`
- `RUNBOOK-split-brain-recovery.md`
- `RUNBOOK-dry-run.md`
- `RUNBOOK-onboard-new-app.md`

### 8.5 Operator CLI (Python)
A `failoverctl` script — a thin wrapper around `boto3` that picks up AWS credentials via `AWS_PROFILE` (default `tbed`) or environment. No API Gateway in front:

- `failoverctl status <app>` — reads SSM, S3 audit, latest Step Functions execution
- `failoverctl failover <app> --to us-east-2 [--dry-run]` — invokes `manual_trigger` Lambda; prints the Step Functions execution ARN
- `failoverctl failback <app> [--dry-run]` — same, reverse direction
- `failoverctl approve <app> --execution-id <id>` — invokes `approval_callback` Lambda, which calls `SendTaskSuccess` on the paused Step Functions execution
- `failoverctl abort <app> --execution-id <id> --reason "..."` — invokes `approval_callback` with `SendTaskFailure`
- `failoverctl drain <app> --region us-east-1` — directly invokes `indicator_updater` Lambda
- `failoverctl history <app> [--limit N]` — lists Step Functions executions and S3 audit entries

Authorization: whatever the caller's IAM principal allows. During the POC build, profile `tbed` has admin in the personal account; in JPMC migration, scoped roles replace that.

### 8.6 Documentation and Diagrams (mandatory deliverables)

Documentation is a deliverable on the same level as code. PRs that change behavior without updating relevant documentation fail review. PRs that add architecture without diagrams fail review.

#### 8.6.1 Documents (in `docs/`)

| File | Audience | Contents |
|---|---|---|
| `docs/solution-overview.md` | Engineering leadership, new joiners | 2–3 pages: problem statement, design goals, how the solution achieves them, what it explicitly does not do, links to deep-dive docs. |
| `docs/architecture.md` | Engineers building or operating the system | Component-by-component deep dive of every box in §3, with embedded diagrams. |
| `docs/decision-engine.md` | Engineers debugging false positives / negatives | Exhaustive signal catalog (every signal: source, formula, red threshold, dwell, why it's in this tier), the decision rule from §4.2 fully expanded, worked examples. |
| `docs/operations.md` | SRE on-call | How to read the dashboard, how to interpret SNS events, common operational tasks, where logs live. |
| `docs/onboarding-new-app.md` | Engineer adding a new app | Step-by-step walkthrough with copy-paste examples for adding a profile, the Terraform app stack, validating in CI, deploying to test harness. |
| `docs/failure-modes.md` | Engineers and SREs | Index of all 14 scenarios in §10 with links to per-scenario walkthroughs in `docs/scenarios/`. |
| `docs/profile-reference.md` | Anyone authoring or modifying a profile | Field-by-field schema reference with type, default, allowed values, examples. Generated from `profile.schema.json` via a CI script and committed; CI fails if the generated doc doesn't match the schema. |
| `docs/api-reference.md` | CLI / automation users | Every operator Lambda's input payload, output format, error codes. |
| `docs/glossary.md` | All audiences | Acronyms (RTO, RPO, CRR, ASL, etc.) and project-specific terms. |
| `docs/adr/NNNN-*.md` | Engineering | Architecture Decision Records — append-only, numbered, with status (`Accepted` / `Superseded by NNNN`). At minimum: 0001 no-route53-arc, 0002 ssm-not-dynamodb, 0003 dns-first-failover-default, 0004 step-functions-for-orchestration, 0005 self-signed-tls-poc, 0006 github-oidc-not-static-keys. |
| `runbooks/RUNBOOK-*.md` | SRE on-call | Per §8.4. Each runbook has a fixed structure: When to use, Prerequisites, Procedure (numbered, copy-paste-ready commands), Verification, Rollback, Escalation. |

Top-level repo files:
- `README.md` — what this repo is, how to get started, link to docs/.
- `ARCHITECTURE.md` — short pointer to `docs/architecture.md`.
- `CONTRIBUTING.md` — branching, PR flow, CI expectations, link to CLAUDE.md.
- `SECURITY.md` — vulnerability reporting policy, dependency-update cadence.
- `CHANGELOG.md` — Keep a Changelog format.

#### 8.6.2 Diagrams (in `docs/diagrams/`)

Two diagram types, two tools:

| Diagram type | Tool | Format |
|---|---|---|
| Flow, sequence, state, decision tree, CI/CD pipeline | **Mermaid** in Markdown | Embedded in `.md` files; renders natively in GitHub. Source IS the rendered form. |
| AWS architecture (real service icons, VPC layout, network topology) | **`diagrams`** Python library (mingrammer/diagrams) | `.py` source committed; CI generates `.png` and `.svg`; both committed. CI verifies the committed PNGs match a fresh render. |

Required diagrams (file naming `NN-short-name.md` or `.py`):

| # | File | Type | What it shows |
|---|---|---|---|
| 01 | `01-solution-overview.md` | Mermaid flowchart | One-page picture: both regions, all major components, data flow direction. |
| 02 | `02-topology.py` → `.png/.svg` | diagrams (AWS icons) | Full network path in both regions: Outer NLB (TLS) → API GW → Inner NLB → ALB → ECS, with Aurora Global, ElastiCache, Kafka, VPC endpoints. |
| 03 | `03-signal-collection-flow.md` | Mermaid sequence | Each Tier 1/2/3 signal, who collects it, where it lands. |
| 04 | `04-decision-tree.md` | Mermaid flowchart | The §4.2 rule visualized as a decision tree. |
| 05 | `05-failover-statemachine.md` | Mermaid stateDiagram-v2 | Step Functions states with transitions. Both DNS-first and writer-first variants. |
| 06 | `06-failback-statemachine.md` | Mermaid stateDiagram-v2 | Same for failback. |
| 07 | `07-cross-region-coordination.md` | Mermaid sequence | How SSM, S3 CRR, SNS interact across regions. |
| 08 | `08-r53-control-pattern.md` | Mermaid sequence | Lambda emits CW metric → alarm changes state → R53 health check fails → DNS resolver answers with secondary IP. |
| 09 | `09-indicator-polling.md` | Mermaid sequence | ECS task → SSM (via VPC endpoint) → cache → Kafka consumer poll/pause decision. |
| 10 | `10-cicd-pipeline.md` | Mermaid flowchart | PR open → CI jobs in parallel → merge → test harness deploy → integration tests → tag → prod approval gates → prod deploy. |
| 11 | `11-iam-roles.md` | Mermaid graph | Every IAM role in the system, what it can do, what assumes it. |
| 12 | `12-vpc-and-endpoints.py` → `.png/.svg` | diagrams | Per-region VPC layout: subnets, route tables, VPC endpoints, security groups. |
| 13 | `13-test-harness.py` → `.png/.svg` | diagrams | What the `test-harness` Terraform module deploys (the synthetic app + supporting infra). |

#### 8.6.3 Per-scenario walkthroughs (in `docs/scenarios/`)

One Markdown file per scenario in §10. Filename `scenario-NN-short-name.md`. Each file contains:

1. **Title** and one-line summary.
2. **Setup** — initial state of all components, profile config relevant to the scenario.
3. **Sequence of events** — minute-by-minute (or tick-by-tick) what happens at each layer (NLB, API GW, ALB, ECS, Aurora, canary).
4. **Signal state at each tick** — table showing Tier 1, 2, 3 signal values.
5. **Decision evaluation at each tick** — does the rule from §4.2 trigger? Why or why not?
6. **Operator actions, if any** — what does on-call see and do?
7. **Final outcome** — failover happened or didn't; data tier final state.
8. **Mermaid sequence diagram** — visualizing the timeline.
9. **What this proves** — the property of the system this scenario verifies.

Scenarios required (from §10):

```
docs/scenarios/
├── scenario-01-deployment-503-blip.md
├── scenario-02-alb-unhealthy-only.md
├── scenario-03-single-az-outage.md
├── scenario-04-full-region-outage.md
├── scenario-05-api-gw-5xx-storm.md
├── scenario-06-app-cant-reach-aurora.md
├── scenario-07-dry-run.md
├── scenario-08-manual-with-aurora-approval.md
├── scenario-09-aurora-confirmation-timeout.md
├── scenario-10-failback.md
├── scenario-11-mid-failover-lambda-crash.md
├── scenario-12-split-brain-attempt.md
├── scenario-13-profile-change-mid-incident.md
└── scenario-14-canary-self-failure.md
```

#### 8.6.4 CI enforcement

Three new CI jobs (added to §11.5):

| Job | Purpose | Failure = block merge |
|---|---|---|
| `mermaid-validate` | Parse every Mermaid block in the repo with `@mermaid-js/mermaid-cli`; fail on syntax errors | Yes |
| `diagrams-render-check` | Run every `.py` in `docs/diagrams/`; diff generated PNG/SVG against committed; fail if drift | Yes |
| `profile-doc-check` | Generate `docs/profile-reference.md` from schema; diff against committed; fail if drift | Yes |

#### 8.6.5 Documentation freshness

- Every PR labeled `behavior-change` must touch at least one file in `docs/` or `runbooks/`. CI checks this via a label-required job.
- Quarterly: a scheduled `docs-freshness` job lists all docs not modified in 90+ days and opens a single tracking issue. Items are reviewed and either touched (with a "reviewed YYYY-MM-DD" line at the bottom of the doc) or marked deprecated.

### 8.7 Validation framework (`tests/chaos/` + `Makefile`)

The validation framework is **the** bottleneck for build velocity. Iteration speed depends on it being correct, complete, and fast. Build it like a deliverable, not an afterthought.

#### 8.7.1 Make targets (the validation surface)

```
make harness-up           # apply base + runtime; idempotent; reuses live infra if up
make harness-down         # destroy everything; only used when explicitly stable or for clean restart
make runtime-apply        # apply runtime layer ONLY; used during tight iteration loops
make scenario-N           # run scenario N (1-14); produces tests/results/scenario-N.json
make scenario-reset       # reset orchestrator runtime state (SSM, control metrics, abort in-flight Step Functions)
make scenarios-parallel   # run scenarios 1, 2, 3, 5, 13, 14 concurrently (non-mutating set)
make scenarios-sequential # run scenarios 4, 7, 8, 9, 10, 11, 12 sequentially (mutating set)
make scenarios-all        # parallel batch then sequential batch; consolidated report
make stable-suite         # run scenarios-all THREE consecutive times; pass only if all 3 runs are clean
make logs-tail SCENARIO=N # tail every relevant Lambda's logs for scenario N in real time
make state-dump           # dump full orchestrator state (SSM, alarms, Step Functions, S3 audit) as JSON
```

#### 8.7.2 What every scenario test must validate

A scenario "passing" is not just "the right action happened." Each scenario test asserts every layer of observable behavior:

| Assertion class | What's checked | Source |
|---|---|---|
| **Final state** | DNS resolution, regional indicator value (ACTIVE/PASSIVE/DRAINING), Aurora writer location, ECS task counts in both regions | DNS query, SSM Parameter Store, RDS DescribeDBClusters, ECS DescribeServices |
| **State machine path** | Which Step Functions states were entered, in what order, with what inputs/outputs | Step Functions GetExecutionHistory |
| **SNS notifications** | Which events published, with which message attributes, in what order, to the account-level topic | SQS test queue subscribed to the topic |
| **Structured logs** | Every expected log event from §3.3 vocabulary appeared in the right Lambda with required fields | CloudWatch Logs Insights query per Lambda |
| **CloudWatch metrics** | Custom metrics emitted with expected values (`Failover/{app}/PrimaryHealthControl`, signal metrics) | CloudWatch GetMetricData |
| **CloudWatch alarms** | Alarms in the right state at the right time | DescribeAlarms with state history |
| **R53 health checks** | Health check state transitions matched the orchestrator's metric emissions | GetHealthCheckLastFailureReason, status history |
| **S3 audit trail** | Decision records, observation snapshots, executor incident records were written with expected schema | S3 ListObjects + GetObject + JSON schema validation |
| **Indicator semantics** | App-side: a synthetic Kafka consumer running in the test harness app actually paused/resumed at the right moments | Test app exposes a `/test/consumer-status` endpoint |
| **Timing** | Each phase completed within the expected window (drain, R53 propagation, Aurora confirmation, etc.) | Timestamps from above sources |

A scenario test is structured as:

```python
# tests/chaos/scenario_04_full_region_outage.py
SETUP   = "force NLB targets unhealthy in us-east-1; force canary failure; inject AWS Health event"
TIMEOUT = 600  # 10 minutes hard cap

def setup() -> None: ...
def assertions() -> list[Assertion]: ...   # 30+ assertions covering every layer above
def cleanup() -> None: ...                 # restore baseline; failback if needed
```

The framework runs setup, waits for the orchestrator to act, evaluates every assertion in `assertions()`, then runs cleanup. **Cleanup itself is a tested code path** — failback paths are validated as part of every scenario that left the system failed-over.

#### 8.7.3 Scenarios that include both failover and failback

These scenarios validate the **complete** cycle, not just one direction:

- **Scenario 4** (region outage): failover happens automatically (once auto_failover enabled), then operator-triggered failback in the cleanup phase.
- **Scenario 7** (dry-run): no real action, no cleanup needed.
- **Scenario 8** (manual + Aurora approval): full failover including Aurora approval callback, then full failback.
- **Scenario 10** (failback after stable secondary): primary scenario for failback validation.
- **Scenario 11** (Lambda crash mid-failover): failover resumes after crash, then operator failback.

For these, assertions cover both the forward and reverse paths.

#### 8.7.4 Notification, log, and metric assertions are explicit

Sample assertion list for Scenario 4 (illustrative):

```
final_state.dns_resolves_to == us-east-2_endpoint
final_state.indicator[us-east-1] == PASSIVE
final_state.indicator[us-east-2] == ACTIVE
final_state.aurora_writer_region == us-east-2
state_machine.path == [EVALUATE, PRECHECK_SECONDARY, NOTIFY_INITIATED,
                       DRAIN_PRIMARY_INDICATOR, FLIP_R53_CONTROL_METRIC,
                       WAIT_R53_PROPAGATION, PROMOTE_SECONDARY_INDICATOR,
                       AURORA_GATE, ELASTICACHE_GATE, POSTCHECK,
                       NOTIFY_COMPLETED, STABLE_SECONDARY]
sns.events_in_order == [failover_authorized, failover_initiated,
                        failover_step_completed (×N), failover_completed]
sns.event[0].message_attributes.app_name == "test-app"
logs.decision_engine.failover_authorized_count == 1
logs.failover_executor.aurora_gate_paused_count == 1
logs.failover_executor.aurora_gate_approved_count == 1
metrics.PrimaryHealthControl[us-east-1].max == 0     # health-check trip value
audit.s3.decision_records_count == 1
audit.s3.executor_run_records_count == 1
indicator.kafka_consumer_paused_during_drain == True
indicator.kafka_consumer_resumed_after_promote == True
timing.drain_to_r53_flip < drain_seconds + 10
timing.total_failover_duration < 600
# ... and ~20 more
```

The framework provides assertion helpers (`assert_sns_events_in_order`, `assert_log_event_count`, `assert_state_machine_path`) so each scenario test reads as a list of declarations, not boilerplate.

#### 8.7.5 Tight-loop iteration support

- **`make scenario-reset` runs in <30 seconds.** It does not redeploy infra. It clears SSM params, resets the failover-control metric to OK, aborts any in-flight Step Functions execution, and resets the test app's synthetic state.
- **`make runtime-apply` runs in <5 minutes** (typical Lambda + Step Functions changes). Base layer untouched.
- **A typical edit-test cycle:** edit Lambda → `make runtime-apply` → `make scenario-N` → read JSON result → fix → repeat. Target loop time: <10 minutes. If a scenario takes longer than its declared TIMEOUT, the framework kills it and surfaces a partial-state report so debugging starts immediately.

---

## 9. Repository Layout

```
.
├── SPEC.md                          # this document
├── CLAUDE.md                        # build guidance for Claude Code (style, anti-patterns, do-nots)
├── profiles/
│   ├── profile.schema.json
│   ├── deposits-account-service.yaml
│   └── ...                          # one per app
├── lambdas/
│   ├── signal_collector/
│   ├── decision_engine/
│   ├── failover_executor/
│   ├── failback_executor/
│   ├── indicator_updater/
│   ├── manual_trigger/
│   ├── approval_callback/
│   └── lib/
├── statemachines/
│   ├── failover.asl.json
│   └── failback.asl.json
├── terraform/
│   ├── modules/
│   │   ├── orchestrator-base/       # VPCs, subnets, VPC endpoints, NLBs, ALBs, ECS cluster, Aurora Global, ACM certs, S3 buckets, Route 53 zone — the slow-to-create resources (15-25 min for Aurora)
│   │   ├── orchestrator-runtime/    # Lambdas, Step Functions, SSM params, CloudWatch alarms, Synthetics canaries, R53 records — the fast-iterating resources (seconds to minutes)
│   │   ├── cross-region-canary/
│   │   ├── r53-control/
│   │   └── test-harness-app/        # synthetic ECS Fargate app (base + runtime separation inside)
│   └── apps/
│       └── test-app/
│           ├── base/                # apply once at start of session; rarely changes
│           ├── runtime/             # apply on every code change; redeploys in seconds
│           └── shared.tfvars        # variables shared across both layers
├── canaries/
│   └── routable_endpoint_probe.py   # CloudWatch Synthetics canary script
├── client_examples/
│   └── kafka_indicator_client/      # reference Java + Python client for the regional indicator contract
├── cli/
│   └── failoverctl
├── docs/
│   ├── solution-overview.md
│   ├── architecture.md
│   ├── decision-engine.md
│   ├── operations.md
│   ├── onboarding-new-app.md
│   ├── failure-modes.md
│   ├── profile-reference.md         # generated from schema by CI; verified clean in PR
│   ├── api-reference.md
│   ├── glossary.md
│   ├── adr/
│   │   ├── 0001-no-route53-arc.md
│   │   ├── 0002-ssm-not-dynamodb-runtime-state.md
│   │   ├── 0003-dns-first-failover-default.md
│   │   ├── 0004-step-functions-for-orchestration.md
│   │   ├── 0005-self-signed-tls-poc.md
│   │   └── 0006-github-oidc-not-static-keys.md
│   ├── diagrams/
│   │   ├── 01-solution-overview.md
│   │   ├── 02-topology.py
│   │   ├── 02-topology.png
│   │   ├── 02-topology.svg
│   │   ├── 03-signal-collection-flow.md
│   │   ├── 04-decision-tree.md
│   │   ├── 05-failover-statemachine.md
│   │   ├── 06-failback-statemachine.md
│   │   ├── 07-cross-region-coordination.md
│   │   ├── 08-r53-control-pattern.md
│   │   ├── 09-indicator-polling.md
│   │   ├── 10-cicd-pipeline.md
│   │   ├── 11-iam-roles.md
│   │   ├── 12-vpc-and-endpoints.py + .png + .svg
│   │   └── 13-test-harness.py + .png + .svg
│   └── scenarios/
│       ├── scenario-01-deployment-503-blip.md
│       ├── scenario-02-alb-unhealthy-only.md
│       ├── scenario-03-single-az-outage.md
│       ├── scenario-04-full-region-outage.md
│       ├── scenario-05-api-gw-5xx-storm.md
│       ├── scenario-06-app-cant-reach-aurora.md
│       ├── scenario-07-dry-run.md
│       ├── scenario-08-manual-with-aurora-approval.md
│       ├── scenario-09-aurora-confirmation-timeout.md
│       ├── scenario-10-failback.md
│       ├── scenario-11-mid-failover-lambda-crash.md
│       ├── scenario-12-split-brain-attempt.md
│       ├── scenario-13-profile-change-mid-incident.md
│       └── scenario-14-canary-self-failure.md
├── runbooks/
│   └── *.md
└── tests/
    ├── unit/
    ├── integration/                 # against test-harness module
    └── chaos/                       # scripted chaos scenarios
```

Top-level files: `README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`, `LICENSE` (or `NOTICE`).

---

## 10. Test Scenarios (must pass before any app onboards)

Each scenario is a scripted test executed against the `test-harness` Terraform module, which deploys a representative ECS Fargate app with the **full topology** (Outer NLB with TLS → API GW → Inner NLB → ALB → ECS Fargate, plus Aurora Global) in account `tbed`, both regions. **TLS uses self-signed certs and the canary runs with `ignoreHttpsErrors: true`** per §2.1 POC-A. Every scenario has a corresponding walkthrough doc in `docs/scenarios/`.

| # | Scenario | Expected outcome |
|---|---|---|
| 1 | App deployment causes `/actuator/health` to return 503 for 3 minutes in primary | **No failover.** Decision Engine logs Tier 3 red, Tier 1 green, no action. |
| 2 | ALB targets unhealthy in primary for 10 min, but NLB targets and canary green | **No failover.** Tier 3 only. |
| 3 | Single AZ outage in primary (target group spread across AZs) | **No failover.** Surviving AZ keeps NLB target health > 0. |
| 4 | Full primary region outage (NLB targets all unhealthy + cross-region canary fails + AWS Health event) | **Failover authorized**, executor runs, Aurora gate pauses (manual), R53 flips after Aurora confirmed, indicator flips, Kafka consumer starts in secondary. |
| 5 | API Gateway 5xx rate spikes to 100% in primary, infra otherwise green | **No failover.** Tier 3 only. |
| 6 | Network partition: primary cannot reach Aurora writer, but routable endpoint and canary succeed | **No automatic failover.** Tier 1 still green. SNS alert fires. Operator decides. |
| 7 | Operator triggers `failoverctl failover --dry-run` | State machine runs in dry-run mode: emits all SNS events with `[DRY-RUN]`, makes no SSM/R53/Aurora changes, logs the actions it would have taken. |
| 8 | Operator triggers manual failover with Aurora `manual_approval_required: true` | Executor pauses at Aurora gate, SNS alert sent, operator runs Aurora promotion in console, calls `failoverctl approve`, executor resumes. |
| 9 | Aurora confirmation never arrives within timeout | Executor fails, CRITICAL SNS, no R53 flip, no indicator flip — system is in a *known stuck* state, not split-brain. |
| 10 | Failback after stable secondary | Operator triggers `failoverctl failback`, full reverse workflow runs. |
| 11 | Mid-failover Lambda crash | State machine resumes from last successful state; idempotency holds. |
| 12 | Both regions briefly write to SSM concurrently (simulated split-brain attempt) | Indicator state machine guard prevents both being ACTIVE; one ends in DRAINING. |
| 13 | Profile change with `auto_failover: true` → `false` mid-incident | Decision Engine respects the latest deployed profile within 1 polling interval. |
| 14 | Synthetic canary itself fails (canary infra issue, not target outage) | Canary failure alone is one signal; without quorum, no failover. SNS alert on canary degraded. |

Chaos scenarios are runnable as `make chaos-N` from the test harness.

---

## 11. Software Development Lifecycle (POC scope — code quality discipline only)

The orchestrator lives in the private GitHub repository **`ramirezh84/failoverv2`**. Every change to Lambda code, Step Functions definitions, Terraform, profiles, runbooks, and documentation goes through PR + CI before landing on `main`. **Deployments to AWS are manual** (`terraform apply` from a local environment with profile `tbed`); no automated CD pipeline exists in the POC.

JPMC port adds the full enterprise CI/CD scaffolding (GitHub OIDC, automated test-harness deploy, prod approval gates, drift detection, dependabot cadence, chaos game day automation, change-management integration). Those items are catalogued in §14 — not in scope for this build.

### 11.1 Repository setup (one-time, prerequisite)

- **Visibility:** private.
- **Default branch:** `main`, protected per §11.4.
- **Branch protection on `main`:**
  - Require pull request before merging
  - Require status checks to pass (CI jobs in §11.5)
  - Require branches to be up to date before merging
  - Require linear history (squash or rebase only)
  - Restrict direct pushes
- **GitHub features enabled:** Issues, Dependabot security updates, Secret scanning, Push protection for secrets, Code scanning (CodeQL).
- **No GitHub OIDC, no AWS role secrets.** Deploys are local; GitHub never touches AWS.

### 11.2 Repository content (in addition to §9 layout)

```
.github/
├── CODEOWNERS                            # Principal Engineer
├── pull_request_template.md
├── ISSUE_TEMPLATE/
│   ├── bug_report.md
│   ├── new_app_onboarding.md
│   └── profile_change_request.md
├── dependabot.yml                        # security updates only
└── workflows/
    ├── ci.yml                            # PR code-quality validation
    ├── codeql.yml                        # CodeQL scan on PR + weekly
    ├── mermaid-validate.yml              # Mermaid syntax check
    ├── diagrams-render-check.yml         # diagrams Python lib output diff
    └── profile-doc-check.yml             # profile-reference.md drift check
```

Top-level files: `README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`, `LICENSE`.

### 11.3 Branching strategy

- **Trunk-based.** `main` always reflects the latest known-good state.
- **Short-lived feature branches:** `feat/<slug>`, `fix/<slug>`, `chore/<slug>`. Maximum 5 working days; stale branches flagged.
- No long-lived release branches. Tags off `main` mark milestones (semver `vX.Y.Z`) but do not trigger any automation in the POC.

### 11.4 Pull request requirements

Every PR must include:

1. **Linked issue or ADR.** No orphan PRs.
2. **PR description** filled per template: what changed, why, blast radius, manual deploy steps if any, runbook updates required.
3. **Tests added or updated** for every code change. Coverage cannot decrease.
4. **Profile schema validation passing** if profile or schema touched.
5. **Terraform fmt + validate clean** for any Terraform change.
6. **Runbook updates** for any behavior change.
7. **Diagram and documentation updates** for any architectural or behavioral change (§8.6).
8. **CHANGELOG.md entry** under `## [Unreleased]`.
9. **All CI checks green.** No merge with red checks.

**Approving review:** NOT required during the POC (solo workflow). Author self-merges after CI passes.

### 11.5 CI pipeline (`.github/workflows/ci.yml`, runs on every PR)

CI runs code-quality checks. **No CI job touches AWS.** No deploys, no Terraform plan against the live account, no integration tests against deployed infrastructure. Deployments are manual and local.

| Job | Purpose | Failure = block merge |
|---|---|---|
| `lint-python` | `ruff check`, `ruff format --check`, `mypy --strict` on lambdas/ and lib/ | Yes |
| `unit-tests` | `pytest` with coverage; gate at ≥80% line coverage, ≥70% branch | Yes |
| `profile-schema-validation` | Validate every YAML in `profiles/` against `profile.schema.json`; reject malformed examples in `tests/unit/profile_validation/invalid/` | Yes |
| `terraform-fmt` | `terraform fmt -check -recursive` | Yes |
| `terraform-validate` | `terraform validate` for every root module — runs without AWS creds | Yes |
| `tflint` | Lint Terraform for AWS-specific anti-patterns | Yes |
| `checkov` | Static analysis of Terraform for security misconfigurations; fail on HIGH/CRITICAL | Yes |
| `bandit` | Python security linter | Fail on HIGH/CRITICAL |
| `semgrep` | SAST with custom rules for boto3 (e.g. detect lambdas missing VPC config, detect IAM `*` actions) | Yes |
| `gitleaks` | Secret scan beyond GitHub native | Yes |
| `pip-audit` | Python dependency vulnerability scan | Fail on HIGH/CRITICAL |
| `iam-policy-check` | Custom job: parse Terraform sources, fail if any IAM policy contains `Action: "*"` or `Resource: "*"` | Yes |
| `vpc-endpoint-check` | Custom job: every Lambda Terraform resource must have `vpc_config` block; fail if missing | Yes |
| `markdownlint` | Lint Markdown in `docs/` and `runbooks/` | Yes |
| `mermaid-validate` | Parse every Mermaid block; fail on syntax errors | Yes |
| `diagrams-render-check` | Run `.py` files in `docs/diagrams/`; diff against committed PNG/SVG | Yes |
| `profile-doc-check` | Generate `docs/profile-reference.md` from schema; diff against committed | Yes |
| `link-check` | Broken link checker for Markdown | Warn only |

### 11.6 Deployment model (manual, local)

There is no CD pipeline. Deployments work like this:

1. Pull latest `main`.
2. Configure AWS profile: `export AWS_PROFILE=tbed`.
3. Navigate to the relevant Terraform root: `cd terraform/apps/test-harness/`.
4. `terraform init && terraform plan && terraform apply`.
5. Run integration / chaos tests against the deployed harness using the test runner: `make test-integration` or `make chaos-N`.

Any change to a deployed environment requires the operator to remember to apply it. Drift between `main` and the live account is possible and must be checked manually before testing. (When porting to JPMC, the GHA-driven pipeline removes this manual step — see §14.)

### 11.7 Tagging and changelog

- PRs merged to `main` accumulate under `## [Unreleased]` in `CHANGELOG.md`.
- When the orchestrator reaches a stable milestone, the operator opens a release PR moving `[Unreleased]` content under `[vX.Y.Z]` with date, then tags `vX.Y.Z` after merge.
- Tags do not trigger any deployment or release automation in the POC. They exist for human reference and to give Terraform a known commit to align deployed state against.

### 11.8 Onboarding a new app (manual)

1. Open an issue using the `new_app_onboarding.md` template.
2. Open a PR adding `profiles/<new-app>.yaml` and `terraform/apps/<new-app>/`.
3. CI validates schema, ensures no IAM widening, lints Terraform.
4. Self-merge after CI passes.
5. Manually run `terraform apply` against the new app's stack.
6. Onboarding runbook (`runbooks/RUNBOOK-onboard-new-app.md`) walks the operator through post-deploy verification.

---

## 12. Operational Rollout Strategy (POC, single-app)

This section governs how the orchestrator's behavior matures over the life of the POC, separate from how individual code changes flow through CI.

1. **Stage 0 — Dry-run only.** Profile sets `auto_failover: false`. Operator triggers `failoverctl failover --dry-run` regularly to validate signal collection and state machine correctness without acting on real data.
2. **Stage 1 — Alert-only.** `auto_failover: false`. Decision Engine fires SNS when criteria met. Operator runs manual failover when signals are valid. Tune `dwell_minutes` and `tier1_quorum` based on observed signal patterns in the test harness.
3. **Stage 2 — Auto-failover with manual Aurora.** Set `auto_failover: true`. Aurora gate stays manual.
4. **Chaos validation.** Run all 14 scenarios against the live test harness via `make chaos-N`. Document outcomes in `docs/scenarios/`. JPMC port adds these as a quarterly automated game day.

Every manual `terraform apply` should be preceded locally by:
- `terraform plan` reviewed by the operator
- Unit tests passing (`make test-unit`)
- Profile schema validation passing

---

## 13. Acceptance Criteria

A change is mergeable only if:

1. All CI jobs in §11.5 pass green.
2. Profile JSON Schema rejects every malformed example in `tests/unit/profile_validation/invalid/`.
3. Every Lambda has ≥80% line coverage, every signal collector module has tests for healthy/unhealthy/timeout cases.
4. **Terraform `validate` and `fmt`** pass for every root module (CI runs these without AWS creds).
5. **Static IAM policy check** passes: zero `Action: "*"`, zero `Resource: "*"`.
6. **VPC config check** passes: every Lambda Terraform resource has a `vpc_config` block.
7. Runbooks exist for every scenario in §8.4.
8. **No runtime code path uses DynamoDB, AppConfig, or Route 53 ARC.** A DynamoDB lock table is permitted only as the Terraform state-lock backend (the orchestrator's runtime never reads or writes it).
9. No code path is borrowed from any prior failover orchestrator.
10. **All required documents in §8.6.1 are present** and have audience headers.
11. **All required diagrams in §8.6.2 are present**, Mermaid diagrams parse cleanly, `diagrams` Python sources regenerate identically to committed PNG/SVG.
12. **All 14 scenario walkthroughs in `docs/scenarios/` are present** and each has a Mermaid sequence diagram.
13. **`docs/profile-reference.md` is in sync with `profiles/profile.schema.json`** (CI verifies).
14. `README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md` exist at the repo root.

A POC milestone is "stable" when:

- A clean `make harness-up` deploys both layers (base + runtime) successfully in account `tbed` across `us-east-1` and `us-east-2`.
- `make stable-suite` passes — i.e., **`make scenarios-all` passes three consecutive times** with no spurious failures, no flaky retries, no manual intervention beyond the documented Aurora approval steps in scenarios 8 and 10.
- Every scenario's assertion list (per §8.7.2) is satisfied — final state, state machine path, SNS notifications in order, structured logs, CloudWatch metrics and alarms, R53 health check transitions, S3 audit records, indicator semantics, and timing.
- A failover and a failback are demonstrated end-to-end with the operator using `failoverctl`, with all observability layers verified.
- `make state-dump` produces a JSON snapshot showing the system in a known-good baseline state at the end of the suite.

There is no "production deploy" gate in the POC — POC stability is local validation. JPMC port adds a real production deployment gate (§14).

---

## 14. Future Migrations (out of scope for this build, but design must accommodate)

- **DynamoDB Global Tables** replacing SSM Parameter Store + S3 CRR for state. Isolation point: `lib/state_store.py` interface.
- **AppConfig with on-host agent** replacing SSM-based regional indicator. Isolation point: `lib/indicator_writer.py` interface and the documented client contract.
- **API Gateway removal** when org modernization completes. Isolation point: `network` block in profile + signal collector's API GW module (already optional).
- **Active/active write traffic** when Aurora Global writer-anywhere becomes acceptable. Isolation point: `aurora.writer_policy` field.
- **Operator API Gateway with IAM SigV4 + role separation** (`FailoverOperator` / `FailoverApprover`) added in front of the existing `manual_trigger` and `approval_callback` Lambdas. The Lambdas themselves do not change. Isolation point: new `terraform/modules/operator-api/` module + Terraform-toggled in front of existing Lambdas.
- **Real internal CA certs** replacing self-signed certs at the outer NLB. Synthetics canary's `ignore_tls_errors` flag flipped to `false` and the JPMC internal CA bundle supplied. Isolation point: `canary.ignore_tls_errors` and `canary.internal_ca_bundle_s3_uri` profile fields.
- **Automated CI/CD pipeline** replacing manual local `terraform apply`. This is the largest single migration. Adds:
  - GitHub OIDC identity provider in the JPMC AWS account(s).
  - IAM deploy roles with trust policies scoped to the repo, branch (for non-prod), and tag pattern (for prod). No static AWS keys in GitHub at any stage.
  - GitHub Actions workflows: `deploy-test-harness.yml` (on merge to `main`), `integration-tests.yml` (after test harness deploy success), `deploy-prod.yml` (tag-triggered, manual approval gate, change-management ticket required), `release.yml` (SBOM + changelog), `terraform-drift.yml` (nightly), `chaos-game-day.yml` (quarterly).
  - CODEOWNERS with mandatory secondary reviewer and approver-distinct-from-author rule.
  - Branch protection requiring approving review.
  - Dependabot weekly cadence for Python, Terraform, GitHub Actions versions.
  - JIRA / ServiceNow change-ticket gate before prod approval.
  - Multi-account Terraform workspaces (one per JPMC account / environment).

  Isolation point: `.github/workflows/` directory and a new `terraform/modules/gha-oidc/` module. **The orchestrator's runtime code, profiles, state machines, and infrastructure-under-test do not change.** Only the surrounding deploy automation is added.

---

## 15. Confirmed decisions and remaining items

### 15.1 Confirmed by Principal Engineer (locked into this spec)
- Lambda runtime: **Python 3.14**.
- SNS: **one topic per AWS account**, app distinguished via message attributes.
- Repository: private GitHub repo **`ramirezh84/failoverv2`**. Code-quality CI on PRs only — no automated CD pipeline in the POC. Deploys are manual via local `terraform apply` with profile `tbed`.
- Apps are **read-tolerant** during writer flip; **DNS-first failover is the default**, with writer-first retained as a profile flag for future strict-write apps.
- **Build target:** Principal Engineer's personal AWS account, accessed via AWS profile `tbed`. Single-account, two-region POC.
- **TLS handling for POC:** self-signed certs at the same termination points as JPMC. Synthetics canary runs with `ignoreHttpsErrors: true` via profile flag. **Full topology including API Gateway is built from day one** — no incremental enabling.
- **No operator API Gateway.** Operators invoke `manual_trigger` and `approval_callback` Lambdas directly via `aws lambda invoke` (or the `failoverctl` CLI wrapping `boto3`). IAM credentials behind profile `tbed` are the auth.
- **Step Functions Standard** is the orchestration engine (rationale in §3.4).
- **No GitHub OIDC, no AWS role secrets, no automated deploys** in the POC. GitHub never touches AWS. JPMC port adds the full automated CD pipeline as a single migration item (§14).
- **Solo workflow.** Author self-merges after green CI. No approving review required. JPMC port adds the second-reviewer rule.
- **Profile store: S3 with versioning + Cross-Region Replication enabled** even in single-account POC. Reliability over simplicity. Each region's Decision Engine reads from its local bucket; CRR ensures the secondary region always has the latest profile even if the primary region is unreachable. Identical to the JPMC target.
- **Terraform state backend:** S3 with versioning + native S3 locking (Terraform 1.10+) OR S3 + DynamoDB lock table — Claude Code picks whichever is simpler given the Terraform version. The DynamoDB lock table is a permitted exception to the runtime DDB ban (it's a Terraform concern, never touched by orchestrator runtime code).
- **AWS service quotas:** Principal Engineer is responsible for confirming `tbed` has capacity in both regions for ECS Fargate, NLB, ALB, Aurora Global, Step Functions, Synthetics, Lambda concurrency, VPC endpoints. If a `terraform apply` fails on a quota limit, Principal Engineer requests an increase manually.

### 15.2 Items requiring confirmation before Claude Code starts

None. All decisions are locked. Claude Code may start work using SPEC.md and CLAUDE.md as the source of truth.