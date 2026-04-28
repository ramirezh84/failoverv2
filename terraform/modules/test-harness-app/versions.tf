terraform {
  required_version = ">= 1.5.0, < 2.0.0"
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      version               = "~> 5.80"
      configuration_aliases = [aws.use1, aws.use2]
    }
  }
}
