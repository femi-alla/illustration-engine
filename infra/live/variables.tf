variable "project" {
  description = "Name used for every resource in this project."
  type        = string
  default     = "illustration-engine"
}

variable "region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-2"
}

variable "image_tag" {
  description = "Tag of the image in the project ECR repository to run (normally the git SHA)."
  type        = string
}

variable "container_port" {
  description = "Port the application listens on inside the container."
  type        = number
  default     = 8080
}

variable "task_cpu" {
  description = "Fargate task CPU units (256 = 0.25 vCPU)."
  type        = number
  default     = 256
}

variable "task_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 512
}

variable "desired_count" {
  description = "Baseline number of tasks; autoscaling moves between min_count and max_count."
  type        = number
  default     = 1
}

variable "min_count" {
  type    = number
  default = 1
}

variable "max_count" {
  type    = number
  default = 3
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "alarm_email" {
  description = "Optional email address subscribed to the alarm topic. Empty disables the subscription."
  type        = string
  default     = ""
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}
