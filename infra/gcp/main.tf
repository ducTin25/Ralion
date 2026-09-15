resource "random_id" "project_suffix" {
  byte_length = 3
}

locals {
  project_id  = "${var.project_id_prefix}-${random_id.project_suffix.hex}"
  deploy_user = "p040-deploy"
  common_labels = {
    environment = "staging"
    managed_by  = "terraform"
    teardown_by = "d${replace(var.teardown_deadline, "-", "_")}"
  }
  api_services = toset([
    "billingbudgets.googleapis.com",
    "cloudbilling.googleapis.com",
    "compute.googleapis.com",
    "serviceusage.googleapis.com",
  ])
}

resource "google_project" "staging" {
  name                = "p040-staging"
  project_id          = local.project_id
  billing_account     = var.billing_account_id
  auto_create_network = false
  deletion_policy     = "DELETE"
  labels              = local.common_labels

  lifecycle {
    precondition {
      condition     = timecmp("${var.teardown_deadline}T23:59:59Z", plantimestamp()) > 0
      error_message = "The approved 2026-11-08 teardown deadline has passed; do not create or update paid resources."
    }
  }
}

resource "google_project_service" "apis" {
  for_each = local.api_services

  project            = google_project.staging.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_compute_network" "staging" {
  project                 = google_project.staging.project_id
  name                    = "p040-staging"
  auto_create_subnetworks = false

  depends_on = [google_project_service.apis["compute.googleapis.com"]]
}

resource "google_compute_subnetwork" "staging" {
  project       = google_project.staging.project_id
  name          = "p040-staging-sg"
  region        = var.region
  network       = google_compute_network.staging.id
  ip_cidr_range = "10.40.0.0/24"
}

resource "google_compute_firewall" "ssh" {
  project = google_project.staging.project_id
  name    = "p040-allow-ssh"
  network = google_compute_network.staging.name

  source_ranges = var.ssh_source_ranges
  target_tags   = ["p040-staging"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

resource "google_compute_firewall" "web" {
  project = google_project.staging.project_id
  name    = "p040-allow-web"
  network = google_compute_network.staging.name

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["p040-staging"]

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  allow {
    protocol = "udp"
    ports    = ["443"]
  }
}

resource "google_compute_instance" "staging" {
  project      = google_project.staging.project_id
  name         = "p040-staging"
  zone         = var.zone
  machine_type = var.machine_type
  tags         = ["p040-staging"]
  labels       = local.common_labels

  allow_stopping_for_update = true
  deletion_protection       = false

  boot_disk {
    auto_delete = true
    initialize_params {
      image = "projects/ubuntu-os-cloud/global/images/family/ubuntu-2404-lts-amd64"
      size  = var.boot_disk_size_gb
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.staging.id

    # Deliberately ephemeral: avoids reserving an address during the trial.
    access_config {}
  }

  metadata = {
    block-project-ssh-keys = "true"
  }

  metadata_startup_script = templatefile("${path.module}/startup.sh.tftpl", {
    deploy_user           = local.deploy_user
    deploy_public_key_b64 = base64encode(trimspace(var.deploy_public_key))
    bootstrap_script_b64  = base64encode(file("${path.module}/../../scripts/vps/bootstrap.sh"))
    backup_service_b64    = base64encode(file("${path.module}/../../deploy/systemd/p040-backup.service"))
    backup_timer_b64      = base64encode(file("${path.module}/../../deploy/systemd/p040-backup.timer"))
    monitor_service_b64   = base64encode(file("${path.module}/../../deploy/systemd/p040-monitor.service"))
    monitor_timer_b64     = base64encode(file("${path.module}/../../deploy/systemd/p040-monitor.timer"))
  })

  shielded_instance_config {
    enable_integrity_monitoring = true
    enable_secure_boot          = true
    enable_vtpm                 = true
  }

  depends_on = [google_project_service.apis["compute.googleapis.com"]]
}

resource "google_billing_budget" "trial_credit" {
  provider = google.billing

  billing_account = var.billing_account_id
  display_name    = "P-040 staging Welcome credit guard"

  budget_filter {
    projects               = ["projects/${google_project.staging.number}"]
    credit_types_treatment = "EXCLUDE_ALL_CREDITS"
  }

  amount {
    specified_amount {
      # The billing account is denominated in VND; Google rejects USD budgets
      # even though the Welcome credit is marketed as USD 300.
      currency_code = "VND"
      units         = tostring(var.billing_budget_units_vnd)
    }
  }

  threshold_rules { threshold_percent = 0.003333 }
  threshold_rules { threshold_percent = 0.166667 }
  threshold_rules { threshold_percent = 0.666667 }
  threshold_rules { threshold_percent = 0.933333 }

  depends_on = [google_project_service.apis["billingbudgets.googleapis.com"]]
}
