# API Reference

**Audience:** CLI / automation users.

Every operator-facing Lambda's input payload and output format. Inputs are
validated server-side; bad input returns a non-2xx Lambda invocation result
with an error message.

## `manual_trigger`

**Function name:** `<app>-manual_trigger-{use1|use2}`

**Input:**

```json
{
  "direction": "failover" | "failback" | "dryrun",
  "operator": "ramirezh84",
  "target_region": "us-east-2",
  "dry_run": false
}
```

`target_region` is optional; if provided, must match the profile's
`secondary_region` (failover) or `primary_region` (failback). `dry_run`
is implicit `true` for `direction=dryrun`.

**Output:**

```json
{
  "ok": true,
  "execution_arn": "arn:aws:states:us-east-1:...:execution:test-app-failover:failover-test-app-...",
  "execution_name": "failover-test-app-20260427-failover-000-abc1",
  "input": { ... }
}
```

If an execution with the same name already exists (idempotency):

```json
{
  "ok": true,
  "duplicate": true,
  "execution_name": "...",
  "message": "An execution with this name already exists; returning idempotently."
}
```

## `approval_callback`

**Function name:** `<app>-approval_callback-{use1|use2}`

**Input:**

```json
{
  "task_token": "<base64 from the AURORA_GATE_PAUSE SNS message>",
  "decision": "approve" | "abort",
  "operator": "ramirezh84",
  "reason": "Aurora secondary promoted via console; writer confirmed."
}
```

**Output:**

```json
{ "ok": true, "decision": "approve", "operator": "ramirezh84" }
```

## `indicator_updater`

**Function name:** `<app>-indicator_updater-{use1|use2}`

**Input:** (called by the state machine; operators rarely invoke directly)

```json
{
  "app_name": "test-app",
  "region": "us-east-1",
  "role": "DRAINING" | "ACTIVE" | "PASSIVE",
  "executor_run_id": "failover-...",
  "sequence": 1,
  "dry_run": false
}
```

**Output:**

```json
{
  "ok": true,
  "role": "DRAINING",
  "region": "us-east-1",
  "executor_run_id": "...",
  "sequence": 1
}
```

## `signal_collector`

EventBridge-driven; rarely invoked by hand. Returns:

```json
{
  "ok": true,
  "tier1_red": ["outer_nlb_unhealthy"],
  "tier2_red": [],
  "tier3_red": [],
  "timestamp": "2026-04-27T12:00:00Z"
}
```

## `decision_engine`

EventBridge-driven. Returns:

```json
{
  "ok": true,
  "state": "GREEN" | "WATCHING" | "FAILOVER_AUTHORIZED" | "FAILOVER_AUTHORIZED_BUT_NOT_AUTO" | "FAILOVER_AUTHORIZED_BUT_UNSAFE",
  "failover_authorized": true,
  "red_signals": ["outer_nlb_unhealthy", "cross_region_canary_fail"]
}
```

## Step Functions input/output

The state machine's input is what `manual_trigger` returns under `input`:

```json
{
  "failover_id": "failover-test-app-20260427-failover-000-abc1",
  "app_name": "test-app",
  "direction": "failover",
  "source_region": "us-east-1",
  "target_region": "us-east-2",
  "operator": "ramirezh84",
  "requested_at": "2026-04-27T12:00:00+00:00",
  "dry_run": false,
  "profile_snapshot": { ... }
}
```

Each state appends its result under a per-state key (e.g. `$.precheck`,
`$.flip_r53`). The terminal `STABLE_SECONDARY` succeeds with the full
accumulated state available via `GetExecutionHistory`.

## Error codes

Lambda errors propagate as the standard Lambda invoke `FunctionError`
field. Common errors:

| Error | Cause | Recovery |
|---|---|---|
| `ValueError` (direction must be) | `manual_trigger` called with bad direction | Use `failover|failback|dryrun` |
| `ExecutionAlreadyExists` | Same `failover_id` used twice | Idempotent — returns the existing execution |
| `OperatorAbort` | `approval_callback` with `decision=abort` | Expected; state machine routes to FAIL |
| `States.Timeout` | Aurora gate timed out | See `RUNBOOK-stuck-state-machine.md` |

_Last reviewed: 2026-04-27._
