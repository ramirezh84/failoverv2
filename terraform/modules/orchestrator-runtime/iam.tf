###############################################################################
# IAM roles and policies for the orchestrator Lambdas.
# CLAUDE.md §2 #5: NO Action:* and NO Resource:*. Every action enumerated.
# We use one role per region with the union of permissions; per-Lambda role
# splitting is a JPMC-port enhancement.
###############################################################################

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ---- Primary region role ----
resource "aws_iam_role" "lambda_primary" {
  provider           = aws.use1
  name               = "${var.app_name}-orchestrator-lambda-use1"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = merge(local.common_tags_use1, { component = "iam-role" })
}

resource "aws_iam_role_policy_attachment" "lambda_primary_basic" {
  provider   = aws.use1
  role       = aws_iam_role.lambda_primary.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_primary_vpc" {
  provider   = aws.use1
  role       = aws_iam_role.lambda_primary.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

data "aws_iam_policy_document" "lambda_primary" {
  # SSM
  statement {
    sid     = "ssmReadWrite"
    actions = ["ssm:GetParameter", "ssm:PutParameter", "ssm:DeleteParameter"]
    resources = [
      "arn:aws:ssm:${var.primary_region}:${data.aws_caller_identity.current.account_id}:parameter/failover/${var.app_name}/*",
    ]
  }
  # CloudWatch metrics
  statement {
    sid       = "cloudwatchMetrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"] # iam-policy-check: allow-wildcard AWS requires "*" for PutMetricData; restricted via condition
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values = [
        "Failover/${var.app_name}",
        "Failover/${var.app_name}/Signals",
      ]
    }
  }
  statement {
    sid       = "cloudwatchRead"
    actions   = ["cloudwatch:GetMetricStatistics", "cloudwatch:GetMetricData", "cloudwatch:ListMetrics", "cloudwatch:DescribeAlarms"]
    resources = ["*"] # iam-policy-check: allow-wildcard CW Get/List APIs do not support resource-level
  }
  # SNS
  statement {
    sid       = "snsPublish"
    actions   = ["sns:Publish"]
    resources = [var.sns_topic_arn_primary]
  }
  # S3
  statement {
    sid     = "s3ReadProfile"
    actions = ["s3:GetObject", "s3:ListBucket"]
    resources = [
      "arn:aws:s3:::${var.profile_bucket_primary}",
      "arn:aws:s3:::${var.profile_bucket_primary}/*",
    ]
  }
  statement {
    sid       = "s3WriteAudit"
    actions   = ["s3:PutObject"]
    resources = ["arn:aws:s3:::${var.audit_bucket_primary}/*"]
  }
  statement {
    sid       = "kms"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [var.kms_key_arn_primary]
  }
  # RDS
  statement {
    sid     = "rdsRead"
    actions = ["rds:DescribeDBClusters", "rds:DescribeGlobalClusters"]
    resources = [
      "arn:aws:rds::${data.aws_caller_identity.current.account_id}:global-cluster:${var.aurora_global_cluster_id}",
      "arn:aws:rds:${var.primary_region}:${data.aws_caller_identity.current.account_id}:cluster:${var.app_name}-use1",
      "arn:aws:rds:${var.secondary_region}:${data.aws_caller_identity.current.account_id}:cluster:${var.app_name}-use2",
    ]
  }
  # Step Functions task token + execution start
  statement {
    sid     = "stepfunctionsCallback"
    actions = ["states:SendTaskSuccess", "states:SendTaskFailure", "states:SendTaskHeartbeat"]
    resources = [
      "arn:aws:states:${var.primary_region}:${data.aws_caller_identity.current.account_id}:stateMachine:*${var.app_name}*",
    ]
  }
  statement {
    sid     = "stepfunctionsStart"
    actions = ["states:StartExecution", "states:DescribeExecution"]
    resources = [
      "arn:aws:states:${var.primary_region}:${data.aws_caller_identity.current.account_id}:stateMachine:${var.app_name}-failover",
      "arn:aws:states:${var.primary_region}:${data.aws_caller_identity.current.account_id}:stateMachine:${var.app_name}-failback",
      "arn:aws:states:${var.primary_region}:${data.aws_caller_identity.current.account_id}:execution:${var.app_name}-failover:*",
      "arn:aws:states:${var.primary_region}:${data.aws_caller_identity.current.account_id}:execution:${var.app_name}-failback:*",
    ]
  }
  # Health
  statement {
    sid       = "healthRead"
    actions   = ["health:DescribeEvents"]
    resources = ["*"] # iam-policy-check: allow-wildcard Health API does not support resource-level
  }
}

