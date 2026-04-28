variable "app_name" {
  description = "App slug (matches orchestrator-base)."
  type        = string
}

variable "primary_region" {
  description = "Primary region."
  type        = string
}

variable "secondary_region" {
  description = "Secondary region."
  type        = string
}

variable "vpc_id_primary" {
  description = "Primary VPC id."
  type        = string
}

variable "vpc_id_secondary" {
  description = "Secondary VPC id."
  type        = string
}

variable "private_subnet_ids_primary" {
  description = "Private subnet ids (primary)."
  type        = list(string)
}

variable "private_subnet_ids_secondary" {
  description = "Private subnet ids (secondary)."
  type        = list(string)
}

variable "routable_subnet_ids_primary" {
  description = "Routable subnet ids (primary). Outer NLB lives here."
  type        = list(string)
}

variable "routable_subnet_ids_secondary" {
  description = "Routable subnet ids (secondary)."
  type        = list(string)
}

variable "ecs_cluster_arn_primary" {
  description = "ECS cluster ARN (primary)."
  type        = string
}

variable "ecs_cluster_arn_secondary" {
  description = "ECS cluster ARN (secondary)."
  type        = string
}

variable "acm_certificate_arn_primary" {
  description = "ACM cert ARN (self-signed leaf, primary, for outer NLB TLS listener)."
  type        = string
}

variable "acm_certificate_arn_secondary" {
  description = "ACM cert ARN (self-signed leaf, secondary)."
  type        = string
}

variable "route53_zone_id" {
  description = "Hosted zone id."
  type        = string
}

variable "route53_zone_name" {
  description = "Hosted zone FQDN."
  type        = string
}

variable "tags" {
  description = "Common tags."
  type        = map(string)
  default = {
    managed_by = "terraform"
    repo       = "failoverv2"
    env        = "poc"
  }
}

variable "container_image" {
  description = "Synthetic ECS app container image. Default: a small open echo image. Replace with the test-app image when iterating scenarios."
  type        = string
  default     = "public.ecr.aws/nginx/nginx:1.27"
}

variable "container_port" {
  description = "Port the synthetic app listens on."
  type        = number
  default     = 80
}

variable "task_count" {
  description = "Desired ECS service task count (warm standby). >=1 always."
  type        = number
  default     = 1
}
