output "lambda_arns_primary" {
  description = "Map of Lambda name -> ARN (primary)."
  value       = module.orchestrator_runtime.lambda_arns_primary
}

output "lambda_arns_secondary" {
  description = "Map of Lambda name -> ARN (secondary)."
  value       = module.orchestrator_runtime.lambda_arns_secondary
}

output "failover_state_machine_arn_primary" {
  description = "Failover state-machine ARN (primary)."
  value       = module.orchestrator_runtime.failover_state_machine_arn_primary
}

output "failback_state_machine_arn_primary" {
  description = "Failback state-machine ARN (primary)."
  value       = module.orchestrator_runtime.failback_state_machine_arn_primary
}

output "primary_health_check_id" {
  description = "Route 53 health check id (primary)."
  value       = module.orchestrator_runtime.primary_health_check_id
}
