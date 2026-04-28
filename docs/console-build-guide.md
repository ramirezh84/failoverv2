# Console Build Guide — Orchestrator (no IaC)

**Audience:** Operators building the orchestrator in the AWS Console.
**Assumes:** VPCs, subnets, route tables, IGWs/NATs, the customer app
(active/passive), and Aurora are already deployed. This guide covers the
**orchestrator** only: VPC endpoint verification, S3/KMS/SNS, IAM, Lambdas,
Step Functions, EventBridge, alarms, Synthetics, Route 53.

**Cadence:** ~10 phases, each with a verify gate. Don't skip the gates —
the most painful failures (IAM, SG, VPC endpoint DNS) only show up at
runtime and are 10× harder to debug than they are to prevent.

**Time:** 1.5–2 days for the first region; ~half that for the second region
(you'll be copy-pasting most of it).

---

## Phase 0 — Decide variables

Pick these now, write them down, never change them:

| Variable | Example | Notes |
|---|---|---|
| `APP_NAME` | `myapp` | Used in every resource name; lowercase, hyphens ok |
| `PRIMARY_REGION` | `us-east-1` | Active region |
| `SECONDARY_REGION` | `us-east-2` | Warm-passive region |
| `ACCOUNT_ID` | `123456789012` | The AWS account |
| `VPC_ID_PRIMARY` | `vpc-0abc...` | Existing VPC in primary |
| `VPC_ID_SECONDARY` | `vpc-0def...` | Existing VPC in secondary |
| `PRIVATE_SUBNETS_PRIMARY` | 3 subnet IDs | Where Lambdas attach |
| `PRIVATE_SUBNETS_SECONDARY` | 3 subnet IDs | Same |
| `LAMBDA_SG_PRIMARY` | `sg-0...` | Lambda egress SG (will create or reuse) |
| `LAMBDA_SG_SECONDARY` | `sg-0...` | Same |
| `VPCE_SG_PRIMARY` | `sg-0...` | VPC endpoint ingress SG |
| `VPCE_SG_SECONDARY` | `sg-0...` | Same |
| `AURORA_GLOBAL_CLUSTER_ID` | `myapp-global` | Existing |
| `APP_PUBLIC_URL_PRIMARY` | `https://myapp.use1.example.internal` | Routable URL the canary probes |
| `APP_PUBLIC_URL_SECONDARY` | `https://myapp.use2.example.internal` | Same |
| `R53_HOSTED_ZONE_ID` | `Z0...` | Public or private zone for the failover record |
| `R53_RECORD_NAME` | `myapp.example.internal` | Customer-facing hostname |

Replace `<PLACEHOLDERS>` throughout this guide with these values.

---

## Phase 1 — Verify VPC endpoints (each region)

The orchestrator's Lambdas have **no internet egress**. Every AWS API call
leaves through a VPC interface endpoint (or the S3 gateway endpoint). Missing
even one endpoint causes the Lambda that needs it to time out at 30s with
no useful error.

### 1.1 Required endpoints — checklist

In **each region** (`PRIMARY_REGION` and `SECONDARY_REGION`), verify these
**11 interface endpoints** exist and are attached to your private subnets:

| # | Service name (suffix) | Used by |
|---|---|---|
| 1 | `ssm` | indicator_updater (read/write SSM params), state_store |
| 2 | `sns` | executor_notify, decision_engine, SFN waitForTaskToken |
| 3 | `monitoring` | signal_collector, decision_engine (PutMetricData/GetMetricStatistics) |
| 4 | `logs` | every Lambda (CloudWatch Logs) |
| 5 | `rds` | signal_collector (DescribeGlobalClusters), executor_aurora_confirm |
| 6 | `states` | manual_trigger (StartExecution), approval_callback (SendTaskSuccess/Failure) |
| 7 | `synthetics` | signal_collector (DescribeRuns) |
| 8 | `events` | (reserved; not currently called but safer to have) |
| 9 | `lambda` | (reserved; SFN service integration uses STS not this) |
| 10 | `sts` | All Lambdas (boto3 credential resolution + cross-account roles in JPMC port) |
| 11 | `secretsmanager` | (reserved for future cert-rotation; safe to skip if you're certain you'll never use Secrets Manager) |

Plus **1 gateway endpoint**:

| # | Service | Used by |
|---|---|---|
| G1 | `s3` | profile_loader (read profile.yaml), audit writer |

### 1.2 Verify each interface endpoint

For each service in the table above, in **EC2 Console → VPC → Endpoints**
in the target region:

1. Confirm an endpoint exists with `Service name = com.amazonaws.<region>.<service>`.
2. Click it → **Subnets** tab → confirm all 3 private subnets are listed.
3. **Security groups** tab → confirm the VPCE SG (allows 443 ingress from Lambda SG) is attached.
4. **Details** tab → confirm **Private DNS names enabled = Yes** (critical — without this, boto3 won't auto-resolve to the endpoint).

### 1.3 Verify the S3 gateway endpoint

1. Find the endpoint with `Service name = com.amazonaws.<region>.s3` and `Type = Gateway`.
2. **Route tables** tab → confirm the **private subnet route table** is associated. (If S3 endpoint is missing this association, S3 traffic from Lambda goes nowhere.)
3. **Security groups** tab → does NOT apply to gateway endpoints (uses route table only).

### 1.4 Verify Lambda SG can reach the endpoints

The Lambda security group needs **two egress rules**:

1. `tcp/443 → VPCE SG` (or the VPC CIDR) — for interface endpoints.
2. `tcp/443 → pl-XXXXXX` (the S3 prefix list ID — find under VPC → Managed prefix lists, named `com.amazonaws.<region>.s3`) — for the S3 gateway endpoint.

**Without rule #2, every S3 call from Lambda hangs at 30s timeout.** This is
the most common silent failure for VPC-attached Lambdas.

### Verify gate ✓

Pick any private subnet, launch a one-shot test EC2 in it (smallest t3.nano,
Amazon Linux), SSH via SSM Session Manager, and run:

```bash
aws ssm describe-parameters --max-results 1 --region <REGION>
aws sns list-topics --region <REGION>
aws s3 ls
aws rds describe-global-clusters --region <REGION>
aws stepfunctions list-state-machines --region <REGION>
aws synthetics describe-canaries --max-results 1 --region <REGION>
```

All six should return within 1 second. If any hangs at 30s, the corresponding
endpoint is missing or misconfigured. Fix before moving to Phase 2 — every
later phase assumes these work.

---

## Phase 2 — Foundational data resources (each region)

### 2.1 KMS keys

For **each region** (do this in the region's KMS console):

1. **KMS → Customer managed keys → Create key**
2. Symmetric, encrypt/decrypt, single region
3. Alias: `<APP_NAME>-orchestrator-<region-tag>` (e.g. `myapp-orchestrator-use1`)
4. Description: `<APP_NAME> orchestrator audit + profile bucket encryption`
5. Key administrators: yourself (or your IAM admin role)
6. Key users: leave empty for now — we'll grant via bucket policy later
7. Enable automatic key rotation: ✓
8. Note the **Key ID** and **ARN**

### 2.2 S3 buckets — profile + audit (per region)

For **each region**, create two buckets:

**Profile bucket:** `<APP_NAME>-profiles-<ACCOUNT_ID>-use1` (and `-use2`)

1. **S3 → Create bucket**
2. Region matches the region you're working in
3. **Object Ownership:** Bucket owner enforced (ACLs disabled)
4. **Block all public access:** ✓ (all four checkboxes)
5. **Bucket versioning:** Enable
6. **Default encryption:** SSE-KMS, choose the KMS key from 2.1, enable Bucket Key
7. Create bucket

**Audit bucket:** `<APP_NAME>-audit-<ACCOUNT_ID>-use1` (and `-use2`)

Same as above, **plus**:
- **Object Lock:** Enable (must be enabled at creation)
- After creation: Properties → Object Lock → Edit → Default retention: GOVERNANCE, 90 days

### 2.3 Cross-region replication on profile bucket (primary → secondary)

So profile changes uploaded to primary auto-replicate to secondary:

1. Open the **primary** profile bucket → Management → Replication rules → Create
2. Rule name: `profile-to-secondary`
3. Status: Enabled
4. Source: this bucket, Apply to all objects
5. Destination: the **secondary** profile bucket
6. IAM role: Create new role (S3 will scaffold one)
7. Encryption: Replicate KMS-encrypted objects → enable, source key + destination key (the secondary's KMS key)
8. Delete marker replication: ✓
9. Save

Repeat the inverse direction (secondary → primary) so failback uploads also replicate.

### 2.4 SNS topic (per region)

For **each region**:

1. **SNS → Topics → Create topic**
2. Type: Standard
3. Name: `<APP_NAME>-failover-events`
4. Encryption: SSE-KMS, choose the region's KMS key
5. After creation, **Subscriptions → Create subscription**
   - Protocol: Email (for SRE on-call) — confirm via email
   - Optionally: SQS (for the chaos test framework's consumer)

### Verify gate ✓

```bash
aws s3 ls s3://<APP_NAME>-profiles-<ACCOUNT_ID>-use1
aws s3 ls s3://<APP_NAME>-audit-<ACCOUNT_ID>-use1
aws sns get-topic-attributes --topic-arn arn:aws:sns:us-east-1:<ACCOUNT_ID>:<APP_NAME>-failover-events
aws kms describe-key --key-id alias/<APP_NAME>-orchestrator-use1
```

All return without error. Repeat for `use2`.

---

## Phase 3 — IAM roles (one-time, account-global)

You need **3 role types** × 2 regions = ~6 roles minimum. We'll build them
once with the cross-region resource ARNs hardcoded.

### 3.1 Lambda execution role — `<APP_NAME>-lambda-use1`

1. **IAM → Roles → Create role**
2. Trusted entity: AWS service → Lambda
3. Skip permissions for now (we'll add inline)
4. Role name: `<APP_NAME>-lambda-use1`
5. Create

After creation, **Add permissions → Attach policies → AWS managed:**
- `AWSLambdaVPCAccessExecutionRole` (for ENI lifecycle in private subnets)

Then **Add permissions → Create inline policy** with this JSON
(replace `<APP>`, `<ACCOUNT>`, `<KMS_KEY_ARN_PRIMARY>`, etc.):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "logs",
      "Effect": "Allow",
      "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:us-east-1:<ACCOUNT>:log-group:/aws/lambda/<APP>-*"
    },
    {
      "Sid": "ssmIndicator",
      "Effect": "Allow",
      "Action": ["ssm:GetParameter", "ssm:GetParameters", "ssm:PutParameter"],
      "Resource": [
        "arn:aws:ssm:us-east-1:<ACCOUNT>:parameter/failover/<APP>/us-east-1/*",
        "arn:aws:ssm:us-east-1:<ACCOUNT>:parameter/failover/<APP>/us-east-2/*"
      ]
    },
    {
      "Sid": "snsPublish",
      "Effect": "Allow",
      "Action": ["sns:Publish"],
      "Resource": "arn:aws:sns:us-east-1:<ACCOUNT>:<APP>-failover-events"
    },
    {
      "Sid": "s3Profile",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:GetObjectVersion"],
      "Resource": "arn:aws:s3:::<APP>-profiles-<ACCOUNT>-use1/*"
    },
    {
      "Sid": "s3Audit",
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": "arn:aws:s3:::<APP>-audit-<ACCOUNT>-use1/*"
    },
    {
      "Sid": "kms",
      "Effect": "Allow",
      "Action": ["kms:Decrypt", "kms:GenerateDataKey"],
      "Resource": "<KMS_KEY_ARN_PRIMARY>"
    },
    {
      "Sid": "cwMetrics",
      "Effect": "Allow",
      "Action": ["cloudwatch:PutMetricData", "cloudwatch:GetMetricStatistics", "cloudwatch:GetMetricData", "cloudwatch:DescribeAlarms"],
      "Resource": "*"
    },
    {
      "Sid": "rds",
      "Effect": "Allow",
      "Action": ["rds:DescribeGlobalClusters", "rds:DescribeDBClusters", "rds:DescribeDBInstances"],
      "Resource": "*"
    },
    {
      "Sid": "synthetics",
      "Effect": "Allow",
      "Action": ["synthetics:DescribeCanaries", "synthetics:DescribeCanariesLastRun", "synthetics:GetCanaryRuns"],
      "Resource": "*"
    },
    {
      "Sid": "stepfunctions",
      "Effect": "Allow",
      "Action": ["states:StartExecution", "states:DescribeExecution", "states:SendTaskSuccess", "states:SendTaskFailure", "states:SendTaskHeartbeat"],
      "Resource": [
        "arn:aws:states:us-east-1:<ACCOUNT>:stateMachine:<APP>-failover",
        "arn:aws:states:us-east-1:<ACCOUNT>:stateMachine:<APP>-failback",
        "arn:aws:states:us-east-1:<ACCOUNT>:execution:<APP>-failover:*",
        "arn:aws:states:us-east-1:<ACCOUNT>:execution:<APP>-failback:*"
      ]
    },
    {
      "Sid": "health",
      "Effect": "Allow",
      "Action": ["health:DescribeEvents", "health:DescribeAffectedEntities"],
      "Resource": "*"
    }
  ]
}
```

**Note:** `cloudwatch:*` and `rds:*` and `health:*` and `synthetics:*` use
`Resource: "*"` because the AWS APIs don't support resource-level scoping
for these read actions. This is documented in the policy itself for
auditors.

Repeat for `<APP_NAME>-lambda-use2` with `us-east-2` substituted everywhere.

### 3.2 Step Functions execution role — `<APP_NAME>-sfn-use1`

1. Create role, trusted entity: AWS service → Step Functions
2. Skip permissions
3. Name: `<APP_NAME>-sfn-use1`
4. Inline policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "invokeOrchestratorLambdas",
      "Effect": "Allow",
      "Action": ["lambda:InvokeFunction"],
      "Resource": [
        "arn:aws:lambda:us-east-1:<ACCOUNT>:function:<APP>-*",
        "arn:aws:lambda:us-east-2:<ACCOUNT>:function:<APP>-*"
      ]
    },
    {
      "Sid": "publishToSnsForTaskToken",
      "Effect": "Allow",
      "Action": ["sns:Publish"],
      "Resource": "arn:aws:sns:us-east-1:<ACCOUNT>:<APP>-failover-events"
    },
    {
      "Sid": "logsForExecutionData",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogDelivery", "logs:GetLogDelivery", "logs:UpdateLogDelivery",
        "logs:DeleteLogDelivery", "logs:ListLogDeliveries", "logs:PutResourcePolicy",
        "logs:DescribeResourcePolicies", "logs:DescribeLogGroups"
      ],
      "Resource": "*"
    }
  ]
}
```

Repeat for `<APP_NAME>-sfn-use2` substituting `us-east-2`.

### 3.3 EventBridge → Lambda invoke (no role needed)

EventBridge invokes Lambda via resource-based policy, not an IAM role.
We'll add the resource policy in Phase 6.

### 3.4 Synthetics canary role — `<APP_NAME>-canary-use1`

1. Create role, trusted entity: AWS service → Lambda (yes, Lambda — Synthetics uses Lambda under the hood)
2. Attach AWS managed: `CloudWatchSyntheticsExecutionRolePolicy`
3. Add inline policy granting writes to your audit bucket:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetBucketLocation"],
      "Resource": "arn:aws:s3:::<APP>-audit-<ACCOUNT>-use1/canary/*"
    }
  ]
}
```

Repeat for `-use2`.

### Verify gate ✓

```bash
aws iam get-role --role-name <APP>-lambda-use1
aws iam list-attached-role-policies --role-name <APP>-lambda-use1
aws iam list-role-policies --role-name <APP>-lambda-use1
```

Expect: VPC access managed policy + your inline policy.

---

## Phase 4 — Lambda layer + functions (each region)

### 4.1 Build the deps layer (one-time, account-global)

The orchestrator Lambdas import `pyyaml`, `pydantic`, and `jsonschema`. None
of these are pre-installed in the Lambda Python runtime. Bundle them in a
layer.

On a Linux machine (or a Linux container — graphviz/pydantic have native deps):

```bash
mkdir -p layer/python
pip install --target layer/python --platform manylinux2014_x86_64 --implementation cp --python-version 3.13 --only-binary=:all: pyyaml==6.0.2 pydantic==2.9.2 jsonschema==4.23.0
cd layer && zip -r ../deps-layer.zip python && cd ..
```

In **each region**:

1. **Lambda → Layers → Create layer**
2. Name: `<APP>-deps`
3. Upload `deps-layer.zip`
4. Compatible runtimes: Python 3.13
5. Compatible architectures: x86_64
6. Create
7. Note the **Layer ARN** (you'll attach it to every function)

### 4.2 Build the function packages (one-time, per release)

The repo's source is in `lambdas/<name>/` and `lib/`. For each of the 10
function names below, build a zip:

```bash
# From repo root
APP=myapp
mkdir -p builds
for fn in signal_collector decision_engine indicator_updater manual_trigger \
          approval_callback executor_precheck executor_notify \
          executor_flip_r53_metric executor_aurora_confirm executor_postcheck; do
  rm -rf /tmp/build-$fn && mkdir -p /tmp/build-$fn
  # All Lambdas need every other lambda's source for cross-module imports
  cp -r lambdas/ /tmp/build-$fn/lambdas
  cp -r lib/ /tmp/build-$fn/lib
  mkdir -p /tmp/build-$fn/profiles && cp profiles/profile.schema.json /tmp/build-$fn/profiles/
  (cd /tmp/build-$fn && zip -r $OLDPWD/builds/$fn.zip .)
done
ls -lh builds/
```

You'll have 10 zip files of ~30KB each.

### 4.3 Create each Lambda function (per region, ×10)

For **each of the 10 functions**, in **each region**:

1. **Lambda → Create function → Author from scratch**
2. Function name: `<APP>-<fn>-use1` (e.g. `myapp-signal_collector-use1`). Use the underscore in the function name — that's what the SFN ARNs reference.
3. Runtime: **Python 3.13**
4. Architecture: **x86_64**
5. Permissions: Use existing role → `<APP>-lambda-use1`
6. **Advanced settings → VPC:** select the VPC, all 3 private subnets, the Lambda SG
7. Create

After creation, do these in order:

1. **Code → Upload from .zip → upload `builds/<fn>.zip`**
2. **Code → Runtime settings → Edit → Handler:** `lambdas.<fn>.handler.lambda_handler`
   (Note: dotted path, NOT slashes. e.g. `lambdas.signal_collector.handler.lambda_handler`)
3. **Configuration → General configuration → Edit:**
    - Memory: 256 MB
    - Timeout: 30 seconds (60 seconds for `executor_aurora_confirm`)
    - **Active tracing:** disable (the syn-python-selenium 10.0 runtime doesn't support it; the orchestrator Lambdas don't need it for POC)
4. **Configuration → Layers → Add a layer → Custom layers → `<APP>-deps`**
5. **Configuration → Environment variables → Edit:** add the variables in the table below. The endpoint URLs come from the VPC endpoint Console — Endpoint → Details tab → "DNS names" → use the **regional** entry, NOT the AZ-specific ones.

| Key | Value |
|---|---|
| `APP_NAME` | `<APP>` |
| `PROFILE_BUCKET` | `<APP>-profiles-<ACCOUNT>-use1` |
| `PROFILE_KEY` | `<APP>/profile.yaml` |
| `AUDIT_BUCKET` | `<APP>-audit-<ACCOUNT>-use1` |
| `SNS_TOPIC_ARN` | `arn:aws:sns:us-east-1:<ACCOUNT>:<APP>-failover-events` |
| `FAILOVER_STATE_MACHINE_ARN` | `arn:aws:states:us-east-1:<ACCOUNT>:stateMachine:<APP>-failover` |
| `FAILBACK_STATE_MACHINE_ARN` | `arn:aws:states:us-east-1:<ACCOUNT>:stateMachine:<APP>-failback` |
| `LOG_LEVEL` | `INFO` |
| `ENDPOINT_SSM` | `https://vpce-XXXX.ssm.<region>.vpce.amazonaws.com` |
| `ENDPOINT_SNS` | `https://vpce-XXXX.sns.<region>.vpce.amazonaws.com` |
| `ENDPOINT_S3` | `https://s3.<region>.amazonaws.com` (gateway endpoint uses public URL, route table redirects) |
| `ENDPOINT_CLOUDWATCH` | `https://vpce-XXXX.monitoring.<region>.vpce.amazonaws.com` |
| `ENDPOINT_LOGS` | `https://vpce-XXXX.logs.<region>.vpce.amazonaws.com` |
| `ENDPOINT_RDS` | `https://vpce-XXXX.rds.<region>.vpce.amazonaws.com` |
| `ENDPOINT_STEPFUNCTIONS` | `https://vpce-XXXX.states.<region>.vpce.amazonaws.com` |
| `ENDPOINT_SYNTHETICS` | `https://vpce-XXXX.synthetics.<region>.vpce.amazonaws.com` |
| `ENDPOINT_HEALTH` | `https://health.us-east-1.amazonaws.com` (Health is global; uses us-east-1 endpoint always) |
| `ENDPOINT_EVENTS` | `https://vpce-XXXX.events.<region>.vpce.amazonaws.com` |
| `ENDPOINT_LAMBDA` | `https://vpce-XXXX.lambda.<region>.vpce.amazonaws.com` |

Repeat all 10 functions in **us-east-2** with `-use2` suffixes and `us-east-2` ARNs/endpoints.

### 4.4 Smoke test each function

For **each function**, **Test → New event:**

```json
{"app_name": "<APP>", "dry_run": true}
```

You're not validating logic yet — you're validating that:
- Cold start completes (no `Runtime.ImportModuleError`)
- The function reaches some code that runs (even if it then errors on missing keys)

Common failures and fixes:

| Symptom | Fix |
|---|---|
| `Runtime.ImportModuleError: No module named 'yaml'` | Layer not attached or wrong arch |
| Timeout at 30s, no logs | VPC endpoint missing or Lambda SG egress doesn't allow it |
| `botocore.exceptions.ClientError: ... no credentials` | Lambda execution role not assigned |
| `[Errno 2] No such file: /var/task/profiles/profile.schema.json` | Schema not bundled in zip — rebuild with the schema copy step |

### Verify gate ✓

All 20 functions (10 × 2 regions) cold-start without ImportModuleError.

---

## Phase 5 — Step Functions state machines (each region)

You need **4 state machines:** failover + failback, in each region.

### 5.1 ASL definitions

The JSON definitions are in `statemachines/failover.asl.json` and
`statemachines/failback.asl.json`. They contain `${...}` template variables
that need substitution before pasting into the console.

For each region, prepare 2 substituted definitions. Variables to replace:

| Template var | Substitute with |
|---|---|
| `${precheck_lambda_arn}` | `arn:aws:lambda:<region>:<ACCOUNT>:function:<APP>-executor_precheck-use1` (or use2) |
| `${notify_lambda_arn}` | `arn:aws:lambda:<region>:<ACCOUNT>:function:<APP>-executor_notify-...` |
| `${indicator_updater_source_lambda_arn}` | The same-region indicator_updater (POC simplification — both indicators stored in this region's SSM) |
| `${indicator_updater_target_lambda_arn}` | Also the same-region indicator_updater (same simplification) |
| `${flip_r53_metric_lambda_arn}` | `<APP>-executor_flip_r53_metric-...` |
| `${aurora_confirm_lambda_arn}` | `<APP>-executor_aurora_confirm-...` |
| `${postcheck_lambda_arn}` | `<APP>-executor_postcheck-...` |
| `${sns_topic_arn}` | `arn:aws:sns:<region>:<ACCOUNT>:<APP>-failover-events` |

Tip: do this in a text editor with Find & Replace. **Do not** modify any
other JSON content (especially the `Choices`, `Parameters`, or `Catch`
arrays — they're load-bearing).

### 5.2 Create state machine

In **each region**, **for failover then failback:**

1. **Step Functions → State machines → Create**
2. Choose: **Write your workflow in code**
3. Type: **Standard** (NOT Express — the Aurora gate uses `.waitForTaskToken` which Express doesn't support cleanly)
4. Paste your substituted JSON definition
5. Click "Next" — Workflow Studio renders it; verify the visual graph matches the docs/diagrams/05-failover-statemachine.md picture
6. Name: `<APP>-failover` (or `<APP>-failback`). Use this exact name — Lambda env vars reference it
7. Permissions: Use existing role → `<APP>-sfn-use1` (or use2)
8. Logging: enabled, log level ALL, include execution data: ✓
9. Tracing: optional
10. Create

### 5.3 Smoke test

For the failover state machine, **Start execution** with input:

```json
{
  "failover_id": "smoke-test-1",
  "app_name": "<APP>",
  "direction": "dryrun",
  "source_region": "us-east-1",
  "target_region": "us-east-2",
  "operator": "smoke-test",
  "requested_at": "2026-04-28T00:00:00+00:00",
  "dry_run": true,
  "profile_snapshot": {
    "components": {"api_gateway": false, "aurora": false, "elasticache": false, "kafka_consumer": false},
    "aurora_manual_approval_required": false,
    "dns_first_failover": true,
    "drain_seconds": 5,
    "quiesce_seconds": 5,
    "r53_propagation_seconds": 5,
    "aurora_confirm_timeout_minutes": 30
  }
}
```

This is a dry-run with aurora disabled — should reach `STABLE_SECONDARY` in
~30 seconds with every Lambda emitting `dry_run_action_skipped` log lines.

### Verify gate ✓

The smoke-test execution shows green `STABLE_SECONDARY` end state. If it
fails on a specific state, click that state in the visual graph → input/output
panel shows what blew up.

---

## Phase 6 — EventBridge schedules (each region)

Two rules per region: one for `signal_collector` (1 min), one for `decision_engine` (1 min).

For each rule, in **each region**:

1. **EventBridge → Rules → Create rule**
2. Name: `<APP>-signal-collector-use1` (or `decision-engine`, `-use2`)
3. Event bus: default
4. Rule type: **Schedule**
5. Schedule pattern: rate `1 minute`
6. Target: AWS service → Lambda function → `<APP>-signal_collector-use1` (match the Lambda)
7. Configure target input: **Constant (JSON):**
   ```json
   {"app_name": "<APP>"}
   ```
8. Create

EventBridge will auto-add the `lambda:InvokeFunction` resource policy on
the function.

### Verify gate ✓

Wait 2 minutes. Open CloudWatch Logs → `/aws/lambda/<APP>-signal_collector-use1`
→ confirm a fresh log stream every minute, with `signal_collected` events.
Same for decision_engine.

---

## Phase 7 — CloudWatch alarms (each region)

The orchestrator's R53 control mechanism depends on **one alarm per region**:

### 7.1 PrimaryHealthControl alarm (per region)

1. **CloudWatch → Alarms → Create alarm**
2. Select metric: **Browse → Custom namespaces → `Failover/<APP>`** → `PrimaryHealthControl` with dimension `Region = us-east-1`
3. Statistic: Maximum
4. Period: 1 minute
5. Threshold type: Static, **Lower than 0.5**
6. Datapoints: 1 out of 1
7. Treat missing data as: **Missing** (NOT breaching — important: missing data must not trip the alarm)
8. Notification: leave empty for now (R53 health check reads alarm state directly, not via SNS)
9. Name: `<APP>-PrimaryHealthControl-use1`
10. Create

Repeat for `us-east-2`.

### 7.2 Bootstrap the metric

Brand-new alarms are in `INSUFFICIENT_DATA` until the metric exists. Seed
with one healthy datapoint:

```bash
aws cloudwatch put-metric-data --namespace "Failover/<APP>" \
  --metric-data MetricName=PrimaryHealthControl,Value=1.0,Unit=None,Dimensions=[{Name=Region,Value=us-east-1}] \
  --region us-east-1
```

Wait 1 minute, refresh the alarm — should be `OK`.

### Verify gate ✓

Both alarms in `OK` state.

---

## Phase 8 — Synthetics canaries (each region)

**Important constraint** (CLAUDE.md §11 #4): the canary in `us-east-2`
probes the **`us-east-1` public URL**, and vice versa. If a canary lives in
the same region as its target, it can't survive the failure mode it's
supposed to detect.

### 8.1 Create canary in us-east-2 (probes us-east-1)

1. **CloudWatch → Synthetics → Create canary**
2. Blueprint: **Heartbeat monitoring**
3. Name: `<APP>-canary-from-use2-probes-use1`
4. Application or endpoint URL: `<APP_PUBLIC_URL_PRIMARY>`
5. Runtime version: **syn-python-selenium-10.0**
6. Schedule: every 1 minute
7. Timeout: 30 seconds
8. Data retention: 31 days success, 31 days failure
9. **S3 location:** `s3://<APP>-audit-<ACCOUNT>-use2/canary/`
10. **IAM role:** `<APP>-canary-use2`
11. **Active tracing:** disable (10.0 doesn't support)
12. **VPC:** the secondary VPC + private subnets + Lambda SG
13. **Environment variables:** `IGNORE_TLS_ERRORS=true` (POC self-signed cert)
14. Create

### 8.2 Mirror canary in us-east-1 (probes us-east-2)

Same as above but **flip every region reference**.

### Verify gate ✓

Wait 3 minutes. Both canaries showing **success** (or expected failures
matching what their target is doing). Logs in CloudWatch Logs at
`/aws/lambda/cwsyn-<canary-name>-XXX`.

---

## Phase 9 — Route 53 health check + failover record

This wires the alarm → R53 → DNS.

### 9.1 Health check

1. **Route 53 → Health checks → Create health check**
2. Name: `<APP>-primary-health-control`
3. Monitor: **CloudWatch alarm**
4. State of: `<APP>-PrimaryHealthControl-use1` in `us-east-1`
5. Health check status: **Healthy when alarm is `OK`** (alarm `ALARM` = unhealthy → R53 fails over)
6. Inverted: ✗
7. Create

### 9.2 Failover record

1. **Route 53 → Hosted zone `<R53_HOSTED_ZONE_ID>` → Create record**
2. Record name: `<R53_RECORD_NAME>` (e.g. `myapp.example.internal`)
3. Record type: A (alias)
4. Routing policy: **Failover**
5. **Primary record:**
   - Failover record type: Primary
   - Endpoint: alias → your application's NLB / ALB / regional endpoint in `us-east-1`
   - Health check: `<APP>-primary-health-control`
   - Record ID: `<APP>-primary`
6. Create.
7. **Create another record** (same name and type):
   - Failover record type: Secondary
   - Endpoint: alias → application endpoint in `us-east-2`
   - Health check: leave none
   - Record ID: `<APP>-secondary`

### Verify gate ✓

```bash
dig <R53_RECORD_NAME>
```

Should resolve to the primary endpoint. Now manually trip the metric:

```bash
aws cloudwatch put-metric-data --namespace "Failover/<APP>" \
  --metric-data MetricName=PrimaryHealthControl,Value=0.0,Unit=None,Dimensions=[{Name=Region,Value=us-east-1}] \
  --region us-east-1
```

Wait 90 seconds, `dig` again — should now resolve to the secondary endpoint.

Reset:

```bash
aws cloudwatch put-metric-data --namespace "Failover/<APP>" \
  --metric-data MetricName=PrimaryHealthControl,Value=1.0,Unit=None,Dimensions=[{Name=Region,Value=us-east-1}] \
  --region us-east-1
```

DNS returns to primary in another 90s.

---

## Phase 10 — Profile + end-to-end test

### 10.1 Upload the profile

The profile defines per-app behavior (signal sources, thresholds, gates, etc.).
The full schema is in `profiles/profile.schema.json`; an example for the test
harness is in `profiles/test-app.yaml`.

Adapt for your app, then:

```bash
aws s3 cp profiles/<your-app>.yaml \
  s3://<APP>-profiles-<ACCOUNT>-use1/<APP>/profile.yaml
```

CRR will replicate to the secondary bucket within 60 seconds.

### 10.2 End-to-end smoke test

1. **Wait 2 minutes** — let the EventBridge schedules tick once each.
2. **Inspect SSM:** `aws ssm get-parameters-by-path --path /failover/<APP>/ --region us-east-1` — should see `decision` (whatever the engine evaluated).
3. **Inspect S3 audit:** `aws s3 ls s3://<APP>-audit-<ACCOUNT>-use1/observations/` — should see one snapshot per minute.
4. **Trigger a dry-run failover:**
   ```bash
   aws lambda invoke --function-name <APP>-manual_trigger-use1 \
     --payload '{"direction":"dryrun","operator":"smoke","dry_run":true}' \
     --cli-binary-format raw-in-base64-out /tmp/out.json
   cat /tmp/out.json
   ```
   Expect: `{"ok": true, "execution_arn": "..."}`.
5. **Watch the SFN execution** in the console — should reach STABLE_SECONDARY.
6. **Verify no real mutation:** the SSM `role` parameter should NOT exist (dry-run skips writes).

### Verify gate ✓

End-to-end dry-run passes. The orchestrator is live.

---

## Going to production

You've now got a working orchestrator with `auto_failover=false` (the
default — operator decides). Per SPEC §4.3, leave it like that for the
first **30 days** to characterize your app's signal noise floor. During
this period:

- Every alarm is investigated (genuine red? false positive?)
- Profile thresholds (`tier1_quorum`, `dwell_minutes`) tuned based on observed noise
- Operators run `dry-run` and `failover` manually a few times to learn the runbooks

After 30 days, flip `auto_failover: true` in the profile and re-upload. The
orchestrator now triggers on its own when the four-gate rule holds.

---

## Maintenance items

- **Lambda code updates:** rebuild the zip per Phase 4.2, upload via Lambda console (Code → Upload from .zip). The `source_code_hash` will change automatically.
- **Profile changes:** edit and re-upload to the **primary** profile bucket; CRR replicates to secondary.
- **Adding a new app:** repeat Phases 2-9 with a new `<APP_NAME>`. The orchestrator is one-app-per-deployment.
- **Failover drills:** run `failoverctl failover --dry-run` quarterly. Promote to a real failover during a planned maintenance window once a year.

---

## Troubleshooting catalog

| Symptom | Likely cause |
|---|---|
| Lambda timeout 30s, no useful log | Missing or misconfigured VPC endpoint, OR Lambda SG egress doesn't permit S3 prefix list |
| `Runtime.ImportModuleError: No module named 'yaml'` | Layer not attached, or layer built for wrong architecture |
| `[Errno 2] No such file: profiles/profile.schema.json` | Schema not bundled in Lambda zip — rebuild with copy step |
| SFN execution fails on `PROMOTE_SECONDARY_INDICATOR` with "Functions from 'us-east-2' are not reachable" | SFN can't cross-region invoke Lambda. Use the POC simplification: same-region indicator updater for both source and target. |
| R53 not flipping | Alarm in `INSUFFICIENT_DATA` (need to seed metric); or health check not actually attached to primary record |
| Aurora gate hangs forever | `executor_aurora_confirm` Lambda needs `rds:DescribeGlobalClusters` IAM perm; OR Aurora hasn't actually been promoted yet (operator hasn't approved) |
| Decision engine never goes red | Profile `tier1_quorum` higher than the number of red signals; check observation snapshots in audit S3 |
| Dry-run actually mutates | Lambda `dry_run` event flag not propagated through SFN input — verify the SFN definition's Parameters include `"dry_run.$": "$.dry_run"` |

---

_Last reviewed: 2026-04-28._
