# CI/CD and staging deployment

The application uses the organization's ephemeral self-hosted Actions runners and a single
Google Cloud staging VPS funded by remaining Welcome credit on a Paid billing account.
Render is no longer part of the release path.

## Workflows

- `ci.yml` runs Ruff, Alembic and pytest against an isolated tmpfs ParadeDB, then smoke-tests
  the production image. It runs for pull requests and pushes to `develop` or `main`.
- `main-merge-guard.yml` verifies that pull requests into `main` come from `develop`.
- `release.yml` builds and publishes a `linux/amd64` GHCR image by immutable digest, then
  deploys it to the `staging` GitHub Environment on pushes to `main`.
- `staging-monitor.yml` provides an on-demand external health/readiness and disk check.

CI ignores pull requests from forks so untrusted code cannot execute on a self-hosted runner.
Only the publish job has `packages: write`; deploy secrets belong to the protected `staging`
Environment and are used only after a push to `main`. GitHub-hosted runner billing is not
part of this deployment path. Release builds use inline cache metadata from the `main` GHCR
image instead of GitHub Actions cache storage.

## Infrastructure

Terraform under `infra/gcp` creates one `e2-medium` Ubuntu 24.04 VM in
`asia-southeast1-b`, a 30 GB standard persistent boot disk, firewall rules and a
7,897,351 VND budget matching the billing account's displayed Welcome credit. The VM uses
an ephemeral IPv4 address and an `sslip.io` hostname. PostgreSQL and
FastAPI remain private behind Caddy.

The VPS runs `p040-monitor.timer` every five minutes. It validates the local Caddy HTTPS
route, `/health`, `/ready`, and the 70% root-disk threshold. This runtime monitoring remains
active even if GitHub Actions is unavailable.

The Paid billing account can charge its payment method after credit is exhausted. Do not
apply until the operator confirms remaining credit and accepts that risk. Welcome credit
expires on 2026-11-13; the mandatory backup and destroy deadline is 2026-11-08. The setup
deliberately creates no load balancer, Cloud SQL, reserved IP, snapshot schedule or object
storage. Budget alerts are notifications, not a hard spending cap.

## Operations

The canonical, step-by-step procedure for provisioning, GitHub Environment configuration,
first deploy, rollback, backup and the day-90 exit is
[deployment-vps-runbook.md](deployment-vps-runbook.md).

Local quality gate:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test-backend.ps1
```

Runtime secrets belong only in `/opt/p040/env` and GitHub Environment secrets. Never commit
Terraform variables, SSH keys, database credentials, API keys or downloaded backups.
