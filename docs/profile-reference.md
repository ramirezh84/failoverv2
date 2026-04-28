# Profile Reference

**Audience:** Anyone authoring or modifying a per-app failover profile.
**Generated from:** `profiles/profile.schema.json`. Do not edit by hand —
run `uv run python scripts/generate_profile_reference.py > docs/profile-reference.md`.

This document is the field-by-field reference for the per-app YAML profile.
The orchestrator's runtime behavior is entirely driven by these fields; no
code change is required to onboard a new app.

See [`docs/onboarding-new-app.md`](onboarding-new-app.md) for the workflow,
and [`profiles/profile.schema.json`](../profiles/profile.schema.json) for the
machine-readable contract.

## Top-level fields

- **`app_name`** (string) **(required)**
  DNS-safe app slug, used as a key in resource ARNs and SNS message attributes.
- **`pattern`** (string) **(required)**
  Failover pattern. The POC currently exercises active_passive only; active_active is reserved for future read-mostly apps.
  Allowed: `active_passive`, `active_active`.
- **`primary_region`** (string) **(required)**
  AWS region where the application normally runs.
  Allowed: `us-east-1`, `us-east-2`.
- **`secondary_region`** (string) **(required)**
  AWS region the app fails over to. Must differ from primary_region.
  Allowed: `us-east-1`, `us-east-2`.
- **`components`** (object) **(required)**
  Which optional components the app uses. Decision Engine and Executor only collect/act on signals for components the app declares.
  - **`api_gateway`** (boolean) **(required)**
    App fronts traffic through API Gateway.
  - **`aurora`** (boolean) **(required)**
    App uses Aurora Global.
  - **`elasticache`** (boolean) **(required)**
    App uses ElastiCache Global Datastore.
  - **`kafka_consumer`** (boolean) **(required)**
    App has a Kafka consumer gated on the regional indicator.
- **`network`** (object) **(required)**
  ARNs and IDs of the app's network fabric in both regions. SPEC §7.
  - **`outer_nlb_arn_primary`** (string) **(required)**
  - **`outer_nlb_arn_secondary`** (string) **(required)**
  - **`alb_arn_primary`** (string) **(required)**
  - **`alb_arn_secondary`** (string) **(required)**
  - **`api_gw_id_primary`** (string \| null)
    Required iff components.api_gateway=true.
  - **`api_gw_id_secondary`** (string \| null)
  - **`routable_url_primary`** (string) **(required)**
  - **`routable_url_secondary`** (string) **(required)**
- **`dns`** (object) **(required)**
  - **`global_record_name`** (string) **(required)**
    The R53 record that the orchestrator flips between regional health checks.
  - **`hosted_zone_id`** (string) **(required)**
    Route 53 hosted zone ID owning global_record_name.
- **`aurora`** (object \| null)
  Required iff components.aurora=true.
- **`elasticache`** (object \| null)
  Required iff components.elasticache=true.
- **`kafka`** (object) **(required)**
  - **`consumer_group`** (string) **(required)**
  - **`gate_on_indicator`** (boolean) **(required)**
    When true, the app library pauses the consumer based on /failover/{app}/{region}/role.
- **`signals`** (object) **(required)**
  - **`tier1_quorum`** (integer) **(required)**
    Number of distinct Tier 1 signals that must be red simultaneously. Default 2 (SPEC §4.3).
  - **`dwell_minutes`** (integer) **(required)**
    Continuous duration the quorum must hold. Default 5.
  - **`hysteresis_minutes`** (integer) **(required)**
    Minimum time between successive decision changes. Default 3.
  - **`canary_failure_rate_pct`** (integer) **(required)**
    Failure rate (%) over the dwell window that turns the canary signal red. Default 80.
- **`canary`** (object) **(required)**
  - **`ignore_tls_errors`** (boolean) **(required)**
    Synthetics canary Puppeteer flag. true for POC (self-signed); false for JPMC (SPEC §2.1 POC-A).
  - **`internal_ca_bundle_s3_uri`** (string \| null) **(required)**
- **`failover`** (object) **(required)**
  - **`auto_failover`** (boolean) **(required)**
    When false (default for first 30 days), Decision Engine emits SNS only — operator triggers failover manually. SPEC §4.3.
  - **`auto_failback`** (boolean) **(required)**
    Always false; failback is always operator-triggered. Hard constraint (CLAUDE.md §2 #9).
  - **`drain_seconds`** (integer) **(required)**
    How long the executor waits after writing DRAINING before flipping R53/indicator. Default 60.
  - **`quiesce_seconds`** (integer) **(required)**
    How long the executor waits for in-flight requests to complete during failback. Default 60.
  - **`r53_propagation_seconds`** (integer) **(required)**
    How long the executor waits after flipping the R53 control metric. Default 90.
  - **`stable_minutes_before_failback`** (integer) **(required)**
    How long primary Tier 1 signals must be green before PRECHECK_PRIMARY succeeds. Default 30.
- **`slo`** (object) **(required)**
  - **`rto_minutes`** (integer) **(required)**
  - **`rpo_minutes`** (integer) **(required)**
- **`notifications`** (object) **(required)**
  - **`sns_topic_arn_primary`** (string) **(required)**
  - **`sns_topic_arn_secondary`** (string) **(required)**
  - **`events`** (array) **(required)**
    Item enum: `failover_authorized`, `failover_initiated`, `failover_step_completed`, `failover_completed`, `failover_failed`, `failback_initiated`, `failback_completed`, `failback_failed`, `signal_red`, `signal_recovered`.

