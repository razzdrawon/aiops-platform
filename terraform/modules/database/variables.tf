variable "name_prefix" {
  description = "Prefix applied to all resource names."
  type        = string
}

variable "vpc_id" {
  description = "VPC the database lives in."
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnets for the DB subnet group."
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to connect on the Postgres port (e.g. the app SG)."
  type        = list(string)
}

variable "db_name" {
  description = "Initial database name."
  type        = string
  default     = "aiops"
}

variable "username" {
  description = "Master username."
  type        = string
  default     = "aiops_user"
}

variable "password" {
  description = "Master password (injected from Secrets Manager / random_password, never hardcoded)."
  type        = string
  sensitive   = true
}

variable "engine_version" {
  description = "PostgreSQL engine version."
  type        = string
  default     = "16.4"
}

variable "instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage" {
  description = "Storage in GiB."
  type        = number
  default     = 20
}

variable "multi_az" {
  description = "Multi-AZ deployment (true for prod HA, false for dev to save cost)."
  type        = bool
  default     = false
}

variable "deletion_protection" {
  description = "Block accidental deletion (enable in prod)."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags merged onto every resource."
  type        = map(string)
  default     = {}
}
