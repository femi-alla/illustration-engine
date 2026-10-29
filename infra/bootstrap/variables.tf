variable "project" {
  description = "Name used for every resource in this project."
  type        = string
  default     = "illustration-engine"
}

variable "region" {
  description = "AWS region for the state bucket and registry."
  type        = string
  default     = "us-east-2"
}

variable "github_repository" {
  description = "GitHub repository (owner/name) allowed to assume the deploy role."
  type        = string
  default     = "femi-alla/illustration-engine"
}
