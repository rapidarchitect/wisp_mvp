variable "aws_profile" {
  description = "AWS CLI profile name from ~/.aws/credentials"
  type        = string
  default     = "default"
}

variable "region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type for the WISPGen host"
  type        = string
  default     = "t3.large"
}

variable "allowed_ssh_cidr" {
  description = "IPv4 CIDR block allowed to SSH to the instance"
  type        = string
  nullable    = false
}

variable "key_name" {
  description = "Name for the new EC2 keypair"
  type        = string
  default     = "wispgen-deploy"
}

variable "base_domain" {
  description = "Base domain for tenant subdomains"
  type        = string
  default     = "app.wisp.llc"
}

variable "data_volume_size" {
  description = "Size in GiB for the encrypted root/data volume"
  type        = number
  default     = 20
}

variable "project_tag" {
  description = "Value for the Project cost tag"
  type        = string
  default     = "wispgen"
}

variable "environment" {
  description = "Environment tag"
  type        = string
  default     = "production"
}
