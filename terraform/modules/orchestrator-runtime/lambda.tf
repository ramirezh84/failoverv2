###############################################################################
# Lambda functions. We package each Lambda's directory plus the lib/ directory
# into a zip and deploy two copies (one per region). Each Lambda is VPC-attached
# in private subnets — vpc-endpoint-check CI job enforces this.
#
# Third-party deps (pyyaml, pydantic, jsonschema) ship via a Lambda Layer.
# boto3/botocore are pre-installed in the Lambda runtime, so we don't bundle
# them.
###############################################################################

# Build the deps layer: pip install into .builds/deps/python so the layer
# unpacks at /opt/python (Lambda's default PYTHONPATH for layers).
resource "null_resource" "deps_layer_build" {
  triggers = {
    deps_hash = sha256("pyyaml==6.0.2|pydantic==2.9.2|jsonschema==4.23.0")
  }
  provisioner "local-exec" {
    command = <<-EOT
      set -e
      rm -rf ${path.module}/.builds/deps
      mkdir -p ${path.module}/.builds/deps/python
      pip3 install \
        --quiet \
        --platform manylinux2014_x86_64 \
        --implementation cp \
        --python-version 3.13 \
        --only-binary=:all: \
        --target ${path.module}/.builds/deps/python \
        pyyaml==6.0.2 pydantic==2.9.2 jsonschema==4.23.0
    EOT
  }
}

data "archive_file" "deps_layer_zip" {
  type        = "zip"
  source_dir  = "${path.module}/.builds/deps"
  output_path = "${path.module}/.builds/deps-layer.zip"
  depends_on  = [null_resource.deps_layer_build]
}

resource "aws_lambda_layer_version" "deps_primary" {
  provider                 = aws.use1
  layer_name               = "${var.app_name}-deps"
  filename                 = data.archive_file.deps_layer_zip.output_path
  source_code_hash         = data.archive_file.deps_layer_zip.output_base64sha256
  compatible_runtimes      = ["python3.13"]
  compatible_architectures = ["x86_64"]
}

resource "aws_lambda_layer_version" "deps_secondary" {
  provider                 = aws.use2
  layer_name               = "${var.app_name}-deps"
  filename                 = data.archive_file.deps_layer_zip.output_path
  source_code_hash         = data.archive_file.deps_layer_zip.output_base64sha256
  compatible_runtimes      = ["python3.13"]
  compatible_architectures = ["x86_64"]
}

# Build one zip per Lambda. Each zip contains every Lambda's source under
# lambdas/* + lib/* + profile schema. Bundling all lambdas keeps cross-module
# imports working (e.g., executor_postcheck → executor_precheck.logic).
locals {
  all_lambda_files = toset([
    for p in fileset(var.lambda_source_root, "*/*.py") : p
    if !startswith(basename(p), "test_")
  ])
}

data "archive_file" "lambda_zip" {
  for_each    = local.lambda_packages
  type        = "zip"
  output_path = "${path.module}/.builds/${each.key}.zip"

  dynamic "source" {
    for_each = local.all_lambda_files
    content {
      content  = file("${var.lambda_source_root}/${source.value}")
      filename = "lambdas/${source.value}"
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
  # Bundle the profile JSON Schema (lib.profile_loader resolves it via
  # lib/../profiles/profile.schema.json → /var/task/profiles/profile.schema.json).
  source {
    content  = file("${var.lib_source_root}/../profiles/profile.schema.json")
    filename = "profiles/profile.schema.json"
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

  layers = [aws_lambda_layer_version.deps_primary.arn]

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

  layers = [aws_lambda_layer_version.deps_secondary.arn]

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
