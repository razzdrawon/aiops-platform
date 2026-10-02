variable "name_prefix" {
  description = "Prefix applied to all resource names."
  type        = string
}

variable "vpc_id" {
  description = "VPC for the cache security group."
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnets for the cache subnet group."
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to reach Redis."
  type        = list(string)
  default     = []
}

variable "node_type" {
  description = "ElastiCache node type."
  type        = string
  default     = "cache.t4g.micro"
}

variable "engine_version" {
  description = "Redis engine version."
  type        = string
  default     = "7.1"
}

variable "tags" {
  description = "Tags merged onto every resource."
  type        = map(string)
  default     = {}
}
