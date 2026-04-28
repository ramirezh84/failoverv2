variable "app_name" {
  description = "App slug."
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

variable "aws_profile" {
  description = "AWS CLI profile."
  type        = string
  default     = null
}

variable "base_state_bucket" {
  description = "S3 bucket holding the base layer's tfstate (must already exist)."
  type        = string
}

variable "profile_yaml_path" {
  description = <<-EOT
    Optional path to a profile YAML to bake into Lambda env vars (PROFILE_YAML).
    When set, Lambdas load the profile from env (no runtime S3 dependency).
    When empty (default), Lambdas load from S3 via PROFILE_BUCKET/PROFILE_KEY.
    See docs/profile-delivery-modes.md for tradeoffs.
  EOT
  type        = string
  default     = ""
}
