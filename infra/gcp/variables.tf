variable "billing_account_id" {
  description = "Google Cloud Paid billing account with remaining Welcome credit."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", upper(var.billing_account_id)))
    error_message = "billing_account_id must use the 000000-000000-000000 Google billing account format."
  }
}

variable "billing_quota_project_id" {
  description = "Existing project used only as the ADC quota project for Billing Budget API calls. Set this to the staging project ID on the second apply after that project exists."
  type        = string
  default     = null

  validation {
    condition     = var.billing_quota_project_id == null || can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.billing_quota_project_id))
    error_message = "billing_quota_project_id must be null or a valid Google Cloud project ID."
  }
}

variable "billing_budget_units_vnd" {
  description = "Welcome credit value shown by this VND-denominated billing account. Budget APIs require the billing account currency."
  type        = number
  default     = 7897351

  validation {
    condition     = var.billing_budget_units_vnd == 7897351
    error_message = "The approved Welcome credit budget is locked to 7,897,351 VND. Re-review Billing before changing it."
  }
}

variable "deploy_public_key" {
  description = "OpenSSH public key for the p040-deploy user."
  type        = string

  validation {
    condition     = startswith(trimspace(var.deploy_public_key), "ssh-ed25519 ")
    error_message = "deploy_public_key must be an Ed25519 OpenSSH public key."
  }
}

variable "credit_backed_paid_account_confirmed" {
  description = "Explicit acknowledgement that this is a Paid account, charges can exceed credit, and teardown is required before the deadline."
  type        = bool
  default     = false

  validation {
    condition     = var.credit_backed_paid_account_confirmed
    error_message = "Set credit_backed_paid_account_confirmed=true only after accepting Paid account risk and verifying remaining credit."
  }
}

variable "credit_expiry_date" {
  description = "Welcome credit expiry date confirmed in Google Cloud Console."
  type        = string
  default     = "2026-11-13"

  validation {
    condition     = var.credit_expiry_date == "2026-11-13"
    error_message = "The reviewed credit window expires on 2026-11-13. Re-review billing before changing this date."
  }
}

variable "teardown_deadline" {
  description = "Mandatory destroy deadline, five days before the Welcome credit expires."
  type        = string
  default     = "2026-11-08"

  validation {
    condition     = var.teardown_deadline == "2026-11-08"
    error_message = "The approved teardown deadline is locked to 2026-11-08."
  }
}

variable "project_id_prefix" {
  description = "Prefix for the globally unique project ID."
  type        = string
  default     = "p040-staging"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,23}[a-z0-9]$", var.project_id_prefix))
    error_message = "project_id_prefix must be 6-25 lowercase letters, digits or hyphens."
  }
}

variable "region" {
  description = "Singapore region used during the remaining credit window."
  type        = string
  default     = "asia-southeast1"

  validation {
    condition     = var.region == "asia-southeast1"
    error_message = "The reviewed staging region is locked to asia-southeast1."
  }
}

variable "zone" {
  description = "Singapore zone for the staging VM."
  type        = string
  default     = "asia-southeast1-b"

  validation {
    condition     = var.zone == "asia-southeast1-b"
    error_message = "The trial staging zone is locked to asia-southeast1-b."
  }
}

variable "machine_type" {
  description = "Shared-core VM covered by the remaining Welcome credit."
  type        = string
  default     = "e2-medium"

  validation {
    condition     = var.machine_type == "e2-medium"
    error_message = "The reviewed credit-backed plan permits only e2-medium."
  }
}

variable "boot_disk_size_gb" {
  description = "Small standard persistent disk; Docker cleanup and backup retention protect capacity."
  type        = number
  default     = 30

  validation {
    condition     = var.boot_disk_size_gb == 30
    error_message = "The reviewed credit-backed plan permits exactly a 30 GB boot disk."
  }
}

variable "ssh_source_ranges" {
  description = "CIDRs allowed to SSH. Shared ephemeral runners have changing egress IPs, so the default relies on key-only SSH."
  type        = list(string)
  default     = ["0.0.0.0/0"]

  validation {
    condition     = length(var.ssh_source_ranges) > 0 && alltrue([for cidr in var.ssh_source_ranges : can(cidrnetmask(cidr))])
    error_message = "ssh_source_ranges must contain valid IPv4 CIDR ranges."
  }
}
