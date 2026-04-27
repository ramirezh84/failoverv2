# CLAUDE.md — Build Instructions for the `failoverv2` Repository

This file is read by Claude Code at the start of every session. It defines the rules of the road for this codebase. **SPEC.md is the source of truth for what to build. CLAUDE.md is the source of truth for how to build it.** When the two conflict, ask the user.

---

## 1. Project at a glance

`failoverv2` is a **multi-region failover orchestrator** for ECS Fargate applications running on AWS, written in Python 3.14, deployed via Terraform with `aws-cli` profile `tbed`, orchestrated by AWS Step Functions. GitHub Actions runs code-quality CI only; AWS deploys are local manual `terraform apply`.

- **Build target:** Principal Engineer's personal AWS account, accessed via AWS profile `tbed`.
- **Topology mirror:** the POC replicates the eventual JPMC topology 100%. Do not "simplify" the architecture for the POC. The only POC-specific concessions are around credentials (self-signed certs, single account, no SSO) and process (manual local apply, no CD pipeline).
- **Read SPEC.md first.** Every architectural decision is justified there. Do not improvise on architecture.

### 1.1 POC velocity mode (read this first)

This POC prioritizes **speed of completion over deliberation**. While building:

- **Decide, don't ask**, when the choice doesn't violate any §2 hard constraint. Variable names, helper function design, internal refactoring, log message wording (within the §3.3 vocabulary), error message phrasing, test structure, file organization within a module — pick a reasonable answer and move on. Do not write "I could approach this two ways..." paragraphs.
- **Self-merge after green CI.** No waiting for human review. The PR + CI flow is for code quality and audit trail, not for blocking on approval.
- **Default to `terraform apply -auto-approve`** once the operator has seen the plan output once for that root module. For subsequent applies of the same module on the same day, no fresh human review of the plan needed.
- **Run scenarios in parallel where state allows.** Scenarios 1, 2, 3, 5, 14 are non-mutating (or only mutate signal metrics) and can run concurrently. Scenarios 4, 7, 8, 9, 10, 11, 12 mutate the orchestrator's state machine and indicator and must run sequentially. Scenario 13 (profile change mid-incident) needs its own profile and can run in parallel with non-mutating ones.
- **Batch error reporting.** When running a scenario suite, surface all failures in a single consolidated report at the end. Do not stop the suite on first failure unless the failure makes subsequent scenarios meaningless (e.g., test harness deploy failed → don't try to run scenarios; signal collector Lambda crashlooping → don't run decision-engine scenarios).
- **Skip preamble.** Don't explain the plan before executing it. Don't summarize what's about to happen. Just do the work and post a one-line summary in the PR description.
- **Multiple PRs in flight.** If a piece of work cleanly decomposes into independent chunks, open them as separate PRs in parallel. Do not serialize unnecessarily.

This mode does **NOT** relax:
- Any §2 hard constraint
- Test coverage gates (≥80% line, ≥70% branch)
- Documentation update requirements (every behavior change touches docs)
- Profile schema validation
- IAM scoping rules (no `*`, every Lambda VPC-attached, every boto3 client with `endpoint_url`)
- Self-verification checklist in §8 before opening a PR

When you genuinely cannot proceed — AWS service quota hit, regional service mismatch (e.g., a service unavailable in `us-east-2`), ambiguity in SPEC, conflict between SPEC and observed AWS behavior — **surface immediately with a clear ask and wait**. Don't guess on these. Don't proceed with a "best effort" workaround that diverges from SPEC.

### 1.2 Iteration loop (build → validate → fix → re-validate)

Build quality is non-negotiable. **Validation speed** is what makes velocity possible. The loop is:

1. Edit code (Lambda, state machine ASL, profile, runbook, etc.).
2. `make runtime-apply` — applies only the runtime layer; typical 1-5 minutes.
3. `make scenario-N` — runs one scenario; should complete in <5 minutes.
4. Read `tests/results/scenario-N.json`. PASS → next scenario. FAIL → look at the structured failure reason, fix, go back to step 1.
5. **Do not run `make scenarios-all` until individual scenarios are passing in isolation.** Running the full suite to find one bug is wasteful; isolate first.

