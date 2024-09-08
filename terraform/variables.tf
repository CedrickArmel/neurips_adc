#########
# Secrets

# Terraform
variable "gcp_iam_infra_sa_account_id" {
  description = "Core IAM & Infra LC management SA"
  type        = string
  sensitive   = true
}

variable "gcp_project" {
  description = "Google Cloud project to deploy on"
  type        = string
  sensitive   = true
}

variable "gcp_region" {
  description = "Google Cloud region to deploy on"
  type        = string
  sensitive   = true
}

variable "hcp_terraform_org_name" {
  description = "Organization name in HCP Terraform Cloud"
  type        = string
  sensitive   = true
}

variable "hcp_terraform_ws_id" {
  description = "Project's worksapce in HCP Terraform Cloud"
  type        = string
  sensitive   = true
}

variable "hcp_terraform_ws_name" {
  description = "Project's worksapce in HCP Terraform Cloud"
  type        = string
  sensitive   = true
}

# Main
