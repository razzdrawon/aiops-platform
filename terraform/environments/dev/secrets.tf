# Secrets live in AWS Secrets Manager; the ECS execution role reads them at
# task start and injects them as container env vars. Values never touch the
# image or the task definition in plaintext.

# DB master password — generated, never seen by a human.
resource "random_password" "db" {
  length  = 24
  special = false # avoid URL-encoding headaches in the connection string
}

resource "aws_secretsmanager_secret" "db_url" {
  name        = "${local.name_prefix}/database-url"
  description = "Async SQLAlchemy connection URL for the AIOps API"
}

resource "aws_secretsmanager_secret_version" "db_url" {
  secret_id     = aws_secretsmanager_secret.db_url.id
  secret_string = module.database.connection_url
}

resource "aws_secretsmanager_secret" "openai" {
  name        = "${local.name_prefix}/openai-api-key"
  description = "OpenAI API key (empty => offline heuristic mode)"
}

resource "aws_secretsmanager_secret_version" "openai" {
  secret_id     = aws_secretsmanager_secret.openai.id
  secret_string = var.openai_api_key
}

resource "aws_secretsmanager_secret" "pinecone" {
  name        = "${local.name_prefix}/pinecone-api-key"
  description = "Pinecone API key (empty => heuristic RAG)"
}

resource "aws_secretsmanager_secret_version" "pinecone" {
  secret_id     = aws_secretsmanager_secret.pinecone.id
  secret_string = var.pinecone_api_key
}
