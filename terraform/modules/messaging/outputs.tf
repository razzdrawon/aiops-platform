output "bootstrap_brokers_tls" {
  description = "TLS bootstrap broker connection string."
  value       = aws_msk_cluster.this.bootstrap_brokers_tls
}

output "zookeeper_connect_string" {
  description = "ZooKeeper connection string."
  value       = aws_msk_cluster.this.zookeeper_connect_string
}

output "security_group_id" {
  description = "Security group attached to the MSK cluster."
  value       = aws_security_group.msk.id
}
