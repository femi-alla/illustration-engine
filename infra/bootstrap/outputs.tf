output "state_bucket" {
  description = "S3 bucket for the live stack's Terraform state (set as the TF_STATE_BUCKET repo variable)."
  value       = aws_s3_bucket.state.bucket
}

output "ecr_repository_url" {
  description = "Registry URL the deploy workflow pushes to."
  value       = aws_ecr_repository.app.repository_url
}

output "github_deploy_role_arn" {
  description = "IAM role GitHub Actions assumes (set as the AWS_ROLE_ARN repo variable)."
  value       = aws_iam_role.github_deploy.arn
}
