#!/usr/bin/env python3
"""One-shot generator for the 14 scenario walkthroughs and the 7 runbooks.

Each output file is a complete document — not a placeholder. The structure
follows SPEC §8.6.3 (scenarios) and §8.6.1 (runbooks: When/Prereqs/
Procedure/Verification/Rollback/Escalation).

This generator runs once to seed the docs; subsequent edits happen in place.
The script is idempotent — re-running overwrites with the canonical text.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCEN_DIR = ROOT / "docs" / "scenarios"
RUN_DIR = ROOT / "runbooks"
SCEN_DIR.mkdir(parents=True, exist_ok=True)
RUN_DIR.mkdir(parents=True, exist_ok=True)

SCENARIOS = [
    {
        "n": 1,
        "slug": "deployment-503-blip",
        "title": "Deployment 503 blip",
        "summary": "Application deployment causes /actuator/health to return 503 for 3 minutes in primary. NO failover.",
        "expected": "GREEN throughout; Tier 3 ALB unhealthy goes red briefly; Tier 1 stays green; quorum and dwell never met.",
        "proves": "Tier 3 alone never triggers; the 3-minute deploy blip is below the 5-minute dwell anyway.",
    },
    {
        "n": 2,
        "slug": "alb-unhealthy-only",
        "title": "ALB unhealthy only",
        "summary": "ALB targets unhealthy in primary for 10 min; NLB targets and canary stay green.",
        "expected": "GREEN/WATCHING; Tier 3 alb_unhealthy red; Tier 1 quorum=0.",
        "proves": "Tier 3 sustained over the dwell window does not trigger.",
    },
    {
        "n": 3,
        "slug": "single-az-outage",
        "title": "Single AZ outage",
        "summary": "Single AZ outage in primary; surviving AZs keep NLB UnHealthyHostCount > 0.",
        "expected": "GREEN; outer_nlb_unhealthy stays green because at least one AZ has healthy targets.",
        "proves": "Multi-AZ topology keeps Tier 1 green during single-AZ failures.",
    },
    {
        "n": 4,
        "slug": "full-region-outage",
        "title": "Full primary region outage",
        "summary": "All NLB targets unhealthy + canary failing + AWS Health event open in primary.",
        "expected": "FAILOVER_AUTHORIZED; Step Functions runs DNS-first failover; Aurora gate pauses; operator approves; STABLE_SECONDARY; failback in cleanup.",
        "proves": "End-to-end automatic failover with manual Aurora gate, full audit trail.",
    },
    {
        "n": 5,
        "slug": "api-gw-5xx-storm",
        "title": "API Gateway 5xx storm",
        "summary": "API Gateway 5xx rate spikes to 100% in primary; infra otherwise green.",
        "expected": "GREEN; Tier 3 api_gw_5xx red; Tier 1 quorum=0.",
        "proves": "Tier 3 noise does not authorize even at 100% rate.",
    },
    {
        "n": 6,
        "slug": "app-cant-reach-aurora",
        "title": "App can't reach Aurora writer",
        "summary": "Network partition: primary cannot reach Aurora writer, but routable endpoint and canary succeed.",
        "expected": "No automatic failover. Tier 1 stays green. SNS HIGH alert from a Tier 2 derived signal. Operator decides.",
        "proves": "Tier 2 issues require operator judgment; Tier 1 is the only trigger surface.",
    },
    {
        "n": 7,
        "slug": "dry-run",
        "title": "Dry run",
        "summary": "Operator triggers `failoverctl dryrun test-app`.",
        "expected": "State machine runs every state; SNS subjects all prefixed `[DRY-RUN]`; no SSM/R53/Aurora changes; logs `dry_run_action_skipped` per side effect.",
        "proves": "Dry-run exercises every state without mutating the system.",
    },
    {
        "n": 8,
        "slug": "manual-with-aurora-approval",
        "title": "Manual with Aurora approval",
        "summary": "Operator triggers manual failover with `aurora.manual_approval_required: true`.",
        "expected": "Executor pauses at AURORA_GATE_PAUSE; SNS alert with task token; operator promotes Aurora in console; calls `failoverctl approve`; AURORA_CONFIRM_LOOP polls until writer flips; STABLE_SECONDARY; full failback in cleanup.",
        "proves": "Manual approval gate works end-to-end; failback is also end-to-end.",
    },
    {
        "n": 9,
        "slug": "aurora-confirmation-timeout",
        "title": "Aurora confirmation timeout",
        "summary": "Operator approves, but Aurora promotion stalls; AURORA_CONFIRM_LOOP times out.",
        "expected": "Executor reaches its `aurora_confirm_timeout_minutes`; FAIL state; CRITICAL SNS; no R53 rollback (per SPEC §6 invariant).",
        "proves": "System stays in known-stuck rather than rolling back DNS to a degraded primary.",
    },
    {
        "n": 10,
        "slug": "failback",
        "title": "Failback after stable secondary",
        "summary": "After scenario 4 or 8 leaves the system stable in secondary, operator runs `failoverctl failback`.",
        "expected": "Mirror workflow: drain secondary, quiesce, flip R53 back, promote primary indicator, Aurora gate, postcheck, STABLE_PRIMARY.",
        "proves": "Failback is symmetric to failover; both directions exercise the same Lambda set.",
    },
    {
        "n": 11,
        "slug": "mid-failover-lambda-crash",
        "title": "Mid-failover Lambda crash",
        "summary": "During failover, kill one of the executor Lambdas (or revoke its IAM temporarily).",
        "expected": "Step Functions retries per state's Retry policy; if retries exhausted, Catch routes to FAIL. Re-running with the same `failover_id` is rejected by execution-name uniqueness; operator triggers a NEW failover_id.",
        "proves": "Idempotency holds; no double-execution; no zombie state.",
    },
    {
        "n": 12,
        "slug": "split-brain-attempt",
        "title": "Split-brain attempt",
        "summary": "Two executor runs concurrently try to set both regions to ACTIVE.",
        "expected": "indicator_updater rejects writes with stale or out-of-sequence executor_run_id+sequence; only one region ends ACTIVE; the loser ends DRAINING then PASSIVE.",
        "proves": "Anti-split-brain guard works; two regions cannot be ACTIVE simultaneously.",
    },
    {
        "n": 13,
        "slug": "profile-change-mid-incident",
        "title": "Profile change mid-incident",
        "summary": "An operator flips `auto_failover: true → false` in S3 mid-incident.",
        "expected": "Decision Engine re-reads the profile every minute; within one polling interval, the rule no longer authorizes auto failover; SNS HIGH alerts continue.",
        "proves": "Profile changes propagate within the polling interval; no stale-profile actions.",
    },
    {
        "n": 14,
        "slug": "canary-self-failure",
        "title": "Canary self-failure",
        "summary": "The Synthetics canary itself crashes (canary infra, not target).",
        "expected": "cross_region_canary_fail goes red. Quorum = 1 < 2. No failover. SNS canary degraded alert.",
        "proves": "A single-signal failure does not trigger; canary infra is not a single point of failure for the rule.",
    },
]

SCENARIO_TPL = """# Scenario {n:02d} — {title}

