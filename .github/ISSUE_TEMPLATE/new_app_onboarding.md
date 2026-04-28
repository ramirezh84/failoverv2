---
name: New app onboarding
about: Onboard a new ECS Fargate app to the orchestrator
title: "[onboard] <app-name>"
labels: onboarding
assignees: ramirezh84
---

<!-- Follow runbooks/RUNBOOK-onboard-new-app.md alongside this issue. -->

## App identity

- App name (DNS-safe slug):
- Owning team / on-call rotation:
- Pattern: `active_passive` | `active_active`
- Primary region:
- Secondary region:

## Components present

- [ ] API Gateway
- [ ] Aurora (Global Database)
- [ ] ElastiCache (Global Datastore)
- [ ] Kafka consumer (gated on regional indicator)

## Network

- Outer NLB ARN (primary):
- Outer NLB ARN (secondary):
- ALB ARN (primary):
- ALB ARN (secondary):
- API GW ID (primary): N/A or `<id>`
- API GW ID (secondary): N/A or `<id>`
- Routable URL (primary):
- Routable URL (secondary):

## Aurora (if present)

- Cluster ID (primary):
- Cluster ID (secondary):
- Global cluster ID:
- Writer policy: `pin_primary` | `follow_traffic`
- DNS-first failover: `true` (default for read-tolerant) | `false`

## Notifications

- SNS topic ARN (primary):
- SNS topic ARN (secondary):

## Profile starting values

- `tier1_quorum`:
- `dwell_minutes`:
- `auto_failover`: `false` (always for first 30 days)
- `auto_failback`: `false` (always)

## Acceptance

- [ ] Profile passes JSON schema validation in CI
- [ ] Terraform stack added under `terraform/apps/<app>/`
- [ ] All 14 chaos scenarios pass against the new app stack
- [ ] Onboarding runbook walkthrough completed
