# RDS PostgreSQL in private subnets. Reachable only from the app security group;
# never publicly accessible. Storage encrypted at rest.

resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db-subnets"
  subnet_ids = var.private_subnet_ids
  tags       = merge(var.tags, { Name = "${var.name_prefix}-db-subnets" })
}

resource "aws_security_group" "db" {
  name        = "${var.name_prefix}-db-sg"
  description = "Postgres access from the application tier only"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, { Name = "${var.name_prefix}-db-sg" })

  lifecycle {
    create_before_destroy = true
  }
}

# Ingress 5432 from each allowed SG (rules kept separate from the SG for clean diffs).
resource "aws_security_group_rule" "db_ingress" {
  count                    = length(var.allowed_security_group_ids)
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.db.id
  source_security_group_id = var.allowed_security_group_ids[count.index]
  description              = "Postgres from application tier"
}

resource "aws_db_instance" "this" {
  identifier     = "${var.name_prefix}-postgres"
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  db_name  = var.db_name
  username = var.username
  password = var.password
  port     = 5432

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.allocated_storage * 2 # allow autoscaling headroom
  storage_type          = "gp3"
  storage_encrypted     = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false
  multi_az               = var.multi_az

  backup_retention_period   = var.multi_az ? 7 : 1
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = !var.deletion_protection
  final_snapshot_identifier = var.deletion_protection ? "${var.name_prefix}-postgres-final" : null

  # Minor versions can be patched in the maintenance window without a TF diff.
  auto_minor_version_upgrade = true
  apply_immediately          = !var.deletion_protection

  tags = merge(var.tags, { Name = "${var.name_prefix}-postgres" })
}