**Layer discipline:**
- `make harness-up` (full base + runtime apply) runs **once per session**, at the start. Base layer is slow (Aurora Global takes 15-25 min). Don't redeploy it casually.
- `make runtime-apply` is the iteration command. Lambdas, Step Functions, alarms, SSM params, canaries — fast resources.
- `make harness-down` runs **only when explicitly stable** (suite passes 3× in a row) or for a clean restart. The harness stays up between iterations.
- If you need to clean orchestrator runtime state without touching infra: `make scenario-reset`. Runs in <30 seconds.

**"Stable" definition:**
- `make stable-suite` — runs `make scenarios-all` three consecutive times. Pass means all 14 scenarios pass cleanly in all three runs. **One spurious failure across the three runs = not stable.** Investigate and fix flakiness before declaring done.
- Single-run pass is a milestone, not stability. Treat it as "promising" and immediately attempt the second run.

**Validation surface (every scenario, not just outcome):**
- Final state (DNS, indicator, Aurora writer, ECS task counts)
- Step Functions execution path — exact state sequence, exact inputs/outputs at each state
- SNS notifications — every event, in order, with correct message attributes (especially `app_name`)
- CloudWatch Logs — every expected event from §3.3 vocabulary appeared in the right Lambda
- CloudWatch Metrics — custom metrics emitted with expected values
- CloudWatch Alarms — state transitions captured
- Route 53 health checks — state matched orchestrator emissions
- S3 audit trail — decision records, observation snapshots, executor incident records
- Indicator semantics — synthetic Kafka consumer in test app actually paused/resumed at right times
- Timing — every phase within its expected window

If a scenario's outcome is correct but a notification is missing or a log event has wrong fields, the scenario **fails**. "It worked but the logs are messy" is a bug, not a quibble. SRE on-call depends on those logs.

**Tight-loop discipline (when fixing bugs):**
- Fix in place on a feature branch. Multiple commits per hour is fine.
- Don't open a PR after each commit. Accumulate fixes for one logical issue, rebase, push, open one PR per logical issue.
- CI runs on every push. Self-merge after green.
- Update `CHANGELOG.md` once per logical issue, not per commit.
- For tracking: every fix references an issue in the PR description, but multiple fixes in one PR is fine if they belong to the same logical issue.

**When a scenario is flaky:**
- Don't add retries to mask flakiness. Flakiness is a real bug, usually one of: insufficient wait between operations (race condition), assumption that AWS API returns immediately consistent results (it often doesn't — RDS/Route 53/Aurora especially), or scenario state leakage from a previous run not cleaned up.
- Investigate root cause, fix it, document the cause in `docs/scenarios/scenario-NN-*.md` under a "Flakiness fixed" subsection so future debugging benefits.

### 1.3 What "speed up" means and doesn't mean

**Speed up means:**
- Faster validation loop (sub-10-min edit-test cycle)
- No waiting on human review for routine PRs
- Auto-approve Terraform when nothing about the plan is surprising
- Run independent scenarios in parallel
- Surface failures in batches, not one-at-a-time
- Skip preamble; just do and summarize

**Speed up does NOT mean:**
- Skip tests
- Skip docs
- Skip schema validation
- Skip the assertion list per scenario
- Lower coverage gates
- Mask flakiness with retries
- Declare "stable" after one passing run
- Ship a Lambda without `endpoint_url=` because "it works in dev"
- Open PRs without an issue link
- Skip the self-verification checklist in §8

If the work is rushed enough to compromise any of those, slow down. The goal is "validation is fast, build is solid" — not "build is sloppy, validation papers over it."

---

## 2. Hard constraints (NEVER violate; ask before deviating)

These are non-negotiable. If a request appears to require violating one of these, stop and ask the user.

