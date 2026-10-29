terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Bucket and region are supplied with -backend-config at init time so that the
  # account id never has to be committed. Terraform 1.10+ locks natively in S3.
  backend "s3" {
    key          = "live/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
      Stack     = "live"
    }
  }
}