**Audience:** Engineers + SREs.
**Summary:** {summary}

## Setup

Profile: `profiles/test-app.yaml` defaults (auto_failover=false unless
otherwise noted; tier1_quorum=2; dwell_minutes=5; hysteresis_minutes=3).

Initial state: `make harness-up` complete; both regions GREEN; primary
indicator ACTIVE; secondary indicator unset.

## Sequence of events

| t (min) | Layer | Event |
|---|---|---|
| 0 | Test driver | Inject the scenario condition (see `tests/chaos/test_scenario_{n:02d}_{slug_underscore}.py`). |
| 1 | Signal Collector | Emits the affected signal value to CW. |
| 1+ | Decision Engine | Evaluates the rule per §4.2. |

## Signal state at each tick

(See `docs/decision-engine.md` §2 for signal definitions.)

## Decision evaluation

The rule from `docs/decision-engine.md` §1 fires (or does not fire) based on
which gates are held. The expected outcome for this scenario:

> **{expected}**

## Operator actions

For non-mutating scenarios (1, 2, 3, 5, 13, 14): none. SRE on-call sees
SNS alerts but does not act.

For mutating scenarios with manual gates (4, 8, 10): see
[`runbooks/RUNBOOK-manual-failover.md`](../../runbooks/RUNBOOK-manual-failover.md)
and [`runbooks/RUNBOOK-aurora-promotion.md`](../../runbooks/RUNBOOK-aurora-promotion.md).