1. **No DynamoDB for runtime state.** Runtime state lives in SSM Parameter Store + S3. The `lib/state_store.py` interface is the single isolation point for a future DynamoDB swap. **A DynamoDB lock table is permitted as the Terraform state-lock backend ONLY** — the orchestrator's runtime code never reads or writes that table. (Personal POC concession; the Terraform-1.10 native S3 locking option is ALSO acceptable if simpler.)
2. **No AppConfig.** The regional indicator is a pulled SSM parameter. The `lib/indicator_writer.py` interface is the single isolation point for a future AppConfig swap.
3. **No Route 53 ARC.** R53 control is via CloudWatch metric → alarm → R53 health check. Lambda emits the metric; it does not call `route53` APIs directly.
4. **No internet egress from any Lambda.** Every Lambda is VPC-attached in a private subnet. Every AWS API call goes through an interface VPC endpoint. Every `boto3` client is constructed with an explicit `endpoint_url` parameter pointing at the VPC endpoint.
5. **No IAM `*` actions or `*` resources.** Every IAM policy enumerates specific actions and specific resource ARNs. The CI job `iam-policy-check` will reject PRs with `*`.
6. **GitHub Actions CI never touches AWS.** CI runs code-quality checks only (lint, types, tests, schema validation, Terraform validate). There is no automated deploy. AWS credentials live only on the operator's local machine via `aws configure --profile tbed`. Do not add deploy workflows, do not configure GitHub OIDC, do not add AWS role ARNs to GitHub Secrets or Variables. Adding any of these is a JPMC-port concern (SPEC §14), not a POC concern.
7. **No code or design borrowed from any prior failover orchestrator.** This is a net-new build. If the user references prior work, ask for explicit text — do not pattern-match from training data.
8. **No automatic Aurora promotion.** Every Aurora writer flip is operator-triggered via `SendTaskSuccess` on a paused Step Functions state. The orchestrator confirms but never initiates.
9. **No automatic failback.** Failback is always operator-triggered. Even when the auto-failover flag is on, auto-failback stays off.
10. **No bypassing the SDLC.** Every change goes through PR + CI + (where required) approval + merge. No direct pushes to `main`. No `terraform apply` from a laptop. Ever.

---

## 3. Code conventions

### 3.1 Python (3.14)
- **Type hints are mandatory** on every function signature, every class attribute, every module-level constant. `mypy --strict` must pass.
- **`ruff` for lint and format.** Settings in `pyproject.toml`. CI checks both.
- **Structured logging with the standard `logging` module + a JSON formatter.** Every log line includes `app_name`, `region`, `execution_id` (when applicable), `event`, and `severity`. No `print()`.
- **No bare `except:`.** Catch specific exceptions. Re-raise with context if you don't fully handle.
- **Idempotency is non-negotiable** in any Lambda invoked by Step Functions. Use deterministic IDs (e.g., `failover-{app}-{utc_date}-{sequence}`) and check before mutating.
- **Dataclasses or Pydantic for structured data**, not raw dicts. Profile loading uses Pydantic for validation.
- **Always pass `endpoint_url=` to boto3 clients.** Never construct a boto3 client without it. The `lib/aws_clients.py` module provides factory functions that do this; use them.
- **No `time.sleep()` in Lambdas.** Use Step Functions `Wait` states for any delay.

### 3.2 Module layout (mirror SPEC §9)
- `lambdas/<lambda_name>/handler.py` — the Lambda entrypoint, single function `lambda_handler(event, context)`.
- `lambdas/<lambda_name>/logic.py` — pure-Python business logic, no AWS SDK calls. Unit-testable without mocks.
- `lambdas/<lambda_name>/aws.py` — thin AWS SDK wrapper, the only place that imports `boto3` for that Lambda.
- `lambdas/<lambda_name>/test_*.py` — unit tests colocated with code.
- `lib/` — code shared across Lambdas. Treat as a library; tests in `lib/test_*.py`.
- Never put business logic in `handler.py`. The handler parses the event, calls `logic.run(...)`, returns the result.

