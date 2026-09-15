#!/usr/bin/env bash

set -Eeuo pipefail

DEPLOY_USER="${DEPLOY_USER:-p040-deploy}"
P040_BASE_DIR="${P040_BASE_DIR:-/opt/p040}"
CONFIGURE_UFW="${CONFIGURE_UFW:-false}"
CONFIGURE_SSH_HARDENING="${CONFIGURE_SSH_HARDENING:-false}"
DEPLOY_PUBLIC_KEY="${DEPLOY_PUBLIC_KEY:-}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this bootstrap script as root." >&2
  exit 1
fi

if [[ ! -f /etc/os-release ]]; then
  echo "Unsupported operating system: /etc/os-release is missing." >&2
  exit 1
fi

if [[ ! "$DEPLOY_USER" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  echo "DEPLOY_USER contains unsupported characters." >&2
  exit 1
fi
if [[ "$CONFIGURE_SSH_HARDENING" == "true" && -z "$DEPLOY_PUBLIC_KEY" ]]; then
  echo "DEPLOY_PUBLIC_KEY is required before SSH hardening can be enabled." >&2
  exit 1
fi

# shellcheck disable=SC1091
. /etc/os-release
if [[ "${ID:-}" != "ubuntu" ]]; then
  echo "This bootstrap script supports Ubuntu only." >&2
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl gnupg unattended-upgrades ufw

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

ARCH="$(dpkg --print-architecture)"
CODENAME="${UBUNTU_CODENAME:-${VERSION_CODENAME}}"
echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "$DEPLOY_USER"
fi
usermod -aG docker "$DEPLOY_USER"
printf '%s ALL=(ALL) NOPASSWD: ALL\n' "$DEPLOY_USER" > "/etc/sudoers.d/${DEPLOY_USER}"
chmod 0440 "/etc/sudoers.d/${DEPLOY_USER}"

install -d -m 0750 -o "$DEPLOY_USER" -g "$DEPLOY_USER" \
  "$P040_BASE_DIR" \
  "$P040_BASE_DIR/deploy" \
  "$P040_BASE_DIR/env" \
  "$P040_BASE_DIR/scripts" \
  "$P040_BASE_DIR/state" \
  "$P040_BASE_DIR/backups"

if [[ -n "$DEPLOY_PUBLIC_KEY" ]]; then
  install -d -m 0700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "/home/${DEPLOY_USER}/.ssh"
  printf '%s\n' "$DEPLOY_PUBLIC_KEY" > "/home/${DEPLOY_USER}/.ssh/authorized_keys"
  chown "$DEPLOY_USER:$DEPLOY_USER" "/home/${DEPLOY_USER}/.ssh/authorized_keys"
  chmod 0600 "/home/${DEPLOY_USER}/.ssh/authorized_keys"
fi

if [[ "$CONFIGURE_SSH_HARDENING" == "true" ]]; then
  cat > /etc/ssh/sshd_config.d/99-p040-hardening.conf <<'EOF'
PasswordAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
EOF
  systemctl restart ssh
fi

if [[ "$CONFIGURE_UFW" == "true" ]]; then
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw allow 443/udp
  ufw --force enable
else
  echo "UFW was not enabled. Review the SSH port, then configure ports 22, 80 and 443 manually."
fi

echo "Bootstrap complete. Log out and back in before ${DEPLOY_USER} uses Docker."
echo "Docker and passwordless sudo are root-equivalent; protect the deploy SSH key accordingly."
