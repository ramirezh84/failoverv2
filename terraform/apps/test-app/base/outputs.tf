output "vpc_id_primary" {
  description = "Pass-through: orchestrator-base.vpc_id_primary."
  value       = module.orchestrator_base.vpc_id_primary
}
output "vpc_id_secondary" {
  description = "Pass-through: orchestrator-base.vpc_id_secondary."
  value       = module.orchestrator_base.vpc_id_secondary
}
output "private_subnet_ids_primary" {
  description = "Pass-through: orchestrator-base.private_subnet_ids_primary."
  value       = module.orchestrator_base.private_subnet_ids_primary
}
output "private_subnet_ids_secondary" {
  description = "Pass-through: orchestrator-base.private_subnet_ids_secondary."
  value       = module.orchestrator_base.private_subnet_ids_secondary
}
output "lambda_security_group_id_primary" {
  description = "Pass-through."
  value       = module.orchestrator_base.lambda_security_group_id_primary
}
output "lambda_security_group_id_secondary" {
  description = "Pass-through."
  value       = module.orchestrator_base.lambda_security_group_id_secondary
}
output "vpc_endpoint_dns_primary" {
  description = "Pass-through: ENDPOINT_* env source for runtime."
  value       = module.orchestrator_base.vpc_endpoint_dns_primary
}
output "vpc_endpoint_dns_secondary" {
  description = "Pass-through."
  value       = module.orchestrator_base.vpc_endpoint_dns_secondary
}
output "audit_bucket_primary" {
  description = "Pass-through."
  value       = module.orchestrator_base.audit_bucket_primary
}
output "audit_bucket_secondary" {
  description = "Pass-through."
  value       = module.orchestrator_base.audit_bucket_secondary
}
output "profile_bucket_primary" {
  description = "Pass-through."
  value       = module.orchestrator_base.profile_bucket_primary
}
output "profile_bucket_secondary" {
  description = "Pass-through."
  value       = module.orchestrator_base.profile_bucket_secondary
}
output "kms_key_arn_primary" {
  description = "Pass-through."
  value       = module.orchestrator_base.kms_key_arn_primary
}
output "kms_key_arn_secondary" {
  description = "Pass-through."
  value       = module.orchestrator_base.kms_key_arn_secondary
}
output "sns_topic_arn_primary" {
  description = "Pass-through: account-level SNS topic ARN."
  value       = module.orchestrator_base.sns_topic_arn_primary
}
output "sns_topic_arn_secondary" {
  description = "Pass-through."
  value       = module.orchestrator_base.sns_topic_arn_secondary
}
output "aurora_global_cluster_id" {
  description = "Pass-through."
  value       = module.orchestrator_base.aurora_global_cluster_id
}
output "route53_zone_id" {
  description = "Pass-through."
  value       = module.orchestrator_base.route53_zone_id
}
output "route53_zone_name" {
  description = "Pass-through."
  value       = module.orchestrator_base.route53_zone_name
}
output "outer_nlb_arn_primary" {
  description = "Test-harness app outer NLB ARN (primary)."
  value       = module.test_harness_app.outer_nlb_arn_primary
}
output "outer_nlb_arn_secondary" {
  description = "Test-harness app outer NLB ARN (secondary)."
  value       = module.test_harness_app.outer_nlb_arn_secondary
}
output "alb_arn_primary" {
  description = "Test-harness app inner ALB ARN (primary)."
  value       = module.test_harness_app.alb_arn_primary
}
output "alb_arn_secondary" {
  description = "Test-harness app inner ALB ARN (secondary)."
  value       = module.test_harness_app.alb_arn_secondary
}
