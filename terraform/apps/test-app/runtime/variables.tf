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
