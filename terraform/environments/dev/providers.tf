provider "aws" {
  region = var.region

  # Tags applied to every taggable resource — invaluable for cost allocation
  # and knowing what Terraform owns.
  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
