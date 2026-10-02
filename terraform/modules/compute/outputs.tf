output "alb_dns_name" {
  description = "Public DNS name of the load balancer."
  value       = aws_lb.this.dns_name
}

output "app_url" {
  description = "Base URL to reach the API."
  value       = "${var.certificate_arn != "" ? "https" : "http"}://${aws_lb.this.dns_name}"
}

output "ecr_repository_url" {
  description = "ECR repository URL to push images to."
  value       = aws_ecr_repository.app.repository_url
}

output "app_security_group_id" {
  description = "Security group of the ECS tasks (grant DB ingress from this)."
  value       = aws_security_group.app.id
}

output "cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.this.name
}

output "service_name" {
  description = "ECS service name."
  value       = aws_ecs_service.app.name
}

output "task_definition_family" {
  description = "Task definition family (used by the CD pipeline)."
  value       = aws_ecs_task_definition.app.family
}