### 3.3 Logging events (use these exact strings)
Pick from this list when adding logs. Do not invent variants. New events require a SPEC update.
- `signal_collected`, `signal_red`, `signal_recovered`
- `decision_evaluated`, `decision_changed`, `failover_authorized`
- `state_machine_started`, `state_machine_step_entered`, `state_machine_step_completed`, `state_machine_step_failed`
- `aurora_gate_paused`, `aurora_gate_approved`, `aurora_gate_aborted`, `aurora_writer_confirmed`
- `r53_control_metric_emitted`, `indicator_updated`
- `dry_run_action_skipped`

---

## 4. Terraform conventions

- **Modules in `terraform/modules/`, app instances in `terraform/apps/<app>/`.** No exceptions. No ad-hoc resources outside a module.
- **One state file per app instance.** Backend is **S3 + DynamoDB lock table** (DDB allowed strictly for state locking; runtime code does not touch it) OR S3 native locking on Terraform 1.10+. Either is acceptable; pick the simpler one. The runtime forbidden-list still applies — the orchestrator Lambdas never make DDB API calls.
- **`terraform fmt`, `terraform validate`, `tflint`, `checkov` all clean.** CI enforces.
- **No `count = 0` to disable a resource.** Use `for_each` with an empty map, or split into a separate module.
- **Every resource has tags.** Tags include `app`, `env`, `region`, `managed_by = "terraform"`, `repo = "failoverv2"`, `component`.
- **No hardcoded ARNs or account IDs.** Use `data "aws_caller_identity"` and `data "aws_region"`.
- **Variables have descriptions and types.** Outputs have descriptions.
- **Provider versions pinned in `versions.tf`.** AWS provider pinned to a minor version (e.g., `~> 5.80`).
- **Two providers always:** `aws.use1` and `aws.use2`. Never default-provider for cross-region modules. Make region explicit in every resource.

---

## 5. Step Functions conventions

- **Definitions live in `statemachines/*.asl.json`** as JSON, not inline in Terraform. Terraform `templatefile()` is used to inject ARNs.
- **Every Task state has explicit `Retry` and `Catch`.** No exceptions. Defaults: 3 retries, exponential backoff with jitter, on `States.TaskFailed` and `Lambda.ServiceException`.
- **The Aurora gate uses `.waitForTaskToken`** integration with SNS. The state machine pauses; the SNS message contains the task token; `approval_callback` Lambda calls `SendTaskSuccess` or `SendTaskFailure`.
- **Idempotency token in input.** Every state machine execution has a `failover_id` in input. Lambdas use this to dedupe.
- **No Express workflows.** Standard only — Express does not support `waitForTaskToken` cleanly.
- **Execution name is the failover_id.** This makes Step Functions reject duplicate triggers automatically.

---

## 6. Profile and schema conventions

- **`profiles/profile.schema.json`** is the source of truth for what a valid profile looks like. Update it before adding fields anywhere else.
- **Every new schema field needs:** a JSON Schema entry, an entry in the example profile, a Pydantic model field with type, a unit test that asserts loading round-trips correctly, and a runbook note if it changes operator behavior.
- **Never read a profile directly from S3 in business logic.** The `lib/profile_loader.py` module is the only entrypoint. It validates against the schema on every read.
- **Profiles are deployed via CI**, not hand-uploaded.

---

## 7. Testing requirements

- **Every PR adds tests for every change.** Coverage gate: ≥80% line, ≥70% branch, measured at the package level. PRs cannot lower coverage.
- **Three layers:**
  - **Unit:** `pytest`, no AWS, mocks via `moto` where unavoidable. Run on every PR.
  - **Integration:** runs against the deployed test harness in `tbed`. Triggered by `deploy-test-harness.yml` after a successful deploy.
  - **Chaos:** runs the full 14 scenarios from SPEC §10 against the test harness. Triggered quarterly via `chaos-game-day.yml` and on-demand via `workflow_dispatch`.
- **Every Step Functions state has a "resume from this state" test.** Verifies idempotency on re-entry.
- **Every Lambda has a dry-run test.** With `DRY_RUN=true` in the event, the Lambda performs all reads, builds the action plan, logs it, and returns without mutating.
- **Tests in `tests/unit/profile_validation/invalid/`** must contain at least one example for every required field, every constraint, every cross-field rule. Adding a constraint without adding a rejection test is a CI failure.

