# Bootstrap: creates the remote-state backend (S3 bucket + DynamoDB lock table)
# that every environment then uses. Run ONCE, with LOCAL state, before any env.
#
#   cd terraform/bootstrap
#   terraform init && terraform apply
#
# Chicken-and-egg note: this config keeps its own state locally (committed-ignored)
# because the backend it manages does not exist yet.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
      Component = "tf-backend"
    }
  }
}

# State bucket: versioned + encrypted + fully private.
resource "aws_s3_bucket" "state" {
  bucket = "${var.project}-tfstate-${var.region}"

  # Protect against accidental destroy of the bucket holding all state.
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lock table: prevents concurrent applies from corrupting state.
# (Terraform 1.10+ also supports S3-native locking via use_lockfile; DynamoDB is
#  kept here for broad compatibility and explicitness.)
resource "aws_dynamodb_table" "locks" {
  name         = "${var.project}-tflocks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}
