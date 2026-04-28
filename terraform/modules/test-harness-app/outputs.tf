output "outer_nlb_arn_primary" {
  description = "Outer NLB ARN (primary)."
  value       = aws_lb.outer_primary.arn
}

output "outer_nlb_arn_secondary" {
  description = "Outer NLB ARN (secondary)."
  value       = aws_lb.outer_secondary.arn
}

output "outer_nlb_dns_primary" {
  description = "Outer NLB DNS name (primary)."
  value       = aws_lb.outer_primary.dns_name
}

output "outer_nlb_dns_secondary" {
  description = "Outer NLB DNS name (secondary)."
  value       = aws_lb.outer_secondary.dns_name
}

output "alb_arn_primary" {
  description = "Inner ALB ARN (primary)."
  value       = aws_lb.alb_primary.arn
}

output "alb_arn_secondary" {
  description = "Inner ALB ARN (secondary)."
  value       = aws_lb.alb_secondary.arn
}

output "ecs_service_name_primary" {
  description = "ECS service name (primary)."
  value       = aws_ecs_service.primary.name
}

output "ecs_service_name_secondary" {
  description = "ECS service name (secondary)."
  value       = aws_ecs_service.secondary.name
}
