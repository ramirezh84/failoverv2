# ADR 0006 — GitHub OIDC at JPMC port; static profile for POC

**Status:** Accepted (POC); deferred to JPMC port for the OIDC piece
**Date:** 2026-04-27
**Deciders:** Principal Engineer

## Context

The orchestrator's CI/CD model has two distinct lifecycle questions:

1. **Code-quality gates** (lint, types, tests, schema validation,
   terraform validate) — these don't need AWS access.
2. **Deployment** — these do, and require some way for an automated
   actor (or operator) to authenticate to AWS.

For the POC, deploys are manual (CLAUDE.md §1). For JPMC production,
deploys need to be automated AND must NOT use static long-lived AWS
credentials in GitHub Secrets.

## Decision

**POC:** GitHub Actions runs code-quality CI only. Operator runs
`terraform apply` locally with AWS CLI profile `tbed`. No GitHub OIDC,
no AWS role ARNs in GitHub Variables/Secrets.

**JPMC port (SPEC §14):** Add GitHub OIDC identity provider in the JPMC
AWS account(s). IAM deploy roles with trust policies scoped to the repo,
branch (for non-prod), and tag pattern (for prod). No static keys.

## Consequences

**Positive (POC):**
- Zero GitHub-side AWS credentials to rotate.
- CI is pure code-quality; no risk of CI accidentally touching prod.

**Positive (JPMC port):**
- OIDC eliminates the long-lived-key risk class entirely.
- Repo + branch + tag scoping limits blast radius per workflow.

**Negative (POC):**
- Deploys are manual — operator must remember to apply changes.
- Drift between `main` and the live account is possible; runbook must
  cover drift checks.

**Neutral:**
- The JPMC port is a single migration item (SPEC §14); the orchestrator's
  runtime code does not change.

## Alternatives Considered

- **Static AWS keys in GitHub Secrets:** Rejected on principle. Long-lived
  keys are a compliance and rotation burden.
- **AWS Identity Center / SSO from GitHub:** Not yet GA at the time of
  build for this account model.
