output "state_bucket" {
  description = "S3 bucket name to put in each environment's backend config."
  value       = aws_s3_bucket.state.id
}

output "lock_table" {
  description = "DynamoDB table name to put in each environment's backend config."
  value       = aws_dynamodb_table.locks.name
}
