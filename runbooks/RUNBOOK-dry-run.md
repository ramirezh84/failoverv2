# Dry run

**Audience:** SRE on-call.

## When to use

You want to validate the orchestrator end-to-end without changing any state. Useful before a real failover, or as a periodic exercise.

## Prerequisites

- AWS profile `tbed`. `make harness-up` complete.

## Procedure

1. Trigger: `failoverctl dryrun test-app --operator $USER`.
2. Watch SNS — every event should be subject-prefixed `[DRY-RUN]`.
3. Watch Step Functions — every Lambda emits `dry_run_action_skipped` instead of mutating SSM/R53/Aurora.
4. Read the `executor-runs/` audit object; it should record `dry_run: true`.

## Verification

- No SSM /failover/{app}/{region}/role parameter changes.
- No CloudWatch metric emit of PrimaryHealthControl.
- No Aurora promotion attempt.
- Step Functions execution status: SUCCEEDED.

## Rollback

_(none)_

## Escalation

- Dry-run failures are bugs. File an issue.

_Last reviewed: 2026-04-27._
