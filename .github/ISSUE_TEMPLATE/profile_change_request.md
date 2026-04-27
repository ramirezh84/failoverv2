---
name: Profile change request
about: Tune signal thresholds, dwell, hysteresis, or auto-failover for an app
title: "[profile] <app-name>: <change-summary>"
labels: profile-change
assignees: ramirezh84
---

## App

`<app-name>`

## Change requested

<!-- e.g. dwell_minutes 5 -> 7, auto_failover false -> true -->

## Justification

<!-- Reference signal data, post-incident analysis, or a scenario test result. -->

## Risk

- [ ] LOW — within recommended range, no behavior change
- [ ] MEDIUM — extends dwell or quorum
- [ ] HIGH — flips `auto_failover` or `dns_first_failover`

## Validation

- [ ] Re-run impacted scenarios: <!-- list scenario numbers -->
- [ ] Profile change reviewed against `docs/decision-engine.md`

## Rollback

- [ ] Documented in PR description
