---
name: Bug report
about: Report a defect in the orchestrator
title: "[bug] "
labels: bug
assignees: ramirezh84
---

## Summary

<!-- One sentence describing the unexpected behavior. -->

## Affected component(s)

<!-- e.g. decision_engine, failover_executor, terraform/modules/orchestrator-runtime -->

## Region(s) involved

- Primary:
- Secondary:

## Step Functions execution ARN (if applicable)

```
arn:aws:states:us-east-1:...:execution:failover-...:...
```

## Profile snapshot

<details><summary>profile.yaml</summary>

```yaml
# paste; redact ARNs / IDs only if necessary
```

</details>

## CloudWatch Logs Insights query

```
fields @timestamp, @message
| filter event = "..."
| sort @timestamp desc
| limit 100
```

## Expected behavior

## Actual behavior

## Reproduction steps

1.
2.
3.

## Severity

- [ ] CRITICAL — orchestrator down or split-brain
- [ ] HIGH — incorrect failover behavior
- [ ] MEDIUM — observability gap, false alarm, missing log
- [ ] LOW — cosmetic, doc, naming
