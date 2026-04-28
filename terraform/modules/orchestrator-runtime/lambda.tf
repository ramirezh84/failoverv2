###############################################################################
# Lambda functions. We package each Lambda's directory plus the lib/ directory
# into a zip and deploy two copies (one per region). Each Lambda is VPC-attached
# in private subnets — vpc-endpoint-check CI job enforces this.
###############################################################################

# Build one zip per Lambda. Each zip contains: lambdas/<name>/* + lib/*
# archive_file recomputes its hash whenever any source file changes, so a
# separate null_resource trigger isn't needed.
data "archive_file" "lambda_zip" {
  for_each    = local.lambda_packages
  type        = "zip"
  output_path = "${path.module}/.builds/${each.key}.zip"

  source {
    content  = file("${each.value}/handler.py")
    filename = "lambdas/${each.key}/handler.py"
  }
  source {
    content  = file("${each.value}/__init__.py")
    filename = "lambdas/${each.key}/__init__.py"
  }
  # logic.py + aws.py optional per Lambda
  dynamic "source" {
    for_each = fileexists("${each.value}/logic.py") ? [1] : []
    content {
      content  = file("${each.value}/logic.py")
      filename = "lambdas/${each.key}/logic.py"
    }
  }
  dynamic "source" {
    for_each = fileexists("${each.value}/aws.py") ? [1] : []
    content {
      content  = file("${each.value}/aws.py")
      filename = "lambdas/${each.key}/aws.py"
    }
  }
  source {
    content  = ""
    filename = "lambdas/__init__.py"
  }
  # Bundle the shared library
  dynamic "source" {
    for_each = fileset(var.lib_source_root, "*.py")
    content {
      content  = file("${var.lib_source_root}/${source.value}")
      filename = "lib/${source.value}"
    }
  }
}

# CloudWatch log groups (created up front so retention is set even before
# first invocation creates them implicitly).
resource "aws_cloudwatch_log_group" "primary" {
  for_each          = local.lambda_packages
  provider          = aws.use1
  name              = "/aws/lambda/${var.app_name}-${each.key}-use1"
  retention_in_days = var.log_retention_days
  tags              = merge(local.common_tags_use1, { component = "log-group" })
}

resource "aws_cloudwatch_log_group" "secondary" {
  for_each          = local.lambda_packages
  provider          = aws.use2
  name              = "/aws/lambda/${var.app_name}-${each.key}-use2"
  retention_in_days = var.log_retention_days
  tags              = merge(local.common_tags_use2, { component = "log-group" })
}

# ---- Primary region Lambdas ----
resource "aws_lambda_function" "primary" {
  for_each         = local.lambda_packages
  provider         = aws.use1
  function_name    = "${var.app_name}-${each.key}-use1"
  role             = aws_iam_role.lambda_primary.arn
  runtime          = "python3.13" # 3.14 is not yet available in all regions; bump later
  handler          = local.lambda_handlers[each.key]
  memory_size      = 256
  timeout          = each.key == "executor_aurora_confirm" ? 60 : 30
  filename         = data.archive_file.lambda_zip[each.key].output_path
  source_code_hash = data.archive_file.lambda_zip[each.key].output_base64sha256

  vpc_config {
    subnet_ids         = var.private_subnet_ids_primary
    security_group_ids = [var.lambda_security_group_id_primary]
  }

  environment {
    variables = merge(
      local.endpoint_env_primary,
      {
        APP_NAME                   = var.app_name
        PROFILE_BUCKET             = var.profile_bucket_primary
        PROFILE_KEY                = "${var.app_name}/profile.yaml"
        AUDIT_BUCKET               = var.audit_bucket_primary
        SNS_TOPIC_ARN              = var.sns_topic_arn_primary
        FAILOVER_STATE_MACHINE_ARN = "arn:aws:states:${var.primary_region}:${data.aws_caller_identity.current.account_id}:stateMachine:${var.app_name}-failover"
        FAILBACK_STATE_MACHINE_ARN = "arn:aws:states:${var.primary_region}:${data.aws_caller_identity.current.account_id}:stateMachine:${var.app_name}-failback"
        LOG_LEVEL                  = "INFO"
      },
    )
  }

  tracing_config { mode = "Active" }
  tags = merge(local.common_tags_use1, { component = "lambda", lambda_name = each.key })

  depends_on = [aws_cloudwatch_log_group.primary]
}

resource "aws_lambda_function" "secondary" {
  for_each         = local.lambda_packages
  provider         = aws.use2
  function_name    = "${var.app_name}-${each.key}-use2"
  role             = aws_iam_role.lambda_secondary.arn
  runtime          = "python3.13"
  handler          = local.lambda_handlers[each.key]
  memory_size      = 256
  timeout          = each.key == "executor_aurora_confirm" ? 60 : 30
  filename         = data.archive_file.lambda_zip[each.key].output_path
  source_code_hash = data.archive_file.lambda_zip[each.key].output_base64sha256

  vpc_config {
    subnet_ids         = var.private_subnet_ids_secondary
    security_group_ids = [var.lambda_security_group_id_secondary]
  }

  environment {
    variables = merge(
      local.endpoint_env_secondary,
      {
        APP_NAME                   = var.app_name
        PROFILE_BUCKET             = var.profile_bucket_secondary
        PROFILE_KEY                = "${var.app_name}/profile.yaml"
        AUDIT_BUCKET               = var.audit_bucket_secondary
        SNS_TOPIC_ARN              = var.sns_topic_arn_secondary
        FAILOVER_STATE_MACHINE_ARN = "arn:aws:states:${var.secondary_region}:${data.aws_caller_identity.current.account_id}:stateMachine:${var.app_name}-failover"
        FAILBACK_STATE_MACHINE_ARN = "arn:aws:states:${var.secondary_region}:${data.aws_caller_identity.current.account_id}:stateMachine:${var.app_name}-failback"
        LOG_LEVEL                  = "INFO"
      },
    )
  }

  tracing_config { mode = "Active" }
  tags = merge(local.common_tags_use2, { component = "lambda", lambda_name = each.key })

  depends_on = [aws_cloudwatch_log_group.secondary]
}
