variable "name_prefix" {
  description = "Prefix applied to all resource names."
  type        = string
}

variable "region" {
  description = "AWS region (used for log configuration)."
  type        = string
}

variable "vpc_id" {
  description = "VPC to deploy into."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnets for the ALB."
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Private subnets for the ECS tasks."
  type        = list(string)
}

variable "container_image" {
  description = "Full image reference to run (e.g. <ecr-url>:<git-sha>). Defaults to the module's own ECR repo at :latest if empty."
  type        = string
  default     = ""
}

variable "container_port" {
  description = "Port the app listens on inside the container."
  type        = number
  default     = 8000
}

variable "desired_count" {
  description = "Number of ECS tasks to run."
  type        = number
  default     = 1
}

variable "cpu" {
  description = "Fargate task CPU units (256 = 0.25 vCPU)."
  type        = number
  default     = 512
}

variable "memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 1024
}

variable "health_check_path" {
  description = "HTTP path the ALB target group probes."
  type        = string
  default     = "/health"
}

variable "environment_variables" {
  description = "Plain (non-secret) environment variables for the container."
  type        = map(string)
  default     = {}
}

variable "secret_arns" {
  description = "Map of ENV_VAR_NAME => Secrets Manager secret ARN to inject as container secrets."
  type        = map(string)
  default     = {}
}

variable "certificate_arn" {
  description = "ACM certificate ARN. If set, the ALB serves HTTPS on 443 and redirects 80→443; if empty, HTTP only on 80."
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "CloudWatch log retention."
  type        = number
  default     = 14
}

variable "tags" {
  description = "Tags merged onto every resource."
  type        = map(string)
  default     = {}
}
