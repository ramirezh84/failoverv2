###############################################################################
# Cross-region synthetic canaries.
# CLAUDE.md §11 pitfall #4 — canary in opposite region probes its target.
###############################################################################

data "aws_iam_policy_document" "canary_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "canary_primary" {
  provider           = aws.use1
  name               = "${var.app_name}-canary-use1"
  assume_role_policy = data.aws_iam_policy_document.canary_assume.json
  tags               = merge(local.common_tags_use1, { component = "iam-role" })
}

resource "aws_iam_role" "canary_secondary" {
  provider           = aws.use2
  name               = "${var.app_name}-canary-use2"
  assume_role_policy = data.aws_iam_policy_document.canary_assume.json
  tags               = merge(local.common_tags_use2, { component = "iam-role" })
}

resource "aws_iam_role_policy_attachment" "canary_primary_basic" {
  provider   = aws.use1
  role       = aws_iam_role.canary_primary.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "canary_secondary_basic" {
  provider   = aws.use2
  role       = aws_iam_role.canary_secondary.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "canary_primary_inline" {
  statement {
    sid       = "writeCanaryArtifacts"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
    resources = ["arn:aws:s3:::${var.audit_bucket_primary}", "arn:aws:s3:::${var.audit_bucket_primary}/canary/*"]
  }
  statement {
    sid       = "putMetric"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"] # iam-policy-check: allow-wildcard 
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["CloudWatchSynthetics"]
    }
  }
}

resource "aws_iam_role_policy" "canary_primary" {
  provider = aws.use1
  name     = "${var.app_name}-canary-policy"
  role     = aws_iam_role.canary_primary.id
  policy   = data.aws_iam_policy_document.canary_primary_inline.json
}

data "aws_iam_policy_document" "canary_secondary_inline" {
  statement {
    sid       = "writeCanaryArtifacts"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
    resources = ["arn:aws:s3:::${var.audit_bucket_secondary}", "arn:aws:s3:::${var.audit_bucket_secondary}/canary/*"]
  }
  statement {
    sid       = "putMetric"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"] # iam-policy-check: allow-wildcard 
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["CloudWatchSynthetics"]
    }
  }
}

resource "aws_iam_role_policy" "canary_secondary" {
  provider = aws.use2
  name     = "${var.app_name}-canary-policy"
  role     = aws_iam_role.canary_secondary.id
  policy   = data.aws_iam_policy_document.canary_secondary_inline.json
}

# Package the probe script under canaries/.
data "archive_file" "canary_zip" {
  type        = "zip"
  output_path = "${path.module}/.builds/canary.zip"
  source_dir  = "${path.module}/../../../canaries"
}

# Canary in primary region probes the SECONDARY region's routable URL.
resource "aws_synthetics_canary" "in_primary_probes_secondary" {
  provider             = aws.use1
  name                 = substr("probe-${replace(var.route53_zone_name, ".", "-")}-2", 0, 21)
  artifact_s3_location = "s3://${var.audit_bucket_primary}/canary/in-use1-probes-use2/"
  execution_role_arn   = aws_iam_role.canary_primary.arn
  handler              = "routable_endpoint_probe.handler"
  zip_file             = data.archive_file.canary_zip.output_path
  runtime_version      = "syn-python-selenium-10.0"
  start_canary         = true

  schedule {
    expression          = "rate(1 minute)"
    duration_in_seconds = 0
  }
  run_config {
    timeout_in_seconds = 30
    memory_in_mb       = 960
    active_tracing     = true
    environment_variables = {
      TARGET_URL        = "https://${var.app_name}.${var.secondary_region}.${var.route53_zone_name}/health"
      IGNORE_TLS_ERRORS = "true"
    }
  }
  success_retention_period = 7
  failure_retention_period = 30
  tags                     = merge(local.common_tags_use1, { component = "canary", probes = var.secondary_region })
}

resource "aws_synthetics_canary" "in_secondary_probes_primary" {
  provider             = aws.use2
  name                 = substr("probe-${replace(var.route53_zone_name, ".", "-")}-1", 0, 21)
  artifact_s3_location = "s3://${var.audit_bucket_secondary}/canary/in-use2-probes-use1/"
  execution_role_arn   = aws_iam_role.canary_secondary.arn
  handler              = "routable_endpoint_probe.handler"
  zip_file             = data.archive_file.canary_zip.output_path
  runtime_version      = "syn-python-selenium-10.0"
  start_canary         = true

  schedule {
    expression          = "rate(1 minute)"
    duration_in_seconds = 0
  }
  run_config {
    timeout_in_seconds = 30
    memory_in_mb       = 960
    active_tracing     = true
    environment_variables = {
      TARGET_URL        = "https://${var.app_name}.${var.primary_region}.${var.route53_zone_name}/health"
      IGNORE_TLS_ERRORS = "true"
    }
  }
  success_retention_period = 7
  failure_retention_period = 30
  tags                     = merge(local.common_tags_use2, { component = "canary", probes = var.primary_region })
}
