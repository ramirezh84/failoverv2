###############################################################################
# Per-region VPC + subnets. No internet egress from Lambdas (CLAUDE.md §2 #4)
# so we have private subnets + an "egress-routable" subnet for the outer NLB.
# We deliberately do NOT create a NAT Gateway; egress for the test harness app
# (synthetic Kafka peer + SSM) goes through VPC endpoints exclusively.
###############################################################################

# ---- Primary region (us-east-1) ----
resource "aws_vpc" "primary" {
  provider             = aws.use1
  cidr_block           = var.vpc_cidr_primary
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(local.common_tags_use1, { Name = "${var.app_name}-vpc", component = "vpc" })
}

resource "aws_subnet" "primary_private" {
  provider          = aws.use1
  count             = length(local.azs_use1)
  vpc_id            = aws_vpc.primary.id
  cidr_block        = local.private_subnet_cidrs_use1[count.index]
  availability_zone = local.azs_use1[count.index]
  tags = merge(local.common_tags_use1, {
    Name      = "${var.app_name}-private-${local.azs_use1[count.index]}"
    component = "subnet-private"
    Tier      = "private"
  })
}

resource "aws_subnet" "primary_routable" {
  provider          = aws.use1
  count             = length(local.azs_use1)
  vpc_id            = aws_vpc.primary.id
  cidr_block        = local.routable_subnet_cidrs_use1[count.index]
  availability_zone = local.azs_use1[count.index]
  tags = merge(local.common_tags_use1, {
    Name      = "${var.app_name}-routable-${local.azs_use1[count.index]}"
    component = "subnet-routable"
    Tier      = "routable"
  })
}

resource "aws_internet_gateway" "primary" {
  provider = aws.use1
  vpc_id   = aws_vpc.primary.id
  tags     = merge(local.common_tags_use1, { Name = "${var.app_name}-igw", component = "igw" })
}

resource "aws_route_table" "primary_routable" {
  provider = aws.use1
  vpc_id   = aws_vpc.primary.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.primary.id
  }
  tags = merge(local.common_tags_use1, { Name = "${var.app_name}-rtb-routable", component = "route-table" })
}

resource "aws_route_table_association" "primary_routable" {
  provider       = aws.use1
  count          = length(local.azs_use1)
  subnet_id      = aws_subnet.primary_routable[count.index].id
  route_table_id = aws_route_table.primary_routable.id
}

resource "aws_route_table" "primary_private" {
  provider = aws.use1
  vpc_id   = aws_vpc.primary.id
  tags     = merge(local.common_tags_use1, { Name = "${var.app_name}-rtb-private", component = "route-table" })
}

resource "aws_route_table_association" "primary_private" {
  provider       = aws.use1
  count          = length(local.azs_use1)
  subnet_id      = aws_subnet.primary_private[count.index].id
  route_table_id = aws_route_table.primary_private.id
}

resource "aws_security_group" "primary_lambda" {
  provider    = aws.use1
  name        = "${var.app_name}-lambda-sg"
  description = "Egress for orchestrator Lambdas to VPC endpoints"
  vpc_id      = aws_vpc.primary.id
  egress {
    description = "HTTPS to interface VPC endpoints (in-VPC IPs)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.primary.cidr_block]
  }
  egress {
    description     = "HTTPS to S3 via gateway endpoint (prefix list)"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    prefix_list_ids = [aws_vpc_endpoint.primary_s3_gateway.prefix_list_id]
  }
  tags = merge(local.common_tags_use1, { component = "sg-lambda" })
}

resource "aws_security_group" "primary_endpoints" {
  provider    = aws.use1
  name        = "${var.app_name}-vpce-sg"
  description = "Allow Lambda SG to talk to VPC interface endpoints"
  vpc_id      = aws_vpc.primary.id
  ingress {
    description     = "HTTPS from Lambda SG"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.primary_lambda.id]
  }
  tags = merge(local.common_tags_use1, { component = "sg-vpce" })
}

# ---- Secondary region (us-east-2) ----
resource "aws_vpc" "secondary" {
  provider             = aws.use2
  cidr_block           = var.vpc_cidr_secondary
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(local.common_tags_use2, { Name = "${var.app_name}-vpc", component = "vpc" })
}

resource "aws_subnet" "secondary_private" {
  provider          = aws.use2
  count             = length(local.azs_use2)
  vpc_id            = aws_vpc.secondary.id
  cidr_block        = local.private_subnet_cidrs_use2[count.index]
  availability_zone = local.azs_use2[count.index]
  tags = merge(local.common_tags_use2, {
    Name      = "${var.app_name}-private-${local.azs_use2[count.index]}"
    component = "subnet-private"
    Tier      = "private"
  })
}

resource "aws_subnet" "secondary_routable" {
  provider          = aws.use2
  count             = length(local.azs_use2)
  vpc_id            = aws_vpc.secondary.id
  cidr_block        = local.routable_subnet_cidrs_use2[count.index]
  availability_zone = local.azs_use2[count.index]
  tags = merge(local.common_tags_use2, {
    Name      = "${var.app_name}-routable-${local.azs_use2[count.index]}"
    component = "subnet-routable"
    Tier      = "routable"
  })
}

resource "aws_internet_gateway" "secondary" {
  provider = aws.use2
  vpc_id   = aws_vpc.secondary.id
  tags     = merge(local.common_tags_use2, { Name = "${var.app_name}-igw", component = "igw" })
}

resource "aws_route_table" "secondary_routable" {
  provider = aws.use2
  vpc_id   = aws_vpc.secondary.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.secondary.id
  }
  tags = merge(local.common_tags_use2, { Name = "${var.app_name}-rtb-routable", component = "route-table" })
}

resource "aws_route_table_association" "secondary_routable" {
  provider       = aws.use2
  count          = length(local.azs_use2)
  subnet_id      = aws_subnet.secondary_routable[count.index].id
  route_table_id = aws_route_table.secondary_routable.id
}

resource "aws_route_table" "secondary_private" {
  provider = aws.use2
  vpc_id   = aws_vpc.secondary.id
  tags     = merge(local.common_tags_use2, { Name = "${var.app_name}-rtb-private", component = "route-table" })
}

resource "aws_route_table_association" "secondary_private" {
  provider       = aws.use2
  count          = length(local.azs_use2)
  subnet_id      = aws_subnet.secondary_private[count.index].id
  route_table_id = aws_route_table.secondary_private.id
}

resource "aws_security_group" "secondary_lambda" {
  provider    = aws.use2
  name        = "${var.app_name}-lambda-sg"
  description = "Egress for orchestrator Lambdas to VPC endpoints"
  vpc_id      = aws_vpc.secondary.id
  egress {
    description = "HTTPS to interface VPC endpoints (in-VPC IPs)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.secondary.cidr_block]
  }
  egress {
    description     = "HTTPS to S3 via gateway endpoint (prefix list)"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    prefix_list_ids = [aws_vpc_endpoint.secondary_s3_gateway.prefix_list_id]
  }
  tags = merge(local.common_tags_use2, { component = "sg-lambda" })
}

resource "aws_security_group" "secondary_endpoints" {
  provider    = aws.use2
  name        = "${var.app_name}-vpce-sg"
  description = "Allow Lambda SG to talk to VPC interface endpoints"
  vpc_id      = aws_vpc.secondary.id
  ingress {
    description     = "HTTPS from Lambda SG"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.secondary_lambda.id]
  }
  tags = merge(local.common_tags_use2, { component = "sg-vpce" })
}
