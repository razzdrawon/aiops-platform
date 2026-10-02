# Remote state for the dev environment.
# The bucket + lock table are created by terraform/bootstrap (run once).
# Each environment uses a distinct key, so their states never collide.
#
# Initialize with:
#   terraform init
terraform {
  backend "s3" {
    bucket         = "aiops-platform-tfstate-us-east-1"
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "aiops-platform-tflocks"
    encrypt        = true
  }
}
