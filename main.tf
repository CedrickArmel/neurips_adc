#####################
# Import requirements

terraform {
  cloud {
    organization = "mienmo"

    workspaces {
      name = "neurips_adc"
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

########################
# Data sources

data "tfe_workspace" "workspace" {
  name         = "neurips_adc"
  organization = "mienmo"
}


############################# SETUP TERRAFORM PLATFORM ########################################################

###################
# Resources imports

##########################
# Create Services Accounts (SA)
resource "google_service_account" "gcp_iam_infra_sa" {
  account_id                   = var.gcp_iam_infra_sa_account_id
  display_name                 = "Core IAM & Infra LC management SA from outside GCP (Terraform, GHA, etc.)"
  create_ignore_already_exists = true
}

# Bind roles to the Infrastructure Service Account using var.infra_sa_roles
resource "google_project_iam_member" "infra_sa_roles_binding" {
  for_each = toset(var.infra_sa_roles)
  project  = var.gcp_project
  role     = each.value
  member   = google_service_account.gcp_iam_infra_sa.member
}

#####################################
# Create Workload identity (WI) Pools
resource "google_iam_workload_identity_pool" "gcp_wi_infra_pool" {
  workload_identity_pool_id = "infra-pool-1"
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
  attribute_condition                = "assertion.terraform_organization_name=='${data.tfe_workspace.workspace.organization}'" # var.hcp_terraform_org_name
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
  organization = data.tfe_workspace.workspace.organization # var.hcp_terraform_org_name
}

resource "tfe_workspace_variable_set" "gcp_hcp_wif_sa_ws_variable_set" {
  variable_set_id = tfe_variable_set.gcp_hcp_wif_sa_variable_set.id
  workspace_id    = data.tfe_workspace.workspace.id # var.hcp_terraform_ws_id
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

resource "tfe_workspace_variable_set" "gcp_hcp_apply_variable_set" {
  variable_set_id = tfe_variable_set.gcp_hcp_wif_sa_variable_set.id
  workspace_id    = data.tfe_workspace.workspace.id
}



############################# SETUP THE ML PLATFORM ########################################################


##########################
# Create Services Accounts (SA)
resource "google_service_account" "gcp_sa" {
  for_each                     = var.gcp_service_accounts
  account_id                   = each.value.sa_id
  display_name                 = each.value.name
  create_ignore_already_exists = true
  depends_on                   = [tfe_workspace_variable_set.gcp_hcp_apply_variable_set]
}

locals {
  sa_roles = flatten([
    for sa_key, sa_value in var.gcp_service_accounts : [
      for role in sa_value.roles : {
        sa_key = sa_key
        role   = role
      }
    ]
  ])
}
resource "google_project_iam_member" "gcp_sa_roles" {
  for_each = { for sa_role in local.sa_roles : "${sa_role.sa_key}-${sa_role.role}" => sa_role }
  project  = var.gcp_project
  role     = each.value.role
  member   = google_service_account.gcp_sa[each.value.sa_key].member
}


#####################################
# Create Workload identity (WI) Pools
resource "google_iam_workload_identity_pool" "gcp_wi_mlops_pool" {
  workload_identity_pool_id = "mlops-pool-1"
  display_name              = "MLOps pool"
  description               = "Group all externals applications that need communication with GCP to perform CI/CD/CT."
  disabled                  = false
  depends_on                = [tfe_workspace_variable_set.gcp_hcp_apply_variable_set]
}

############################
# Define Identity Providers
resource "google_iam_workload_identity_pool_provider" "gcp_gha_oidc_provider" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.gcp_wi_mlops_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions-oidc-provider"
  display_name                       = "GitHub Actions OIDC Provider"
  description                        = "Used to authenticate to Google Cloud from GHA"
  disabled                           = false
  attribute_mapping = {
    "google.subject"  = "assertion.sub"
    "attribute.aud"   = "assertion.aud"
    "attribute.actor" = "assertion.actor"
  }
  attribute_condition = "assertion.sub=='${var.gha_assertion_sub}' && assertion.aud=='${var.gha_assertion_aud}' && assertion.actor=='${var.gha_assertion_actor}'"
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

################################
# SA impersonations by providers
resource "google_service_account_iam_member" "gcp_ml_sa_impersonate_by_gha_oidc_provider" {
  service_account_id = google_service_account.gcp_sa["gcp_ml_sa"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.gcp_wi_mlops_pool.name}/*"
}


###############################
# Enable services API
resource "google_project_service" "gcp_enable_services" {
  for_each = toset(var.gcp_enabled_services)
  project  = var.gcp_project
  service  = each.value
}
