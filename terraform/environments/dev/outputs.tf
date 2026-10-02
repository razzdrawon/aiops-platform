output "app_url" {
  description = "Public URL of the API behind the ALB."
  value       = module.compute.app_url
}

output "alb_dns_name" {
  description = "ALB DNS name."
  value       = module.compute.alb_dns_name
}

output "ecr_repository_url" {
  description = "Push images here; the CD pipeline tags by git SHA."
  value       = module.compute.ecr_repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name (for CD / one-off migration tasks)."
  value       = module.compute.cluster_name
}

output "ecs_service_name" {
  description = "ECS service name (CD forces a new deployment here)."
  value       = module.compute.service_name
}

output "rds_address" {
  description = "RDS endpoint hostname."
  value       = module.database.address
}

output "messaging_brokers" {
  description = "MSK TLS bootstrap brokers (only when enable_messaging = true)."
  value       = var.enable_messaging ? module.messaging[0].bootstrap_brokers_tls : null
}

output "cache_endpoint" {
  description = "Redis endpoint (only when enable_cache = true)."
  value       = var.enable_cache ? module.cache[0].endpoint : null
}
