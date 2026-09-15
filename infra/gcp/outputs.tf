locals {
  external_ip = google_compute_instance.staging.network_interface[0].access_config[0].nat_ip
  sslip_host  = "api-staging.${replace(local.external_ip, ".", "-")}.sslip.io"
}

output "project_id" {
  value = google_project.staging.project_id
}

output "instance_external_ip" {
  value = local.external_ip
}

output "public_host" {
  value = local.sslip_host
}

output "public_url" {
  value = "https://${local.sslip_host}"
}

output "ssh_command" {
  value = "ssh ${local.deploy_user}@${local.external_ip}"
}

output "credit_expiry_date" {
  value = var.credit_expiry_date
}

output "mandatory_teardown_date" {
  value = var.teardown_deadline
}
