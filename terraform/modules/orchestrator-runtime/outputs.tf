output "lambda_arns_primary" {
  description = "Map of Lambda name -> ARN (primary)."
  value       = { for k, v in aws_lambda_function.primary : k => v.arn }
}

output "lambda_arns_secondary" {
  description = "Map of Lambda name -> ARN (secondary)."
  value       = { for k, v in aws_lambda_function.secondary : k => v.arn }
}

output "failover_state_machine_arn_primary" {
  description = "Failover state-machine ARN (primary)."
  value       = aws_sfn_state_machine.failover_primary.arn
}

output "failback_state_machine_arn_primary" {
  description = "Failback state-machine ARN (primary)."
  value       = aws_sfn_state_machine.failback_primary.arn
}

output "failover_state_machine_arn_secondary" {
  description = "Failover state-machine ARN (secondary)."
  value       = aws_sfn_state_machine.failover_secondary.arn
}

output "failback_state_machine_arn_secondary" {
  description = "Failback state-machine ARN (secondary)."
  value       = aws_sfn_state_machine.failback_secondary.arn
}

output "primary_health_check_id" {
  description = "Route 53 health check id bound to the primary alarm."
  value       = aws_route53_health_check.primary.id
}

output "secondary_health_check_id" {
  description = "Route 53 health check id bound to the secondary alarm."
  value       = aws_route53_health_check.secondary.id
}

output "primary_alarm_name" {
  description = "PrimaryHealthControl alarm name (primary region)."
  value       = aws_cloudwatch_metric_alarm.primary_health_control_use1.alarm_name
}

output "secondary_alarm_name" {
  description = "PrimaryHealthControl alarm name (secondary region)."
  value       = aws_cloudwatch_metric_alarm.primary_health_control_use2.alarm_name
}
