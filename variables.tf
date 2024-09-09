###########
# Variables

variable "gcp_enabled_services" {
  description = "List of services to enable on the ML platform"
  type        = list(string)
  default = [
    "aiplatform.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "container.googleapis.com",
    "containeranalysis.googleapis.com",
    "containerregistry.googleapis.com",
    "datacatalog.googleapis.com",
    "dataflow.googleapis.com",
    "dataform.googleapis.com",
    "iam.googleapis.com",
    "ml.googleapis.com",
    "notebooks.googleapis.com",
    "vision.googleapis.com",
  ]
}

variable "gcp_created_folders" {
  description = "List of folders to create in the main bucket on the ML platform"
  type        = list(string)
  default = [
    "raw/"
  ]
}

variable "infra_sa_roles" {
  description = "List of roles to bind to this service account"
  type        = list(string)
  default = [
    "roles/owner",
    "roles/serviceusage.serviceUsageAdmin"
  ]
}

variable "gcp_service_accounts" {
  description = "A map of service account configurations, including roles, account ID, and description."
  type = map(object({
    roles = list(string)
    sa_id = string
    name  = string
  }))
  default = {
    gcp_ml_sa = {
      roles = [
        "roles/cloudbuild.builds.editor",
        "roles/cloudbuild.integrations.editor",
        "roles/secretmanager.secretAccessor",
        "roles/storage.objectUser",
        "roles/aiplatform.user",
        "roles/ml.developer",
        "roles/artifactregistry.createOnPushWriter"
      ]
      sa_id = "neurips-ml-sa"
      name  = "Core ML tasks SA"
    }
  }
}


variable "gha_assertion_aud" {
  description = "GHA workload identity JWk token aud attribute"
  type        = string
  default     = "https://github.com/CedrickArmel"
}

variable "gha_assertion_sub" {
  description = "GHA workload identity JWk token sub attribute"
  type        = string
  default     = "CedrickArmel/neurips_adc:ref:refs/heads/main"
}

variable "gha_assertion_actor" {
  description = "GHA workload identity JWk token actor attribute"
  type        = string
  default     = "CedrickArmel"
}


#########
# Secrets
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

variable "tfe_token" {
  description = "Token to authenticate TFE provider"
  type        = string
  sensitive   = true
}