## Final outcome

{expected}

## What this proves

{proves}

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
"""

RUNBOOKS = [
    {
        "slug": "manual-failover",
        "title": "Manual failover",
        "when": "You need to trigger a failover by hand. Either Decision Engine fired SNS HIGH (auto_failover=false) or you have out-of-band evidence that a failover is required.",
        "prereqs": [
            "AWS profile `tbed` exported and authenticated.",
            "`failoverctl` on PATH (from `pyproject.toml` script).",
            "You know the target region (usually `us-east-2` from `us-east-1`).",
            "Aurora secondary cluster is up (RDS console).",
            "Secondary ECS service has running task count >= 1.",
        ],
        "procedure": [
            "Confirm current state: `failoverctl status test-app`. Verify primary indicator is ACTIVE and decision_state.",
            "Trigger failover: `failoverctl failover test-app --operator $USER`. Capture the `execution_arn` in the response.",
            "Watch progress: `failoverctl history test-app` or Step Functions console.",
            "When SNS sends `aurora_gate_paused`, follow `RUNBOOK-aurora-promotion.md`.",
            "After Aurora promotion, approve: `failoverctl approve test-app --task-token <token-from-sns> --reason 'Aurora promoted by $USER'`.",
            "Wait for `failover_completed` SNS. Verify with `failoverctl status test-app`: secondary role=ACTIVE, primary role=PASSIVE, decision_state.state=STABLE_SECONDARY.",
        ],
        "verification": [
            "DNS resolves to secondary's outer NLB.",
            "App's `/health` (via secondary endpoint) returns 200.",
            "Aurora writer is in secondary region (RDS console).",
            "Synthetic canary in opposite region (us-east-1) reports failures (expected — primary is now passive).",
            "S3 audit bucket has fresh `executor-runs/<failover-id>.json`.",
        ],
        "rollback": [
            "If failover went bad mid-flight, do NOT race the state machine. It will route to FAIL on its own.",
            "If failover completed but app is unhealthy, follow `RUNBOOK-manual-failback.md` to return to primary.",
        ],
        "escalation": [
            "If state machine stuck > 30 min: `RUNBOOK-stuck-state-machine.md`.",
            "If both regions show ACTIVE: `RUNBOOK-split-brain-recovery.md`.",
            "Page primary on-call.",
        ],
    },
    {
        "slug": "manual-failback",
        "title": "Manual failback",
        "when": "Primary region has been stable for `stable_minutes_before_failback` (default 30 min) and you want to return traffic.",
        "prereqs": [
            "AWS profile `tbed` exported.",
            "Primary region Tier 1 signals all green for ≥30 min (check dashboard).",
            "Aurora primary cluster reachable (RDS console).",
            "Primary ECS service has running task count >= 1.",
        ],
        "procedure": [
            "Confirm current state: `failoverctl status test-app`. Secondary should be ACTIVE.",
            "Trigger failback: `failoverctl failback test-app --operator $USER`.",
            "When `aurora_gate_paused` SNS fires, follow `RUNBOOK-aurora-promotion.md` (this time promoting the primary cluster to writer).",
            "Approve: `failoverctl approve test-app --task-token <token> --reason 'Aurora promoted to primary by $USER'`.",
            "Wait for `failback_completed`.",
        ],
        "verification": [
            "DNS resolves to primary outer NLB.",
            "Aurora writer in primary region.",
            "Primary indicator ACTIVE; secondary PASSIVE.",
        ],
        "rollback": [
            "If primary degrades during failback, the state machine routes to FAIL. Re-run failover.",
        ],
        "escalation": ["Same as `RUNBOOK-manual-failover.md`."],
    },
    {
        "slug": "aurora-promotion",
        "title": "Aurora promotion (operator-only)",
        "when": "Step Functions has paused at AURORA_GATE_PAUSE and SNS sent `aurora_gate_paused` with a task token.",
        "prereqs": [
            "AWS profile `tbed`.",
            "RDS console open in the **target** region.",
            "Task token from the SNS message saved.",
        ],
        "procedure": [
            "In RDS console, navigate to the global cluster `<app>-global`.",
            "Identify the secondary cluster (`<app>-use2` for forward failover; `<app>-use1` for failback).",
            "Click 'Failover' (Aurora Global). Confirm. AWS detaches the secondary from the global cluster and promotes its writer.",
            "Wait until the secondary cluster status returns to 'available' and shows the writer endpoint.",
            "Verify with: `aws --profile tbed --region <target> rds describe-db-clusters --db-cluster-identifier <app>-use2 --query 'DBClusters[0].{Status:Status,Writer:DBClusterMembers[?IsClusterWriter].DBInstanceIdentifier}'`",
            "Call `failoverctl approve` with the task token (or `abort` with reason if the promotion failed).",
        ],
        "verification": [
            "AURORA_CONFIRM_LOOP advances; SNS fires `aurora_writer_confirmed` then `failover_step_completed`.",
            "Within 30s, the executor moves to POSTCHECK.",
        ],
        "rollback": [
            "If you accidentally promoted the wrong cluster: call `failoverctl abort --reason 'wrong cluster'` to fail the state machine; then page Principal Engineer.",
        ],
        "escalation": [
            "Aurora cluster health issues: AWS Support.",
            "Promotion API errors: paste the AWS console error verbatim into the incident channel.",
        ],
    },
    {
        "slug": "stuck-state-machine",
        "title": "Stuck state machine",
        "when": "A Step Functions execution has been RUNNING for more than its expected duration (typical failover < 10 min including Aurora).",
        "prereqs": ["AWS profile `tbed`."],
        "procedure": [
            "Get the execution ARN: `failoverctl history test-app | head`.",
            "Check current state: `aws stepfunctions describe-execution --execution-arn <arn>`.",
            "Get full history: `aws stepfunctions get-execution-history --execution-arn <arn> --max-results 50`.",
            "Identify the state where it stopped advancing.",
            "If at AURORA_GATE_PAUSE, the SNS message with the task token is in CW Logs `/aws/states/<app>-failover-use1`. Re-publish or call `failoverctl approve` / `abort`.",
            "If at AURORA_CONFIRM_LOOP, check RDS console — Aurora may be promoting slowly.",
            "If at WAIT_R53_PROPAGATION, this is normal for up to 90s.",
            "If a Lambda raised an exception, the Catch routed to FAIL. Read the exception in the execution history.",
        ],
        "verification": ["Execution status moves out of RUNNING."],
        "rollback": [
            "Stop the execution: `aws stepfunctions stop-execution --execution-arn <arn> --error 'OperatorAbort' --cause 'reason'`.",
            "Then trigger a fresh failover/failback as needed.",
        ],
        "escalation": ["Page Principal Engineer."],
    },
    {
        "slug": "split-brain-recovery",
        "title": "Split-brain recovery",
        "when": "`failoverctl status test-app` shows BOTH regions with role=ACTIVE.",
        "prereqs": [
            "AWS profile `tbed`. The orchestrator's anti-split-brain guard should prevent this; if you're here, something is very wrong."
        ],
        "procedure": [
            "STOP. Do not let the app continue writing in both regions.",
            "Determine which region you want to keep ACTIVE. Usually that's the region holding the Aurora writer (check RDS console).",
            "In the OTHER region, manually set the indicator to PASSIVE: `failoverctl drain test-app --region <other-region> --operator $USER`. (This sets DRAINING; after drain_seconds, follow up with another invocation that sets PASSIVE — until then the app's Kafka consumer pauses.)",
            "Verify: `failoverctl status test-app` shows exactly one ACTIVE.",
            "File a bug — split-brain occurring at all is a defect.",
        ],
        "verification": [
            "Exactly one region with role=ACTIVE.",
            "DNS resolves to the same region.",
            "Aurora writer in the same region.",
        ],
        "rollback": [],
        "escalation": ["Page Principal Engineer immediately. This is a P0."],
    },
    {
        "slug": "dry-run",
        "title": "Dry run",
        "when": "You want to validate the orchestrator end-to-end without changing any state. Useful before a real failover, or as a periodic exercise.",
        "prereqs": ["AWS profile `tbed`. `make harness-up` complete."],
        "procedure": [
            "Trigger: `failoverctl dryrun test-app --operator $USER`.",
            "Watch SNS — every event should be subject-prefixed `[DRY-RUN]`.",
            "Watch Step Functions — every Lambda emits `dry_run_action_skipped` instead of mutating SSM/R53/Aurora.",
            "Read the `executor-runs/` audit object; it should record `dry_run: true`.",
        ],
        "verification": [
            "No SSM /failover/{app}/{region}/role parameter changes.",
            "No CloudWatch metric emit of PrimaryHealthControl.",
            "No Aurora promotion attempt.",
            "Step Functions execution status: SUCCEEDED.",
        ],
        "rollback": [],
        "escalation": ["Dry-run failures are bugs. File an issue."],
    },
    {
        "slug": "onboard-new-app",
        "title": "Onboard a new app",
        "when": "You're adding a new ECS Fargate app to the orchestrator.",
        "prereqs": ["See `docs/onboarding-new-app.md`."],
        "procedure": [
            "Open the issue (`new_app_onboarding` template).",
            "Branch + add `profiles/<app>.yaml` + `terraform/apps/<app>/`.",
            "Self-merge after green CI.",
            "`make harness-up APP=<app>`.",
            "`failoverctl status <app>`.",
            "Run scenarios 1, 7 against the new app.",
        ],
        "verification": [
            "Both scenarios pass; `make state-dump APP=<app>` shows known-good baseline."
        ],
        "rollback": [
            "Revert the PR. `terraform destroy` per `make harness-down APP=<app>` if needed."
        ],
        "escalation": ["Onboarding bugs: file an issue with the new_app_onboarding label."],
    },
]

RUNBOOK_TPL = """# {title}

