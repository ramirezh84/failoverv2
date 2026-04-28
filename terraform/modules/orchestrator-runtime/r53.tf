###############################################################################
# Route 53 failover record + health check bound to the alarm in cloudwatch.tf.
# CLAUDE.md §2 #3: orchestrator never calls route53 directly; the alarm-bound
# health check IS the orchestrator's R53 control surface.
###############################################################################

resource "aws_route53_health_check" "primary" {
  provider                        = aws.use1
  reference_name                  = "${var.app_name}-primary-hc"
  type                            = "CLOUDWATCH_METRIC"
  cloudwatch_alarm_name           = aws_cloudwatch_metric_alarm.primary_health_control_use1.alarm_name
  cloudwatch_alarm_region         = var.primary_region
  insufficient_data_health_status = "Unhealthy"
  tags                            = merge(local.common_tags_use1, { component = "r53-health-check", Name = "${var.app_name}-primary-hc" })
}

resource "aws_route53_health_check" "secondary" {
  provider                        = aws.use1 # R53 is global; we declare both via use1
  reference_name                  = "${var.app_name}-secondary-hc"
  type                            = "CLOUDWATCH_METRIC"
  cloudwatch_alarm_name           = aws_cloudwatch_metric_alarm.primary_health_control_use2.alarm_name
  cloudwatch_alarm_region         = var.secondary_region
  insufficient_data_health_status = "Healthy" # secondary is healthy by default
  tags                            = merge(local.common_tags_use1, { component = "r53-health-check", Name = "${var.app_name}-secondary-hc" })
}

# The user-facing failover record. Two entries pointing at the per-region
# routable URL; R53 routes to whichever is healthy. We populate the placeholder
# value with the routable hostname; test-harness-app outputs the real ALIAS.
resource "aws_route53_record" "global_primary" {
  provider       = aws.use1
  zone_id        = var.route53_zone_id
  name           = var.route53_zone_name
  type           = "CNAME"
  ttl            = 30
  set_identifier = "primary"
  failover_routing_policy { type = "PRIMARY" }
  health_check_id = aws_route53_health_check.primary.id
  records         = ["${var.app_name}.${var.primary_region}.${var.route53_zone_name}"]
}

resource "aws_route53_record" "global_secondary" {
  provider       = aws.use1
  zone_id        = var.route53_zone_id
  name           = var.route53_zone_name
  type           = "CNAME"
  ttl            = 30
  set_identifier = "secondary"
  failover_routing_policy { type = "SECONDARY" }
  health_check_id = aws_route53_health_check.secondary.id
  records         = ["${var.app_name}.${var.secondary_region}.${var.route53_zone_name}"]
}
