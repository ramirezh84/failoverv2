locals {
  common_tags = merge(var.tags, {
    app  = var.app_name
    repo = "failoverv2"
  })
  common_tags_use1 = merge(local.common_tags, { region = var.primary_region })
  common_tags_use2 = merge(local.common_tags, { region = var.secondary_region })

  # Each Lambda's source is lambdas/<name>/. Build a zip per Lambda.
  lambda_packages = {
    signal_collector         = "${var.lambda_source_root}/signal_collector"
    decision_engine          = "${var.lambda_source_root}/decision_engine"
    indicator_updater        = "${var.lambda_source_root}/indicator_updater"
    manual_trigger           = "${var.lambda_source_root}/manual_trigger"
    approval_callback        = "${var.lambda_source_root}/approval_callback"
    executor_precheck        = "${var.lambda_source_root}/executor_precheck"
    executor_notify          = "${var.lambda_source_root}/executor_notify"
    executor_flip_r53_metric = "${var.lambda_source_root}/executor_flip_r53_metric"
    executor_aurora_confirm  = "${var.lambda_source_root}/executor_aurora_confirm"
    executor_postcheck       = "${var.lambda_source_root}/executor_postcheck"
  }

  # Map each Lambda to its module path (used by the handler reference)
  lambda_handlers = {
    signal_collector         = "lambdas.signal_collector.handler.lambda_handler"
    decision_engine          = "lambdas.decision_engine.handler.lambda_handler"
    indicator_updater        = "lambdas.indicator_updater.handler.lambda_handler"
    manual_trigger           = "lambdas.manual_trigger.handler.lambda_handler"
    approval_callback        = "lambdas.approval_callback.handler.lambda_handler"
    executor_precheck        = "lambdas.executor_precheck.handler.lambda_handler"
    executor_notify          = "lambdas.executor_notify.handler.lambda_handler"
    executor_flip_r53_metric = "lambdas.executor_flip_r53_metric.handler.lambda_handler"
    executor_aurora_confirm  = "lambdas.executor_aurora_confirm.handler.lambda_handler"
    executor_postcheck       = "lambdas.executor_postcheck.handler.lambda_handler"
  }

  endpoint_env_primary = {
    ENDPOINT_SSM           = lookup(var.vpc_endpoint_dns_primary, "ssm", "")
    ENDPOINT_SNS           = lookup(var.vpc_endpoint_dns_primary, "sns", "")
    ENDPOINT_S3            = "https://s3.${var.primary_region}.amazonaws.com"
    ENDPOINT_CLOUDWATCH    = lookup(var.vpc_endpoint_dns_primary, "monitoring", "")
    ENDPOINT_LOGS          = lookup(var.vpc_endpoint_dns_primary, "logs", "")
    ENDPOINT_RDS           = lookup(var.vpc_endpoint_dns_primary, "rds", "")
    ENDPOINT_STEPFUNCTIONS = lookup(var.vpc_endpoint_dns_primary, "states", "")
    ENDPOINT_SYNTHETICS    = lookup(var.vpc_endpoint_dns_primary, "synthetics", "")
    ENDPOINT_HEALTH        = "https://health.us-east-1.amazonaws.com"
    ENDPOINT_EVENTS        = lookup(var.vpc_endpoint_dns_primary, "events", "")
    ENDPOINT_LAMBDA        = lookup(var.vpc_endpoint_dns_primary, "lambda", "")
  }

  endpoint_env_secondary = {
    ENDPOINT_SSM           = lookup(var.vpc_endpoint_dns_secondary, "ssm", "")
    ENDPOINT_SNS           = lookup(var.vpc_endpoint_dns_secondary, "sns", "")
    ENDPOINT_S3            = "https://s3.${var.secondary_region}.amazonaws.com"
    ENDPOINT_CLOUDWATCH    = lookup(var.vpc_endpoint_dns_secondary, "monitoring", "")
    ENDPOINT_LOGS          = lookup(var.vpc_endpoint_dns_secondary, "logs", "")
    ENDPOINT_RDS           = lookup(var.vpc_endpoint_dns_secondary, "rds", "")
    ENDPOINT_STEPFUNCTIONS = lookup(var.vpc_endpoint_dns_secondary, "states", "")
    ENDPOINT_SYNTHETICS    = lookup(var.vpc_endpoint_dns_secondary, "synthetics", "")
    ENDPOINT_HEALTH        = "https://health.us-east-1.amazonaws.com"
    ENDPOINT_EVENTS        = lookup(var.vpc_endpoint_dns_secondary, "events", "")
    ENDPOINT_LAMBDA        = lookup(var.vpc_endpoint_dns_secondary, "lambda", "")
  }
}

data "aws_caller_identity" "current" {}
