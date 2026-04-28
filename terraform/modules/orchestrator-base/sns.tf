###############################################################################
# Account-level SNS topic per region (SPEC §2 #15). Subscribers filter by
# the app_name message attribute.
###############################################################################

resource "aws_sns_topic" "events_primary" {
  provider          = aws.use1
  name              = "failover-events"
  display_name      = "Failover Orchestrator events (account-level)"
  kms_master_key_id = aws_kms_key.audit_primary.arn
  tags              = merge(local.common_tags_use1, { component = "sns-account" })
}

resource "aws_sns_topic" "events_secondary" {
  provider          = aws.use2
  name              = "failover-events"
  display_name      = "Failover Orchestrator events (account-level)"
  kms_master_key_id = aws_kms_key.audit_secondary.arn
  tags              = merge(local.common_tags_use2, { component = "sns-account" })
}
