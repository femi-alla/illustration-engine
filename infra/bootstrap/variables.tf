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

variable "github_owner_id" {
  description = "Numeric id of the repository owner: gh api users/<owner> --jq .id"
  type        = number
  default     = 18646689
}

variable "github_repository_id" {
  description = "Numeric id of the repository: gh api repos/<owner>/<name> --jq .id"
  type        = number
  default     = 1437750696
}
