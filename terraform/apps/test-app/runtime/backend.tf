terraform {
  backend "s3" {
    bucket         = "failoverv2-tfstate-255025578193"
    key            = "apps/test-app/runtime/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "failoverv2-tfstate-lock"
  }
}
