locals {
  name_prefix = "${var.project}-${var.environment}"

  common_tags = {
    Project     = var.project
    Environment = var.environment
  }
}

# --- Networking -----------------------------------------------------------
module "network" {
  source = "../../modules/network"

  name_prefix        = local.name_prefix
  single_nat_gateway = true # dev: one NAT to save cost
  tags               = local.common_tags
}

# --- Compute (ECS + ALB + ECR) -------------------------------------------
# Created before the DB consumes its security group. The DB connection URL is
# delivered as a Secrets Manager secret (see secrets.tf), so compute does not
# depend on the database module directly — avoiding a dependency cycle.
module "compute" {
  source = "../../modules/compute"

  name_prefix        = local.name_prefix
  region             = var.region
  vpc_id             = module.network.vpc_id
  public_subnet_ids  = module.network.public_subnet_ids
  private_subnet_ids = module.network.private_subnet_ids

  container_image = var.container_image
  container_port  = 8000
  desired_count   = var.desired_count

  environment_variables = {
    OPENAI_MODEL           = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
    PINECONE_INDEX_NAME    = "aiops-runbooks"
  }

  secret_arns = {
    DATABASE_URL     = aws_secretsmanager_secret.db_url.arn
    OPENAI_API_KEY   = aws_secretsmanager_secret.openai.arn
    PINECONE_API_KEY = aws_secretsmanager_secret.pinecone.arn
  }

  tags = local.common_tags
}

# --- Database (RDS) -------------------------------------------------------
module "database" {
  source = "../../modules/database"

  name_prefix        = local.name_prefix
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids

  # Only the app tier may reach Postgres.
  allowed_security_group_ids = [module.compute.app_security_group_id]

  password            = random_password.db.result
  multi_az            = false # dev
  deletion_protection = false # dev

  tags = local.common_tags
}

# --- Optional: Messaging (MSK) — off by default --------------------------
module "messaging" {
  source = "../../modules/messaging"
  count  = var.enable_messaging ? 1 : 0

  name_prefix                = local.name_prefix
  vpc_id                     = module.network.vpc_id
  private_subnet_ids         = module.network.private_subnet_ids
  allowed_security_group_ids = [module.compute.app_security_group_id]

  tags = local.common_tags
}

# --- Optional: Cache (ElastiCache) — off by default ----------------------
module "cache" {
  source = "../../modules/cache"
  count  = var.enable_cache ? 1 : 0

  name_prefix                = local.name_prefix
  vpc_id                     = module.network.vpc_id
  private_subnet_ids         = module.network.private_subnet_ids
  allowed_security_group_ids = [module.compute.app_security_group_id]

  tags = local.common_tags
}
