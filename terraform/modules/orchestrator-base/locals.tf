locals {
  common_tags = merge(var.tags, {
    app  = var.app_name
    repo = "failoverv2"
  })
  common_tags_use1 = merge(local.common_tags, { region = var.primary_region })
  common_tags_use2 = merge(local.common_tags, { region = var.secondary_region })

  # Subnet partitioning. /16 split into three /24s per AZ across 3 AZs.
  azs_use1 = ["${var.primary_region}a", "${var.primary_region}b", "${var.primary_region}c"]
  azs_use2 = ["${var.secondary_region}a", "${var.secondary_region}b", "${var.secondary_region}c"]

  private_subnet_cidrs_use1 = [
    cidrsubnet(var.vpc_cidr_primary, 8, 0),
    cidrsubnet(var.vpc_cidr_primary, 8, 1),
    cidrsubnet(var.vpc_cidr_primary, 8, 2),
  ]
  routable_subnet_cidrs_use1 = [
    cidrsubnet(var.vpc_cidr_primary, 8, 10),
    cidrsubnet(var.vpc_cidr_primary, 8, 11),
    cidrsubnet(var.vpc_cidr_primary, 8, 12),
  ]
  private_subnet_cidrs_use2 = [
    cidrsubnet(var.vpc_cidr_secondary, 8, 0),
    cidrsubnet(var.vpc_cidr_secondary, 8, 1),
    cidrsubnet(var.vpc_cidr_secondary, 8, 2),
  ]
  routable_subnet_cidrs_use2 = [
    cidrsubnet(var.vpc_cidr_secondary, 8, 10),
    cidrsubnet(var.vpc_cidr_secondary, 8, 11),
    cidrsubnet(var.vpc_cidr_secondary, 8, 12),
  ]

  # Set of AWS services for which we create interface VPC endpoints in both
  # regions. CLAUDE.md §2 #4: every Lambda boto3 call goes through one of these.
  vpc_endpoint_services = [
    "ssm",
    "sns",
    "monitoring", # CloudWatch metrics
    "logs",       # CloudWatch Logs
    "rds",
    "states", # Step Functions
    "synthetics",
    "events", # EventBridge
    "lambda",
    "sts",
    "secretsmanager",
    "health", # AWS Health — signal_collector.aws_health_open_events()
    # calls describe_events every minute. Without this VPCE the Lambda hangs
    # at 30s timeout on every invocation in a no-internet-egress VPC.
  ]
}

data "aws_caller_identity" "current" {}
