#!/usr/bin/env bash
# state_dump.sh APP PRIMARY SECONDARY  --  emits a JSON snapshot of all
# orchestrator state to stdout. Used by `make state-dump` and the chaos
# framework's "final state" assertion.
set -euo pipefail

APP="${1:?}" PRIMARY="${2:?}" SECONDARY="${3:?}"
PROFILE="${AWS_PROFILE:-tbed}"

aws() { command aws --profile "$PROFILE" "$@"; }
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

emit_region() {
  local region="$1"
  local role decision in_flight alarm_state metric_value
  role=$(aws --region "$region" ssm get-parameter --name "/failover/$APP/$region/role" --query 'Parameter.Value' --output text 2>/dev/null || echo "(unset)")
  decision=$(aws --region "$region" ssm get-parameter --name "/failover/$APP/$region/decision" --query 'Parameter.Value' --output text 2>/dev/null || echo "(unset)")
  in_flight=$(aws --region "$region" ssm get-parameter --name "/failover/$APP/$region/in_flight" --query 'Parameter.Value' --output text 2>/dev/null || echo "(unset)")
  alarm_state=$(aws --region "$region" cloudwatch describe-alarms \
    --alarm-names "$APP-PrimaryHealthControl-$(echo "$region" | tr -d -)" \
    --query 'MetricAlarms[0].StateValue' --output text 2>/dev/null || echo "(unknown)")
  cat <<EOF
"$region": {
  "role": "$role",
  "decision_state": $decision,
  "in_flight": "$in_flight",
  "alarm_state": "$alarm_state"
}
EOF
}

cat <<EOF
{
  "app": "$APP",
  "account": "$ACCOUNT",
  "regions": {
$(emit_region "$PRIMARY"),
$(emit_region "$SECONDARY")
  }
}
EOF
