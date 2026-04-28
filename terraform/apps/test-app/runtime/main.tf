data "terraform_remote_state" "base" {
  backend = "s3"
  config = {
    bucket = var.base_state_bucket
    key    = "apps/${var.app_name}/base/terraform.tfstate"
    region = "us-east-1"
  }
}

module "orchestrator_runtime" {
  source           = "../../../modules/orchestrator-runtime"
  providers        = { aws.use1 = aws.use1, aws.use2 = aws.use2 }
  app_name         = var.app_name
  primary_region   = var.primary_region
  secondary_region = var.secondary_region

  lambda_source_root = "${path.module}/../../../../lambdas"
  lib_source_root    = "${path.module}/../../../../lib"
  statemachines_root = "${path.module}/../../../../statemachines"

  vpc_id_primary                     = data.terraform_remote_state.base.outputs.vpc_id_primary
  vpc_id_secondary                   = data.terraform_remote_state.base.outputs.vpc_id_secondary
  private_subnet_ids_primary         = data.terraform_remote_state.base.outputs.private_subnet_ids_primary
  private_subnet_ids_secondary       = data.terraform_remote_state.base.outputs.private_subnet_ids_secondary
  lambda_security_group_id_primary   = data.terraform_remote_state.base.outputs.lambda_security_group_id_primary
  lambda_security_group_id_secondary = data.terraform_remote_state.base.outputs.lambda_security_group_id_secondary
  vpc_endpoint_dns_primary           = data.terraform_remote_state.base.outputs.vpc_endpoint_dns_primary
  vpc_endpoint_dns_secondary         = data.terraform_remote_state.base.outputs.vpc_endpoint_dns_secondary
  profile_bucket_primary             = data.terraform_remote_state.base.outputs.profile_bucket_primary
  profile_bucket_secondary           = data.terraform_remote_state.base.outputs.profile_bucket_secondary
  audit_bucket_primary               = data.terraform_remote_state.base.outputs.audit_bucket_primary
  audit_bucket_secondary             = data.terraform_remote_state.base.outputs.audit_bucket_secondary
  kms_key_arn_primary                = data.terraform_remote_state.base.outputs.kms_key_arn_primary
  kms_key_arn_secondary              = data.terraform_remote_state.base.outputs.kms_key_arn_secondary
  sns_topic_arn_primary              = data.terraform_remote_state.base.outputs.sns_topic_arn_primary
  sns_topic_arn_secondary            = data.terraform_remote_state.base.outputs.sns_topic_arn_secondary
  aurora_global_cluster_id           = data.terraform_remote_state.base.outputs.aurora_global_cluster_id
  route53_zone_id                    = data.terraform_remote_state.base.outputs.route53_zone_id
  route53_zone_name                  = data.terraform_remote_state.base.outputs.route53_zone_name
}
