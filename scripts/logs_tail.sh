#!/usr/bin/env bash
# logs_tail.sh APP REGION SCENARIO  --  multiplexes CloudWatch Logs tail
# across every orchestrator Lambda for the named scenario.
set -euo pipefail

APP="${1:?}" REGION="${2:?}" SCENARIO="${3:?}"
PROFILE="${AWS_PROFILE:-tbed}"
SUFFIX=$(echo "$REGION" | tr -d '-')

LAMBDAS=(
  signal_collector
  decision_engine
  indicator_updater
  manual_trigger
  approval_callback
  executor_precheck
  executor_notify
  executor_flip_r53_metric
  executor_aurora_confirm
  executor_postcheck
)

for lam in "${LAMBDAS[@]}"; do
  aws --profile "$PROFILE" --region "$REGION" logs tail \
    "/aws/lambda/$APP-$lam-$SUFFIX" --follow --format short &
done
wait
