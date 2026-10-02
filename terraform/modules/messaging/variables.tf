variable "name_prefix" {
  description = "Prefix applied to all resource names."
  type        = string
}

variable "vpc_id" {
  description = "VPC for the MSK security group."
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnets for broker placement (one per AZ)."
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to reach the brokers."
  type        = list(string)
  default     = []
}

variable "kafka_version" {
  description = "Apache Kafka version."
  type        = string
  default     = "3.6.0"
}

variable "broker_instance_type" {
  description = "MSK broker instance type."
  type        = string
  default     = "kafka.t3.small"
}

variable "broker_count" {
  description = "Number of broker nodes (must be a multiple of the AZ count)."
  type        = number
  default     = 2
}

variable "broker_volume_size" {
  description = "EBS volume size per broker (GiB)."
  type        = number
  default     = 20
}

variable "tags" {
  description = "Tags merged onto every resource."
  type        = map(string)
  default     = {}
}
