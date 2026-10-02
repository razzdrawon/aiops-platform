# Amazon MSK (managed Kafka). Written for completeness; gated behind a feature
# flag at the environment level because MSK is expensive (~$130+/mo) and not
# required for the API to run. Enable when the streaming ingestion path is live.

resource "aws_security_group" "msk" {
  name        = "${var.name_prefix}-msk-sg"
  description = "Kafka access from the application tier"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name_prefix}-msk-sg" })

  lifecycle { create_before_destroy = true }
}

resource "aws_security_group_rule" "msk_ingress" {
  count                    = length(var.allowed_security_group_ids)
  type                     = "ingress"
  from_port                = 9092
  to_port                  = 9098
  protocol                 = "tcp"
  security_group_id        = aws_security_group.msk.id
  source_security_group_id = var.allowed_security_group_ids[count.index]
  description              = "Kafka (plaintext + TLS + IAM) from application tier"
}

resource "aws_cloudwatch_log_group" "msk" {
  name              = "/msk/${var.name_prefix}"
  retention_in_days = 14
  tags              = var.tags
}

resource "aws_msk_cluster" "this" {
  cluster_name           = "${var.name_prefix}-kafka"
  kafka_version          = var.kafka_version
  number_of_broker_nodes = var.broker_count

  broker_node_group_info {
    instance_type   = var.broker_instance_type
    client_subnets  = var.private_subnet_ids
    security_groups = [aws_security_group.msk.id]

    storage_info {
      ebs_storage_info {
        volume_size = var.broker_volume_size
      }
    }
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk.name
      }
    }
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-kafka" })
}
