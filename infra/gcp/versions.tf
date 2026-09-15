terraform {
  required_version = ">= 1.8.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0, < 8.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6, < 4.0"
    }
  }
}

provider "google" {
  region = var.region
  zone   = var.zone
}

# Billing Budget API calls made with user ADC need a quota project with
# billingbudgets.googleapis.com enabled. Keep this override isolated from the
# provider used by the project, network, and VM resources.
provider "google" {
  alias                 = "billing"
  region                = var.region
  zone                  = var.zone
  billing_project       = var.billing_quota_project_id
  user_project_override = var.billing_quota_project_id != null
}