resource "aws_iam_role_policy" "lambda_primary" {
  provider = aws.use1
  name     = "${var.app_name}-orchestrator-policy"
  role     = aws_iam_role.lambda_primary.id
  policy   = data.aws_iam_policy_document.lambda_primary.json
}

# ---- Secondary region role (mirror) ----
resource "aws_iam_role" "lambda_secondary" {
  provider           = aws.use2
  name               = "${var.app_name}-orchestrator-lambda-use2"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = merge(local.common_tags_use2, { component = "iam-role" })
}

resource "aws_iam_role_policy_attachment" "lambda_secondary_basic" {
  provider   = aws.use2
  role       = aws_iam_role.lambda_secondary.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_secondary_vpc" {
  provider   = aws.use2
  role       = aws_iam_role.lambda_secondary.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

data "aws_iam_policy_document" "lambda_secondary" {
  statement {
    sid     = "ssmReadWrite"
    actions = ["ssm:GetParameter", "ssm:PutParameter", "ssm:DeleteParameter"]
    resources = [
      "arn:aws:ssm:${var.secondary_region}:${data.aws_caller_identity.current.account_id}:parameter/failover/${var.app_name}/*",
    ]
  }
  statement {
    sid       = "cloudwatchMetrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"] # iam-policy-check: allow-wildcard 
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values = [
        "Failover/${var.app_name}",
        "Failover/${var.app_name}/Signals",
      ]
    }
  }
  statement {
    sid       = "cloudwatchRead"
    actions   = ["cloudwatch:GetMetricStatistics", "cloudwatch:GetMetricData", "cloudwatch:ListMetrics", "cloudwatch:DescribeAlarms"]
    resources = ["*"] # iam-policy-check: allow-wildcard 
  }
  statement {
    sid       = "snsPublish"
    actions   = ["sns:Publish"]
    resources = [var.sns_topic_arn_secondary]
  }
  statement {
    sid     = "s3ReadProfile"
    actions = ["s3:GetObject", "s3:ListBucket"]
    resources = [
      "arn:aws:s3:::${var.profile_bucket_secondary}",
      "arn:aws:s3:::${var.profile_bucket_secondary}/*",
    ]
  }
  statement {
    sid       = "s3WriteAudit"
    actions   = ["s3:PutObject"]
    resources = ["arn:aws:s3:::${var.audit_bucket_secondary}/*"]
  }
  statement {
    sid       = "kms"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [var.kms_key_arn_secondary]
  }
  statement {
    sid     = "rdsRead"
    actions = ["rds:DescribeDBClusters", "rds:DescribeGlobalClusters"]
    resources = [
      "arn:aws:rds::${data.aws_caller_identity.current.account_id}:global-cluster:${var.aurora_global_cluster_id}",
      "arn:aws:rds:${var.primary_region}:${data.aws_caller_identity.current.account_id}:cluster:${var.app_name}-use1",
      "arn:aws:rds:${var.secondary_region}:${data.aws_caller_identity.current.account_id}:cluster:${var.app_name}-use2",
    ]
  }
  statement {
    sid     = "stepfunctionsCallback"
    actions = ["states:SendTaskSuccess", "states:SendTaskFailure", "states:SendTaskHeartbeat"]
    resources = [
      "arn:aws:states:${var.secondary_region}:${data.aws_caller_identity.current.account_id}:stateMachine:*${var.app_name}*",
    ]
  }
  statement {
    sid     = "stepfunctionsStart"
    actions = ["states:StartExecution", "states:DescribeExecution"]
    resources = [
      "arn:aws:states:${var.secondary_region}:${data.aws_caller_identity.current.account_id}:stateMachine:${var.app_name}-failover",
      "arn:aws:states:${var.secondary_region}:${data.aws_caller_identity.current.account_id}:stateMachine:${var.app_name}-failback",
      "arn:aws:states:${var.secondary_region}:${data.aws_caller_identity.current.account_id}:execution:${var.app_name}-failover:*",
      "arn:aws:states:${var.secondary_region}:${data.aws_caller_identity.current.account_id}:execution:${var.app_name}-failback:*",
    ]
  }
  statement {
    sid       = "healthRead"
    actions   = ["health:DescribeEvents"]
    resources = ["*"] # iam-policy-check: allow-wildcard 
  }
}

