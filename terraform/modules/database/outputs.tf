output "address" {
  description = "RDS endpoint hostname."
  value       = aws_db_instance.this.address
}

output "port" {
  description = "RDS port."
  value       = aws_db_instance.this.port
}

output "db_name" {
  description = "Initial database name."
  value       = aws_db_instance.this.db_name
}

output "security_group_id" {
  description = "Security group attached to the database."
  value       = aws_security_group.db.id
}

# Convenience: full async SQLAlchemy URL the app expects. Sensitive (embeds password).
output "connection_url" {
  description = "postgresql+asyncpg connection string for the application."
  value       = "postgresql+asyncpg://${var.username}:${var.password}@${aws_db_instance.this.address}:${aws_db_instance.this.port}/${aws_db_instance.this.db_name}"
  sensitive   = true
}
