terraform {
  required_version = ">= 1.5.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  alias   = "use1"
  region  = "us-east-1"
  profile = var.aws_profile
}

provider "aws" {
  alias   = "use2"
  region  = "us-east-2"
  profile = var.aws_profile
}
