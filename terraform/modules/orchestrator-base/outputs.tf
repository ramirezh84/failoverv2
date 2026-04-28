output "vpc_id_primary" {
  description = "Primary region VPC ID."
  value       = aws_vpc.primary.id
}

output "vpc_id_secondary" {
  description = "Secondary region VPC ID."
  value       = aws_vpc.secondary.id
}

output "private_subnet_ids_primary" {
  description = "Private subnet IDs in the primary region (Lambda + ECS attach here)."
  value       = aws_subnet.primary_private[*].id
}

output "private_subnet_ids_secondary" {
  description = "Private subnet IDs in the secondary region."
  value       = aws_subnet.secondary_private[*].id
}

# Subnets where every required VPCE has an ENI. Some services (notably
# AWS Health) only support a subset of AZs per region; a Lambda placed in
# an AZ where its endpoint has no ENI silently times out at 30s.
output "lambda_subnet_ids_primary" {
  description = "Subnets safe for orchestrator Lambdas (intersection of all VPCE-supported AZs, primary)."
  value = [
    for s in aws_subnet.primary_private : s.id
    if alltrue([
      for svc in local.vpc_endpoint_services :
      contains(data.aws_vpc_endpoint_service.primary[svc].availability_zones, s.availability_zone)
    ])
  ]
}

output "lambda_subnet_ids_secondary" {
  description = "Subnets safe for orchestrator Lambdas (intersection of all VPCE-supported AZs, secondary)."
  value = [
    for s in aws_subnet.secondary_private : s.id
    if alltrue([
      for svc in local.vpc_endpoint_services :
      contains(data.aws_vpc_endpoint_service.secondary[svc].availability_zones, s.availability_zone)
    ])
  ]
}

output "routable_subnet_ids_primary" {
  description = "Routable subnet IDs (outer NLB lives here)."
  value       = aws_subnet.primary_routable[*].id
}

output "routable_subnet_ids_secondary" {
  description = "Routable subnet IDs in the secondary region."
  value       = aws_subnet.secondary_routable[*].id
}

output "lambda_security_group_id_primary" {
  description = "Security group every orchestrator Lambda attaches to (primary)."
  value       = aws_security_group.primary_lambda.id
}

output "lambda_security_group_id_secondary" {
  description = "Security group every orchestrator Lambda attaches to (secondary)."
  value       = aws_security_group.secondary_lambda.id
}

output "vpc_endpoint_dns_primary" {
  description = "Map of service -> endpoint DNS in primary; passed to Lambda env as ENDPOINT_*."
  value       = { for k, v in aws_vpc_endpoint.primary_interface : k => "https://${tolist(v.dns_entry)[0].dns_name}" }
}

output "vpc_endpoint_dns_secondary" {
  description = "Map of service -> endpoint DNS in secondary."
  value       = { for k, v in aws_vpc_endpoint.secondary_interface : k => "https://${tolist(v.dns_entry)[0].dns_name}" }
}

output "audit_bucket_primary" {
  description = "Primary audit bucket name."
  value       = aws_s3_bucket.audit_primary.id
}

output "audit_bucket_secondary" {
  description = "Secondary audit bucket name."
  value       = aws_s3_bucket.audit_secondary.id
}

output "profile_bucket_primary" {
  description = "Primary profile bucket name (CRR-replicated)."
  value       = aws_s3_bucket.profile_primary.id
}

output "profile_bucket_secondary" {
  description = "Secondary profile bucket name."
  value       = aws_s3_bucket.profile_secondary.id
}

output "kms_key_arn_primary" {
  description = "KMS key ARN used for SSE on profile + audit buckets, primary."
  value       = aws_kms_key.audit_primary.arn
}

output "kms_key_arn_secondary" {
  description = "KMS key ARN used for SSE on profile + audit buckets, secondary."
  value       = aws_kms_key.audit_secondary.arn
}

output "sns_topic_arn_primary" {
  description = "Account-level SNS topic in primary region."
  value       = aws_sns_topic.events_primary.arn
}

output "sns_topic_arn_secondary" {
  description = "Account-level SNS topic in secondary region."
  value       = aws_sns_topic.events_secondary.arn
}

output "aurora_cluster_id_primary" {
  description = "Aurora cluster identifier (primary)."
  value       = aws_rds_cluster.primary.cluster_identifier
}

output "aurora_cluster_id_secondary" {
  description = "Aurora cluster identifier (secondary)."
  value       = aws_rds_cluster.secondary.cluster_identifier
}

output "aurora_global_cluster_id" {
  description = "Aurora Global Database cluster identifier."
  value       = aws_rds_global_cluster.this.global_cluster_identifier
}

output "ecs_cluster_arn_primary" {
  description = "ECS Fargate cluster ARN (primary)."
  value       = aws_ecs_cluster.primary.arn
}

output "ecs_cluster_arn_secondary" {
  description = "ECS Fargate cluster ARN (secondary)."
  value       = aws_ecs_cluster.secondary.arn
}

output "acm_certificate_arn_primary" {
  description = "Self-signed leaf cert ACM ARN (primary, for outer NLB TLS listener)."
  value       = aws_acm_certificate.primary.arn
}

output "acm_certificate_arn_secondary" {
  description = "Self-signed leaf cert ACM ARN (secondary)."
  value       = aws_acm_certificate.secondary.arn
}

output "route53_zone_id" {
  description = "Private hosted zone for the failover record."
  value       = aws_route53_zone.private.zone_id
}

output "route53_zone_name" {
  description = "FQDN of the private hosted zone."
  value       = aws_route53_zone.private.name
}
