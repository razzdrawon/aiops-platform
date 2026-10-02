variable "project" {
  description = "Project slug used to name the state bucket and lock table."
  type        = string
  default     = "aiops-platform"
}

variable "region" {
  description = "AWS region for the state backend."
  type        = string
  default     = "us-east-1"
}