resource "aws_iam_role_policy" "lambda_secondary" {
  provider = aws.use2
  name     = "${var.app_name}-orchestrator-policy"
  role     = aws_iam_role.lambda_secondary.id
  policy   = data.aws_iam_policy_document.lambda_secondary.json
}

# ---- Step Functions execution role ----
data "aws_iam_policy_document" "sfn_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sfn_primary" {
  provider           = aws.use1
  name               = "${var.app_name}-sfn-use1"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume_role.json
  tags               = merge(local.common_tags_use1, { component = "iam-role" })
}

data "aws_iam_policy_document" "sfn_primary" {
  statement {
    sid       = "invokeOrchestratorLambdas"
    actions   = ["lambda:InvokeFunction"]
    resources = [for k, _ in local.lambda_packages : aws_lambda_function.primary[k].arn]
  }
  statement {
    sid       = "publishToSnsForTaskToken"
    actions   = ["sns:Publish"]
    resources = [var.sns_topic_arn_primary]
  }
  statement {
    sid = "logsForExecutionData"
    actions = [
      "logs:CreateLogDelivery",
      "logs:GetLogDelivery",
      "logs:UpdateLogDelivery",
      "logs:DeleteLogDelivery",
      "logs:ListLogDeliveries",
      "logs:PutResourcePolicy",
      "logs:DescribeResourcePolicies",
      "logs:DescribeLogGroups",
    ]
    resources = ["*"] # iam-policy-check: allow-wildcard SFN log-delivery API requires *
  }
}

resource "aws_iam_role_policy" "sfn_primary" {
  provider = aws.use1
  name     = "${var.app_name}-sfn-policy"
  role     = aws_iam_role.sfn_primary.id
  policy   = data.aws_iam_policy_document.sfn_primary.json
}

resource "aws_iam_role" "sfn_secondary" {
  provider           = aws.use2
  name               = "${var.app_name}-sfn-use2"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume_role.json
  tags               = merge(local.common_tags_use2, { component = "iam-role" })
}

data "aws_iam_policy_document" "sfn_secondary" {
  statement {
    sid       = "invokeOrchestratorLambdas"
    actions   = ["lambda:InvokeFunction"]
    resources = [for k, _ in local.lambda_packages : aws_lambda_function.secondary[k].arn]
  }
  statement {
    sid       = "publishToSnsForTaskToken"
    actions   = ["sns:Publish"]
    resources = [var.sns_topic_arn_secondary]
  }
  statement {
    sid = "logsForExecutionData"
    actions = [
      "logs:CreateLogDelivery",
      "logs:GetLogDelivery",
      "logs:UpdateLogDelivery",
      "logs:DeleteLogDelivery",
      "logs:ListLogDeliveries",
      "logs:PutResourcePolicy",
      "logs:DescribeResourcePolicies",
      "logs:DescribeLogGroups",
    ]
    resources = ["*"] # iam-policy-check: allow-wildcard SFN log-delivery API requires *
  }
}

resource "aws_iam_role_policy" "sfn_secondary" {
  provider = aws.use2
  name     = "${var.app_name}-sfn-policy"
  role     = aws_iam_role.sfn_secondary.id
  policy   = data.aws_iam_policy_document.sfn_secondary.json
}
