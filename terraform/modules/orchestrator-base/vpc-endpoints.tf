###############################################################################
# Interface VPC endpoints — every AWS service the Lambdas call has one in both
# regions. Plus an S3 Gateway endpoint (cheaper than interface for S3).
# CLAUDE.md §2 #4 + SPEC §3.1 + the vpc-endpoint-check CI job.
#
# Note on AZ availability: some VPCE services (notably AWS Health) are only
# available in a subset of AZs per region. We discover supported AZs per
# service via a data source and intersect with our subnet AZs, so a single
# missing-AZ service doesn't block the others.
###############################################################################

data "aws_vpc_endpoint_service" "primary" {
  for_each     = toset(local.vpc_endpoint_services)
  provider     = aws.use1
  service_name = "com.amazonaws.${var.primary_region}.${each.key}"
}

data "aws_vpc_endpoint_service" "secondary" {
  for_each     = toset(local.vpc_endpoint_services)
  provider     = aws.use2
  service_name = "com.amazonaws.${var.secondary_region}.${each.key}"
}

resource "aws_vpc_endpoint" "primary_interface" {
  for_each          = toset(local.vpc_endpoint_services)
  provider          = aws.use1
  vpc_id            = aws_vpc.primary.id
  service_name      = "com.amazonaws.${var.primary_region}.${each.key}"
  vpc_endpoint_type = "Interface"
  subnet_ids = [
    for s in aws_subnet.primary_private :
    s.id if contains(data.aws_vpc_endpoint_service.primary[each.key].availability_zones, s.availability_zone)
  ]
  security_group_ids  = [aws_security_group.primary_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.common_tags_use1, { Name = "${var.app_name}-vpce-${each.key}", component = "vpce" })
}

resource "aws_vpc_endpoint" "primary_s3_gateway" {
  provider          = aws.use1
  vpc_id            = aws_vpc.primary.id
  service_name      = "com.amazonaws.${var.primary_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.primary_private.id]
  tags              = merge(local.common_tags_use1, { Name = "${var.app_name}-vpce-s3", component = "vpce-gateway" })
}

resource "aws_vpc_endpoint" "secondary_interface" {
  for_each          = toset(local.vpc_endpoint_services)
  provider          = aws.use2
  vpc_id            = aws_vpc.secondary.id
  service_name      = "com.amazonaws.${var.secondary_region}.${each.key}"
  vpc_endpoint_type = "Interface"
  subnet_ids = [
    for s in aws_subnet.secondary_private :
    s.id if contains(data.aws_vpc_endpoint_service.secondary[each.key].availability_zones, s.availability_zone)
  ]
  security_group_ids  = [aws_security_group.secondary_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.common_tags_use2, { Name = "${var.app_name}-vpce-${each.key}", component = "vpce" })
}

resource "aws_vpc_endpoint" "secondary_s3_gateway" {
  provider          = aws.use2
  vpc_id            = aws_vpc.secondary.id
  service_name      = "com.amazonaws.${var.secondary_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.secondary_private.id]
  tags              = merge(local.common_tags_use2, { Name = "${var.app_name}-vpce-s3", component = "vpce-gateway" })
}

# Health control plane only exists in us-east-1; we point both regions'
# Lambdas at the same endpoint for AWS Health by re-using the primary VPCE
# only when primary_region == us-east-1. For the POC where both regions are
# in us-east-{1,2}, we surface health via the primary's endpoint URL only.
