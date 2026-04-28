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
  description = "AWS CLI profile to use. Operator usually exports AWS_PROFILE=tbed and leaves this null."
  type        = string
  default     = null
}