---

## 8. Self-verification checklist (run before opening any PR)

```
[ ] ruff check .          → clean
[ ] ruff format --check . → clean
[ ] mypy --strict .       → clean
[ ] pytest --cov=...      → ≥80% line, ≥70% branch
[ ] terraform fmt -recursive -check  → clean
[ ] terraform validate (every root module) → clean
[ ] tflint                → clean
[ ] checkov -d terraform  → no HIGH/CRITICAL
[ ] bandit -r lambdas/ lib/  → no HIGH/CRITICAL
[ ] gitleaks detect       → no findings
[ ] grep -r '"\*"' terraform/ → no IAM wildcards
[ ] grep -r "boto3.client(" lambdas/ lib/ | grep -v "endpoint_url"  → empty (every client must specify endpoint_url)
[ ] grep -r "time.sleep" lambdas/  → empty (use Wait states)
[ ] CHANGELOG.md updated under [Unreleased]
[ ] SPEC.md updated if behavior changed
[ ] Relevant runbook(s) updated if operator-visible behavior changed
[ ] At least one new test exists for the change
[ ] PR description filled per template
```

If any item fails, fix before pushing. Do not push and let CI tell you.

---

## 9. When to ask vs. when to decide

**Ask the user when:**
- A change would touch a hard constraint in §2.
- The SPEC is silent or ambiguous on a behavior.
- A library or service version pin needs to be raised.
- A new AWS service is introduced that's not already in SPEC §3.
- A profile schema change is needed.
- An IAM permission widening is needed.
- Test coverage would have to drop to merge.

**Decide without asking when:**
- Implementation detail within an already-specified module (variable names, internal helper functions, log message wording from the §3.3 list, refactoring within a Lambda).
- Adding a test.
- Updating a runbook to reflect already-shipped behavior.
- Bumping a patch-version dependency that has no breaking-change notes.
- Improving error messages.

When in doubt, ask. A 30-second clarification beats a 30-minute revert.

---

## 10. Anti-patterns to reject (from yourself or from suggestions)

If you find yourself writing or considering any of these, stop and reconsider.

| Anti-pattern | Why it's wrong here |
|---|---|
| "Let's just store the state in DynamoDB" | Forbidden until org approval (§2.1). Use SSM + S3. |
| "Let's use AppConfig for the indicator" | Same. Forbidden until org approval. |
| "Let's add a Route 53 ARC routing control" | Forbidden by org policy. Use CloudWatch alarm → R53 health check. |
| "I'll have the orchestrator promote Aurora automatically" | Aurora promotion is always manual. Never initiate. Only confirm. |
| "I'll use the default `boto3.client('rds')`" | Every client needs an explicit `endpoint_url=` for the VPC endpoint. |
| "Let me use `time.sleep(60)` to wait for propagation" | Use a Step Functions Wait state. Lambda is the wrong place to wait. |
| "I'll catch `Exception` here to be safe" | Catch the specific exceptions you handle. Let everything else propagate. |
| "Let me put a quick `print()` for debugging" | Use the structured logger. Never `print`. |
| "I'll embed credentials in the Lambda env var" | No. Secrets via Secrets Manager, retrieved at cold-start. |
| "Let's allow `Action: '*'` for this one role to make it work" | No. Find the specific actions. CI will reject the PR anyway. |
| "I'll skip the test for this change, it's small" | No. Every change has tests. The CI coverage gate will block the PR. |
| "I'll just push directly to main, it's a one-line fix" | No. PR flow always. No exceptions. |
| "I'll add a GitHub Actions deploy workflow to make this easier" | No. POC deploys are manual local `terraform apply`. CI is code-quality only. Deploy automation is a JPMC-port migration item, not a POC item. |
| "I'll set up GitHub OIDC so CI can run `terraform plan` against the live account" | No. CI never touches AWS in the POC. `terraform validate` runs without creds; that's enough. |

