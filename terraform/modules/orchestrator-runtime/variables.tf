variable "app_name" {
  description = "DNS-safe app slug; matches orchestrator-base."
  type        = string
}

variable "primary_region" {
  description = "Primary AWS region."
  type        = string
}

variable "secondary_region" {
  description = "Secondary AWS region."
  type        = string
}

variable "lambda_source_root" {
  description = "Local filesystem path to the lambdas/ directory."
  type        = string
}

variable "lib_source_root" {
  description = "Local filesystem path to the lib/ directory."
  type        = string
}

variable "statemachines_root" {
  description = "Local filesystem path to statemachines/."
  type        = string
}

variable "vpc_id_primary" {
  description = "VPC id (primary). Currently unused inside the module — accepted so the test-app stack can pass it without breaking; reserved for future security-group attachments."
  type        = string
  default     = ""
  nullable    = true
}

variable "vpc_id_secondary" {
  description = "VPC id (secondary). Same status as vpc_id_primary."
  type        = string
  default     = ""
  nullable    = true
}

variable "private_subnet_ids_primary" {
  description = "Private subnet ids (primary)."
  type        = list(string)
}

variable "private_subnet_ids_secondary" {
  description = "Private subnet ids (secondary)."
  type        = list(string)
}

variable "lambda_security_group_id_primary" {
  description = "Lambda SG (primary) from base."
  type        = string
}

variable "lambda_security_group_id_secondary" {
  description = "Lambda SG (secondary) from base."
  type        = string
}

variable "vpc_endpoint_dns_primary" {
  description = "Service -> endpoint DNS map (primary), used to set ENDPOINT_* env vars."
  type        = map(string)
}

variable "vpc_endpoint_dns_secondary" {
  description = "Service -> endpoint DNS map (secondary)."
  type        = map(string)
}

variable "profile_bucket_primary" {
  description = "Primary profile bucket name."
  type        = string
}

variable "profile_bucket_secondary" {
  description = "Secondary profile bucket name."
  type        = string
}

variable "audit_bucket_primary" {
  description = "Primary audit bucket name."
  type        = string
}

variable "audit_bucket_secondary" {
  description = "Secondary audit bucket name."
  type        = string
}

variable "kms_key_arn_primary" {
  description = "KMS key (primary) used to read/write profile + audit buckets."
  type        = string
}

variable "kms_key_arn_secondary" {
  description = "KMS key (secondary)."
  type        = string
}

variable "sns_topic_arn_primary" {
  description = "Account-level SNS topic ARN (primary)."
  type        = string
}

variable "sns_topic_arn_secondary" {
  description = "Account-level SNS topic ARN (secondary)."
  type        = string
}

variable "aurora_global_cluster_id" {
  description = "Aurora Global Database identifier."
  type        = string
}

variable "route53_zone_id" {
  description = "Private hosted zone ID."
  type        = string
}

variable "route53_zone_name" {
  description = "Hosted zone FQDN (without trailing dot)."
  type        = string
}

variable "tags" {
  description = "Common tags merged onto every resource."
  type        = map(string)
  default = {
    managed_by = "terraform"
    repo       = "failoverv2"
    env        = "poc"
  }
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention for every Lambda."
  type        = number
  default     = 30
}
