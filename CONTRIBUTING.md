# Contributing

This repository follows the SDLC defined in [`SPEC.md`](SPEC.md) §11 and the
build conventions in [`CLAUDE.md`](CLAUDE.md). Read both before opening a PR.

## Branching

- Trunk-based; `main` always reflects the latest known-good state.
- Short-lived feature branches: `feat/<slug>`, `fix/<slug>`, `chore/<slug>`.
- Maximum 5 working days; stale branches are flagged.

## PR requirements

1. Linked issue (no orphan PRs).
2. PR description filled per template — what changed, why, blast radius,
   any manual deploy steps, runbook updates needed.
3. Tests added or updated. Coverage cannot decrease.
4. Profile schema validation passes if profile or schema touched.
5. Terraform `fmt` + `validate` clean.
6. Runbook updates for any behavior change.
7. Diagram and documentation updates for any architectural / behavioral
   change (see [`SPEC.md`](SPEC.md) §8.6).
8. `CHANGELOG.md` entry under `## [Unreleased]`.
9. All CI checks green.

Approving review is **not** required during the POC (solo workflow). Author
self-merges after CI passes. Squash-merge only.

## Self-verification before pushing

The checklist in [`CLAUDE.md`](CLAUDE.md) §8 must pass locally before pushing.
Do not rely on CI to catch what you can catch locally.

## Reporting bugs

Open an issue using the `bug_report` template. Include:

- AWS region(s) involved
- Step Functions execution ARN if applicable
- Relevant CloudWatch Logs Insights queries
- Profile snapshot (with secrets redacted)