**Audience:** SRE on-call.

## When to use

{when}

## Prerequisites

{prereqs}

## Procedure

{procedure}

## Verification

{verification}

## Rollback

{rollback}

## Escalation

{escalation}

_Last reviewed: 2026-04-27._
"""


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "_(none)_"
    return "\n".join(f"{i + 1}. {x}" for i, x in enumerate(items))


def _markdown_list(items: list[str]) -> str:
    if not items:
        return "_(none)_"
    return "\n".join(f"- {x}" for x in items)


def main() -> None:
    for s in SCENARIOS:
        path = SCEN_DIR / f"scenario-{s['n']:02d}-{s['slug']}.md"
        body = SCENARIO_TPL.format(
            n=s["n"],
            slug_underscore=s["slug"].replace("-", "_"),
            title=s["title"],
            summary=s["summary"],
            expected=s["expected"],
            proves=s["proves"],
        )
        path.write_text(body, encoding="utf-8")
        print(f"wrote {path}")
    for r in RUNBOOKS:
        path = RUN_DIR / f"RUNBOOK-{r['slug']}.md"
        body = RUNBOOK_TPL.format(
            title=r["title"],
            when=r["when"],
            prereqs=_markdown_list(r["prereqs"]),
            procedure=_bullet_list(r["procedure"]),
            verification=_markdown_list(r["verification"]),
            rollback=_markdown_list(r["rollback"]),
            escalation=_markdown_list(r["escalation"]),
        )
        path.write_text(body, encoding="utf-8")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
