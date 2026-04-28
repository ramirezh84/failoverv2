# Diagram 10 — CI/CD Pipeline (POC)

**Audience:** Anyone working on a PR.

```mermaid
flowchart LR
  PR[PR opened] --> CI[GitHub Actions CI]
  subgraph CI [.github/workflows/ci.yml]
    direction TB
    Lint[lint-python] --> Tests[unit-tests]
    Tests --> Schema[profile-schema-validation]
    Schema --> TFFmt[terraform-fmt]
    TFFmt --> TFValidate[terraform-validate]
    TFValidate --> TFLint[tflint]
    TFLint --> Checkov[checkov]
    Checkov --> SemSecGit[semgrep / bandit / pip-audit / gitleaks]
    SemSecGit --> Custom[iam / vpc / boto3 / no-sleep checks]
    Custom --> Mermaid[mermaid-validate]
    Mermaid --> ProfileDoc[profile-doc-check]
  end
  CI --> Green{All green?}
  Green -- yes --> Merge[Self-merge to main]
  Green -- no --> Fix[Fix locally + push]
  Fix --> CI
  Merge --> Local[Operator runs<br/>make harness-up locally]
  Local --> Deployed[Test harness deployed]

  style Local fill:#fde68a
  style Deployed fill:#86efac
```

Per CLAUDE.md §1.1 + SPEC §11: CI never touches AWS. Deploy is manual.
JPMC port adds the GitHub OIDC + automated CD pipeline.
