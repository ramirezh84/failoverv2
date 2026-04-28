#!/usr/bin/env bash
# scenario_reset.sh APP PRIMARY_REGION SECONDARY_REGION
# Resets orchestrator runtime state in <30 seconds (SPEC §8.7.5):
# - SSM /failover/<app>/<region>/{role,decision,in_flight} deleted
# - PrimaryHealthControl metric reset to 1.0 (clear)
# - Any in-flight Step Functions executions stopped
set -euo pipefail

APP="${1:?app name required}"
PRIMARY="${2:?primary region required}"
SECONDARY="${3:?secondary region required}"
PROFILE="${AWS_PROFILE:-tbed}"

aws() { command aws --profile "$PROFILE" "$@"; }

reset_region() {
  local region="$1"
  echo "==> Resetting region $region"
  for name in role decision in_flight; do
    aws --region "$region" ssm delete-parameter \
      --name "/failover/$APP/$region/$name" 2>/dev/null || true
  done
  # Clear control metric (1.0 = healthy)
  aws --region "$region" cloudwatch put-metric-data \
    --namespace "Failover/$APP" \
    --metric-data "MetricName=PrimaryHealthControl,Value=1.0,Unit=None,Dimensions=[{Name=Region,Value=$region}]" \
    || true
  # Stop in-flight executions
  for sm in "$APP-failover" "$APP-failback"; do
    sm_arn="arn:aws:states:$region:$(aws sts get-caller-identity --query Account --output text):stateMachine:$sm"
    running=$(aws --region "$region" stepfunctions list-executions \
      --state-machine-arn "$sm_arn" --status-filter RUNNING \
      --query 'executions[].executionArn' --output text 2>/dev/null || true)
    for arn in $running; do
      [ -n "$arn" ] && aws --region "$region" stepfunctions stop-execution --execution-arn "$arn" || true
    done
  done
}

reset_region "$PRIMARY"
reset_region "$SECONDARY"
echo "OK: scenario state reset for $APP in $PRIMARY + $SECONDARY"
