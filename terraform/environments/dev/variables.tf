variable "project" {
  description = "Project slug."
  type        = string
  default     = "aiops-platform"
}

variable "environment" {
  description = "Environment name."
  type        = string
  default     = "dev"
}

variable "region" {
  description = "AWS region."
  type        = string
  default     = "us-east-1"
}

variable "container_image" {
  description = "Image to deploy. Leave empty to use the module's ECR repo at :latest (the CD pipeline pushes git-SHA tags)."
  type        = string
  default     = ""
}

variable "desired_count" {
  description = "Number of ECS tasks."
  type        = number
  default     = 1
}

# --- Optional, expensive components (off by default) ----------------------
variable "enable_messaging" {
  description = "Provision Amazon MSK (managed Kafka). Off by default — expensive."
  type        = bool
  default     = false
}

variable "enable_cache" {
  description = "Provision ElastiCache (Redis). Off by default."
  type        = bool
  default     = false
}

# --- Secret values --------------------------------------------------------
# Provided at apply time (CLI -var, TF_VAR_*, or CI secrets) — NEVER committed.
variable "openai_api_key" {
  description = "OpenAI API key. Empty = app runs in offline heuristic mode."
  type        = string
  default     = ""
  sensitive   = true
}

variable "pinecone_api_key" {
  description = "Pinecone API key. Empty = RAG runs in heuristic mode."
  type        = string
  default     = ""
  sensitive   = true
}
