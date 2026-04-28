###############################################################################
# CloudWatch alarms.
# The PrimaryHealthControl alarm (per region, watching the metric the
# Decision Engine + executor_flip_r53_metric Lambda emit) drives the R53
# health-check via r53.tf.
###############################################################################

resource "aws_cloudwatch_metric_alarm" "primary_health_control_use1" {
  provider            = aws.use1
  alarm_name          = "${var.app_name}-PrimaryHealthControl-use1"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "PrimaryHealthControl"
  namespace           = "Failover/${var.app_name}"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0.5
  alarm_description   = "Failover control for ${var.app_name} primary region; bound to R53 health check. Tripped when Decision Engine or executor emits 0."
  treat_missing_data  = "breaching"

  dimensions = {
    Region = var.primary_region
  }
  tags = merge(local.common_tags_use1, { component = "alarm-r53-control" })
}

resource "aws_cloudwatch_metric_alarm" "primary_health_control_use2" {
  provider            = aws.use2
  alarm_name          = "${var.app_name}-PrimaryHealthControl-use2"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "PrimaryHealthControl"
  namespace           = "Failover/${var.app_name}"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0.5
  alarm_description   = "Failover control for ${var.app_name} (secondary mirror)."
  treat_missing_data  = "breaching"

  dimensions = {
    Region = var.secondary_region
  }
  tags = merge(local.common_tags_use2, { component = "alarm-r53-control" })
}
