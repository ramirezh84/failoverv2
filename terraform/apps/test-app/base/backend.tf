# Terraform 1.5 doesn't support S3 native locking — use a DynamoDB lock
# table. The lock table is the ONLY DynamoDB resource the orchestrator owns
# and is touched by Terraform alone (CLAUDE.md §2 hard constraint #1).
#
# `make harness-up` provisions the bucket + lock table on first run with the
# bootstrap script under scripts/terraform_bootstrap.sh.
terraform {
  backend "s3" {
    bucket         = "failoverv2-tfstate-255025578193"
    key            = "apps/test-app/base/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "failoverv2-tfstate-lock"
  }
}
