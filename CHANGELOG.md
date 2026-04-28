# Changelog

All notable changes to this repository are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The repository
follows semantic versioning.

## [Unreleased]

### Added
- Project skeleton: `pyproject.toml` (Python 3.14, ruff, mypy strict, pytest
  with ≥80% line / ≥70% branch coverage gate), top-level documentation files
  (`README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`, `SECURITY.md`),
  `.gitignore`, `LICENSE`.
- GitHub repository scaffolding: CODEOWNERS, PR template, issue templates
  (`bug_report`, `new_app_onboarding`, `profile_change_request`),
  `dependabot.yml` (security-only).
- CI workflows per `SPEC.md` §11.5: `ci.yml` (lint, types, unit tests,
  schema validation, terraform fmt/validate, tflint, checkov, bandit,
  semgrep, gitleaks, pip-audit, IAM-policy-check, vpc-endpoint-check,
  markdownlint), `codeql.yml` (CodeQL on PR + weekly), `mermaid-validate.yml`,
  `diagrams-render-check.yml`, `profile-doc-check.yml`.

[Unreleased]: https://github.com/ramirezh84/failoverv2/compare/main...HEAD
