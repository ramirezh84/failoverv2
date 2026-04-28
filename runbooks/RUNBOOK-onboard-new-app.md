# Onboard a new app

**Audience:** SRE on-call.

## When to use

You're adding a new ECS Fargate app to the orchestrator.

## Prerequisites

- See `docs/onboarding-new-app.md`.

## Procedure

1. Open the issue (`new_app_onboarding` template).
2. Branch + add `profiles/<app>.yaml` + `terraform/apps/<app>/`.
3. Self-merge after green CI.
4. `make harness-up APP=<app>`.
5. `failoverctl status <app>`.
6. Run scenarios 1, 7 against the new app.

## Verification

- Both scenarios pass; `make state-dump APP=<app>` shows known-good baseline.

## Rollback

- Revert the PR. `terraform destroy` per `make harness-down APP=<app>` if needed.

## Escalation

- Onboarding bugs: file an issue with the new_app_onboarding label.

_Last reviewed: 2026-04-27._
