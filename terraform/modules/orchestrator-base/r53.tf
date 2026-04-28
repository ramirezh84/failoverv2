###############################################################################
# Route 53 private hosted zone. The R53 health check + alarm-bound failover
# record live in orchestrator-runtime; the zone itself is base infra.
###############################################################################

resource "aws_route53_zone" "private" {
  provider = aws.use1
  name     = "${var.app_name}.failover.internal"
  comment  = "Private DNS for ${var.app_name} failover orchestrator"
  vpc {
    vpc_id     = aws_vpc.primary.id
    vpc_region = var.primary_region
  }
  vpc {
    vpc_id     = aws_vpc.secondary.id
    vpc_region = var.secondary_region
  }
  tags = merge(local.common_tags_use1, { component = "r53-zone" })
}
