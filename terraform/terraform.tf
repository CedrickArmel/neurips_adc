#####################
# Import requirements

terraform {
  cloud {
    organization = "mienmo"

    workspaces {
      name = "credentials"
    }
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "6.1.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "6.1.0"
    }
  }
}

################
# Init providers
provider "google" {
  project = var.gcp_project
  region  = var.gcp_region
}

provider "google-beta" {
  project = var.gcp_project
  region  = var.gcp_region
}

data "google_project" "gcp_project" {}

###################
# Resources imports


##########################
# Create Services Accounts (SA)
resource "google_service_account" "gcp_iam_infra_sa" {
  account_id                   = var.gcp_iam_infra_sa_account_id
  display_name                 = "Core IAM & Infra LC management SA from outside GCP (Terraform, GHA, etc.)"
  create_ignore_already_exists = true
}

resource "google_project_iam_member" "gcp_iam_infra_owner" {
  project = var.gcp_project
  role    = "roles/owner"
  member  = google_service_account.gcp_iam_infra_sa.member
}

resource "google_project_iam_member" "gcp_serviceusage_admin" {
  project = var.gcp_project
  role    = "roles/serviceusage.serviceUsageAdmin"
  member  = google_service_account.gcp_iam_infra_sa.member
}

#####################################
# Create Workload identity (WI) Pools
resource "google_iam_workload_identity_pool" "gcp_wi_infra_pool" {
  workload_identity_pool_id = "infra-pool"
  display_name              = "Infrastructure pool"
  description               = "Group all externals applications that need communication with GCP to perform infrastructure lifecyle management."
  disabled                  = false
}

############################
# Define Identity Providers
resource "google_iam_workload_identity_pool_provider" "gcp_hcp_tf_oidc_provider" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.gcp_wi_infra_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "hcp-tf-oidc-provider"
  display_name                       = "HCP Terraform OIDC Provider"
  description                        = "Used to authenticate to Google Cloud from HCP Terraform"
  attribute_condition                = "assertion.terraform_organization_name=='${var.hcp_terraform_org_name}'"
  attribute_mapping = {
    "google.subject"                        = "assertion.sub"
    "attribute.terraform_workspace_id"      = "assertion.terraform_workspace_id"
    "attribute.terraform_full_workspace"    = "assertion.terraform_full_workspace"
    "attribute.terraform_organization_name" = "assertion.terraform_organization_name"
  }
  oidc {
    issuer_uri = "https://app.terraform.io"
  }
}

################################
# SA impersonations by providers
resource "google_service_account_iam_member" "gcp_infra_sa_impersonate_by_hcp_tf_oidc_provider" {
  service_account_id = google_service_account.gcp_iam_infra_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.gcp_wi_infra_pool.name}/*"
}

#################################
# Setup HCP Terraform to use WIF
resource "tfe_variable_set" "gcp_hcp_wif_sa_variable_set" {
  name         = google_service_account.gcp_iam_infra_sa.account_id
  description  = "Workload identity federation configuration for ${google_service_account.gcp_iam_infra_sa.name} impersonation"
  organization = var.hcp_terraform_org_name
}

resource "tfe_workspace_variable_set" "gcp_hcp_wif_sa_ws_variable_set" {
  variable_set_id = tfe_variable_set.gcp_hcp_wif_sa_variable_set.id
  workspace_id    = var.hcp_terraform_ws_id
}

resource "tfe_variable" "gcp_hcp_tf_provider_auth" {
  key             = "TFC_GCP_PROVIDER_AUTH"
  value           = "true"
  category        = "env"
  variable_set_id = tfe_variable_set.gcp_hcp_wif_sa_variable_set.id
}

resource "tfe_variable" "gcp_hcp_tf_sa_email" {
  sensitive       = true
  key             = "TFC_GCP_RUN_SERVICE_ACCOUNT_EMAIL"
  value           = google_service_account.gcp_iam_infra_sa.email
  category        = "env"
  variable_set_id = tfe_variable_set.gcp_hcp_wif_sa_variable_set.id
}

resource "tfe_variable" "gcp_hcp_tf_provider_name" {
  sensitive       = true
  key             = "TFC_GCP_WORKLOAD_PROVIDER_NAME"
  value           = google_iam_workload_identity_pool_provider.gcp_hcp_tf_oidc_provider.name
  category        = "env"
  variable_set_id = tfe_variable_set.gcp_hcp_wif_sa_variable_set.id
}
