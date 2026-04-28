variable "app_name" {
  description = "DNS-safe app slug; used in resource names and tags."
  type        = string
}

variable "primary_region" {
  description = "Primary AWS region (must be us-east-1 or us-east-2)."
  type        = string
  validation {
    condition     = contains(["us-east-1", "us-east-2"], var.primary_region)
    error_message = "primary_region must be us-east-1 or us-east-2."
  }
}

variable "secondary_region" {
  description = "Secondary AWS region (must differ from primary)."
  type        = string
  validation {
    condition     = contains(["us-east-1", "us-east-2"], var.secondary_region)
    error_message = "secondary_region must be us-east-1 or us-east-2."
  }
}

variable "vpc_cidr_primary" {
  description = "VPC CIDR for the primary region."
  type        = string
  default     = "10.10.0.0/16"
}

variable "vpc_cidr_secondary" {
  description = "VPC CIDR for the secondary region."
  type        = string
  default     = "10.20.0.0/16"
}

variable "tags" {
  description = "Tags applied to every resource (merged with the per-resource component tag)."
  type        = map(string)
  default = {
    managed_by = "terraform"
    repo       = "failoverv2"
    env        = "poc"
  }
}

variable "audit_object_lock_days" {
  description = "S3 audit-bucket Object Lock retention in days (governance mode)."
  type        = number
  default     = 90
}

variable "aurora_engine_version" {
  description = "Aurora PostgreSQL engine version for the global cluster."
  type        = string
  default     = "16.6"
}

variable "aurora_instance_class" {
  description = "Cluster member instance class. db.t4g.medium is the cheapest Graviton tier acceptable for Aurora Global writers."
  type        = string
  default     = "db.r6g.large"
}

variable "aurora_database_name" {
  description = "Initial Aurora database name. Must be a valid PG identifier."
  type        = string
  default     = "failover"
}

variable "aurora_master_username" {
  description = "Aurora master username."
  type        = string
  default     = "failover_admin"
}
