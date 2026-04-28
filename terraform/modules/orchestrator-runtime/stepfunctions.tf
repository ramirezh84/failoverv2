###############################################################################
# Step Functions Standard state machines (failover + failback) per region.
# Definitions live in statemachines/*.asl.json; templatefile() injects the
# Lambda ARNs and SNS topic ARN.
###############################################################################

locals {
  # POC simplification: each SFN invokes its own region's indicator_updater
  # for BOTH source and target indicator writes. Both region-roles are stored
  # in the SFN-region's SSM. Per CLAUDE.md §11 #1, SFN cross-region Lambda
  # invokes are not supported (Lambda.ResourceNotFoundException). True
  # multi-region indicator topology is a follow-up — see TODO in
  # docs/decision-engine.md.
  failover_definition_primary = templatefile("${var.statemachines_root}/failover.asl.json", {
    precheck_lambda_arn                 = aws_lambda_function.primary["executor_precheck"].arn
    notify_lambda_arn                   = aws_lambda_function.primary["executor_notify"].arn
    indicator_updater_source_lambda_arn = aws_lambda_function.primary["indicator_updater"].arn
    indicator_updater_target_lambda_arn = aws_lambda_function.primary["indicator_updater"].arn
    flip_r53_metric_lambda_arn          = aws_lambda_function.primary["executor_flip_r53_metric"].arn
    aurora_confirm_lambda_arn           = aws_lambda_function.primary["executor_aurora_confirm"].arn
    postcheck_lambda_arn                = aws_lambda_function.primary["executor_postcheck"].arn
    sns_topic_arn                       = var.sns_topic_arn_primary
  })

  failback_definition_primary = templatefile("${var.statemachines_root}/failback.asl.json", {
    precheck_lambda_arn                 = aws_lambda_function.primary["executor_precheck"].arn
    notify_lambda_arn                   = aws_lambda_function.primary["executor_notify"].arn
    indicator_updater_source_lambda_arn = aws_lambda_function.primary["indicator_updater"].arn
    indicator_updater_target_lambda_arn = aws_lambda_function.primary["indicator_updater"].arn
    flip_r53_metric_lambda_arn          = aws_lambda_function.primary["executor_flip_r53_metric"].arn
    aurora_confirm_lambda_arn           = aws_lambda_function.primary["executor_aurora_confirm"].arn
    postcheck_lambda_arn                = aws_lambda_function.primary["executor_postcheck"].arn
    sns_topic_arn                       = var.sns_topic_arn_primary
  })

  failover_definition_secondary = templatefile("${var.statemachines_root}/failover.asl.json", {
    precheck_lambda_arn                 = aws_lambda_function.secondary["executor_precheck"].arn
    notify_lambda_arn                   = aws_lambda_function.secondary["executor_notify"].arn
    indicator_updater_source_lambda_arn = aws_lambda_function.secondary["indicator_updater"].arn
    indicator_updater_target_lambda_arn = aws_lambda_function.secondary["indicator_updater"].arn
    flip_r53_metric_lambda_arn          = aws_lambda_function.secondary["executor_flip_r53_metric"].arn
    aurora_confirm_lambda_arn           = aws_lambda_function.secondary["executor_aurora_confirm"].arn
    postcheck_lambda_arn                = aws_lambda_function.secondary["executor_postcheck"].arn
    sns_topic_arn                       = var.sns_topic_arn_secondary
  })

  failback_definition_secondary = templatefile("${var.statemachines_root}/failback.asl.json", {
    precheck_lambda_arn                 = aws_lambda_function.secondary["executor_precheck"].arn
    notify_lambda_arn                   = aws_lambda_function.secondary["executor_notify"].arn
    indicator_updater_source_lambda_arn = aws_lambda_function.secondary["indicator_updater"].arn
    indicator_updater_target_lambda_arn = aws_lambda_function.secondary["indicator_updater"].arn
    flip_r53_metric_lambda_arn          = aws_lambda_function.secondary["executor_flip_r53_metric"].arn
    aurora_confirm_lambda_arn           = aws_lambda_function.secondary["executor_aurora_confirm"].arn
    postcheck_lambda_arn                = aws_lambda_function.secondary["executor_postcheck"].arn
    sns_topic_arn                       = var.sns_topic_arn_secondary
  })
}

resource "aws_cloudwatch_log_group" "sfn_failover_primary" {
  provider          = aws.use1
  name              = "/aws/states/${var.app_name}-failover-use1"
  retention_in_days = var.log_retention_days
  tags              = merge(local.common_tags_use1, { component = "sfn-log-group" })
}

resource "aws_cloudwatch_log_group" "sfn_failback_primary" {
  provider          = aws.use1
  name              = "/aws/states/${var.app_name}-failback-use1"
  retention_in_days = var.log_retention_days
  tags              = merge(local.common_tags_use1, { component = "sfn-log-group" })
}

resource "aws_cloudwatch_log_group" "sfn_failover_secondary" {
  provider          = aws.use2
  name              = "/aws/states/${var.app_name}-failover-use2"
  retention_in_days = var.log_retention_days
  tags              = merge(local.common_tags_use2, { component = "sfn-log-group" })
}

resource "aws_cloudwatch_log_group" "sfn_failback_secondary" {
  provider          = aws.use2
  name              = "/aws/states/${var.app_name}-failback-use2"
  retention_in_days = var.log_retention_days
  tags              = merge(local.common_tags_use2, { component = "sfn-log-group" })
}

resource "aws_sfn_state_machine" "failover_primary" {
  provider   = aws.use1
  name       = "${var.app_name}-failover"
  role_arn   = aws_iam_role.sfn_primary.arn
  type       = "STANDARD"
  definition = local.failover_definition_primary
  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn_failover_primary.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }
  tracing_configuration { enabled = true }
  tags = merge(local.common_tags_use1, { component = "sfn", workflow = "failover" })
}

resource "aws_sfn_state_machine" "failback_primary" {
  provider   = aws.use1
  name       = "${var.app_name}-failback"
  role_arn   = aws_iam_role.sfn_primary.arn
  type       = "STANDARD"
  definition = local.failback_definition_primary
  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn_failback_primary.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }
  tracing_configuration { enabled = true }
  tags = merge(local.common_tags_use1, { component = "sfn", workflow = "failback" })
}

resource "aws_sfn_state_machine" "failover_secondary" {
  provider   = aws.use2
  name       = "${var.app_name}-failover"
  role_arn   = aws_iam_role.sfn_secondary.arn
  type       = "STANDARD"
  definition = local.failover_definition_secondary
  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn_failover_secondary.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }
  tracing_configuration { enabled = true }
  tags = merge(local.common_tags_use2, { component = "sfn", workflow = "failover" })
}

resource "aws_sfn_state_machine" "failback_secondary" {
  provider   = aws.use2
  name       = "${var.app_name}-failback"
  role_arn   = aws_iam_role.sfn_secondary.arn
  type       = "STANDARD"
  definition = local.failback_definition_secondary
  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn_failback_secondary.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }
  tracing_configuration { enabled = true }
  tags = merge(local.common_tags_use2, { component = "sfn", workflow = "failback" })
}
