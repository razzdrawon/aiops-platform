# ElastiCache (Redis) for RAG result caching + rate limiting (Phase 5).
# Gated behind a feature flag at the environment level; not required for the
# core API. Single-node by default to keep cost minimal.

resource "aws_security_group" "cache" {
  name        = "${var.name_prefix}-cache-sg"
  description = "Redis access from the application tier"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name_prefix}-cache-sg" })

  lifecycle { create_before_destroy = true }
}

resource "aws_security_group_rule" "cache_ingress" {
  count                    = length(var.allowed_security_group_ids)
  type                     = "ingress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  security_group_id        = aws_security_group.cache.id
  source_security_group_id = var.allowed_security_group_ids[count.index]
  description              = "Redis from application tier"
}

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name_prefix}-cache-subnets"
  subnet_ids = var.private_subnet_ids
  tags       = var.tags
}

resource "aws_elasticache_cluster" "this" {
  cluster_id           = "${var.name_prefix}-redis"
  engine               = "redis"
  engine_version       = var.engine_version
  node_type            = var.node_type
  num_cache_nodes      = 1
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.this.name
  security_group_ids   = [aws_security_group.cache.id]
  parameter_group_name = "default.redis7"

  tags = merge(var.tags, { Name = "${var.name_prefix}-redis" })
}