---

## 11. Common pitfalls in this codebase

These have already bitten or are known traps. Watch for them.

1. **Cross-region boto3 calls hang.** Never have a Lambda in `us-east-1` make a synchronous boto3 call to a service endpoint in `us-east-2`. Always go through Step Functions: invoke the in-region Lambda from the state machine. The cross-region "hang" symptom (no error, no timeout, no return) is the canonical failure mode.
2. **VPC endpoints are per-service, per-region.** Adding a new boto3 service call means adding a new VPC endpoint. CI's `vpc-endpoint-check` job enforces this.
3. **Step Functions execution name uniqueness.** Re-running with the same `failover_id` is a feature (idempotency) but you must include the `failover_id` as the execution name, not just in input.
4. **Synthetic canary in the *opposite* region.** The canary in `us-east-2` probes `us-east-1`, and vice versa. If you find yourself deploying a canary in the same region as its target, that's wrong — it can't survive the failure mode it's supposed to detect.
5. **Profile changes need both regions to converge.** When a profile is updated, both Decision Engines must read the new version. CRR is async; allow ~60 seconds before assuming both regions are in sync. Tests for profile-driven behavior must wait for replication.
6. **Aurora `DescribeDBClusters` returns stale data briefly after promotion.** Poll with backoff for up to 5 minutes; do not believe the first response.
7. **R53 health checks have their own propagation window.** The "wait after flipping the control metric" Step Functions Wait state defaults to 90 seconds and exists for this. Don't reduce it without testing.
8. **`ignoreHttpsErrors: true` only applies to the canary, never to production code.** No production Lambda or app should ever skip TLS verification. The canary is the only carve-out, and only because the POC uses self-signed certs.

---

## 12. Repository hygiene

- **Branch from `main`**, name `feat/<short-slug>` or `fix/<short-slug>` or `chore/<short-slug>`.
- **Squash merges only.** No merge commits. No rebase merges.
- **Branches over 5 days old are flagged.** Either land or close.
- **CHANGELOG.md** is the human-facing log. Every PR adds an entry under `## [Unreleased]`. Keep entries to one line each.
- **ADRs in `docs/adr/`** for any architectural decision. Format: `NNNN-short-title.md`. Numbered sequentially. Once committed, ADRs are append-only — superseded ADRs get a successor with a "Supersedes 0007" link.
- **Issues** for tracking work. Every PR links an issue.

---

## 13. Documentation and diagrams (mandatory; see SPEC §8.6)

Documentation is a deliverable, not an afterthought.

### 13.1 What must exist
- The full document set listed in SPEC §8.6.1 (`solution-overview.md`, `architecture.md`, `decision-engine.md`, `operations.md`, `onboarding-new-app.md`, `failure-modes.md`, `profile-reference.md`, `api-reference.md`, `glossary.md`, ADRs).
- All 13 diagrams listed in SPEC §8.6.2 (Mermaid for flow/sequence/state, `diagrams` Python lib for AWS architecture).
- One scenario walkthrough per scenario in SPEC §10 (14 total) in `docs/scenarios/`, each with a Mermaid sequence diagram.

### 13.2 Conventions
- **Every doc declares its audience at the top.** Format: `**Audience:** SRE on-call` (or `Engineering leadership`, `Engineer adding a new app`, etc.). No doc starts without this.
- **Tone is technical and direct.** No marketing language, no fluff, no "Welcome to the world of failover orchestration!" intros. Lead with what the doc tells you and how to use it.
- **Code/CLI examples wherever they help.** Copy-pasteable. Show the command and the expected output.
- **Mermaid for everything that fits.** Renders in GitHub natively. Source IS the rendered form. No PNG screenshots of diagrams when Mermaid would do.
- **AWS architecture diagrams** use the `diagrams` Python library. Commit both the `.py` source and the rendered `.png` and `.svg`. CI regenerates and diffs.
- **No proprietary diagram formats.** No Visio, no Lucidchart, no draw.io binary. Everything must be regenerable from text in the repo.
- **No screenshots from AWS Console** unless absolutely necessary. They go stale instantly. Prefer CLI commands or describe-the-state in text.

