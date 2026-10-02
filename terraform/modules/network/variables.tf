variable "name_prefix" {
  description = "Prefix applied to all resource names, e.g. \"aiops-dev\"."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "az_count" {
  description = "How many Availability Zones to span (2 is the practical minimum for HA)."
  type        = number
  default     = 2

  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "az_count must be 2 or 3."
  }
}

variable "single_nat_gateway" {
  description = "Use one shared NAT Gateway instead of one per AZ. true = cheaper (dev), false = HA (prod)."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags merged onto every resource."
  type        = map(string)
  default     = {}
}
