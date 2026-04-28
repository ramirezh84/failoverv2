locals {
  common_tags = merge(var.tags, {
    app  = var.app_name
    repo = "failoverv2"
  })
  common_tags_use1 = merge(local.common_tags, { region = var.primary_region })
  common_tags_use2 = merge(local.common_tags, { region = var.secondary_region })
}

# aws_caller_identity not currently consumed; left out to satisfy
# tflint terraform_unused_declarations.