### 13.3 When to update documentation
- Any PR labeled `behavior-change` MUST touch at least one file in `docs/` or `runbooks/`. CI enforces this via a label-required job.
- Adding a new signal → update `docs/decision-engine.md` AND the relevant scenario walkthroughs AND the dashboard widget list in `docs/operations.md`.
- Adding a new profile field → update `profile.schema.json` AND `profile-reference.md` (CI regenerates and diffs) AND `docs/onboarding-new-app.md` if it's user-facing.
- Adding a new state to the failover state machine → update `05-failover-statemachine.md` Mermaid AND any scenario walkthroughs that pass through that state.
- Changing a runbook's procedure → bump the runbook's `Last reviewed:` date at the bottom.

### 13.4 ADR discipline
- Open an ADR for any decision with non-obvious tradeoffs. The ADR template (`docs/adr/TEMPLATE.md`) requires: Status, Context, Decision, Consequences, Alternatives Considered.
- ADRs are append-only. To change a decision, write a new ADR that supersedes the old one. Do not edit accepted ADRs except to mark them `Superseded by NNNN`.

### 13.5 Anti-patterns (reject these)
| Anti-pattern | Why it's wrong |
|---|---|
| "I'll add the doc in a follow-up PR" | No. Same PR. |
| "The code is self-documenting" | Code documents what; docs document why. Both are needed. |
| Pasting a screenshot of a Mermaid diagram | Use the Mermaid source. The point is text-based version control. |
| Long marketing-style intros to docs | Audience header + first sentence = what this doc tells you and when to read it. Get to the point. |
| Documentation that re-explains the SPEC | Link to the SPEC. Don't duplicate. Docs explain what's not in the SPEC (the how, the day-to-day, the operator's view). |
| Stale "Last updated: 2025" headers | Every doc has a footer with `Last reviewed: YYYY-MM-DD`. Quarterly reviews touch this even if the content is unchanged. |

---

## 14. AWS specifics for `tbed`

- **Profile name:** `tbed`. Always. Never assume default profile. Every shell command and every Terraform invocation runs with `AWS_PROFILE=tbed` set or `--profile tbed` passed.
- **Regions:** `us-east-1` (primary), `us-east-2` (secondary). Never deploy elsewhere without SPEC update.
- **No GitHub OIDC, no IAM deploy roles for GitHub.** GitHub Actions runs code-quality CI only. AWS deploys happen locally with the `tbed` profile.
- **Terraform backend:** S3 bucket `failoverv2-tfstate-<account-id>` in `us-east-1` with versioning and SSE (AWS-managed KMS is fine for the POC). State locking via Terraform 1.10+ S3 native locking is preferred; DynamoDB lock table `failoverv2-tfstate-lock` is acceptable as the simpler alternative if needed. Pick one. One state key per app: `apps/<app>/terraform.tfstate`.
- **TLS for the test harness:** Terraform generates a self-signed CA + leaf cert via the `tls` provider, imports the leaf into ACM in both regions, attaches to the outer NLB TLS listener. Synthetics canary script reads `IGNORE_TLS_ERRORS=true` from environment.
- **No Aurora deletion protection bypass in code.** If you need to delete a test Aurora cluster, the operator does it manually. Terraform does not have permission to remove deletion protection.
- **Service quotas are the operator's responsibility.** If `terraform apply` fails on a quota limit, surface a clear error in the runbook with a quota-increase request URL — do not silently retry.

---

## 15. The end

If something in this file is unclear, contradicts SPEC.md, or contradicts something the user said in chat — **stop and ask**. The cost of a clarification is always less than the cost of a wrong commit on `main`.

---

**Last updated:** 2026-04-27 (rev 5 — iteration loop discipline; tight loop with full observability assertions; stable = 3 consecutive full-suite passes)
**Companion:** SPEC.md (architecture and behavior), runbooks/ (operator procedures).