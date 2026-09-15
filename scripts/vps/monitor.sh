#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

require_file "$COMPOSE_ENV_FILE"
mkdir -p "$STATE_DIR"

status_file="${STATE_DIR}/last-monitor"
checked_at="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

record_failure() {
  local exit_code=$?
  if ((exit_code != 0)); then
    printf 'status=failed\nchecked_at=%s\nexit_code=%s\n' \
      "$checked_at" "$exit_code" > "$status_file"
  fi
}
trap record_failure EXIT

public_host="$(env_value PUBLIC_HOST)"
if [[ ! "$public_host" =~ ^[A-Za-z0-9.-]+$ ]]; then
  echo "PUBLIC_HOST is missing or contains unsupported characters." >&2
  exit 1
fi

for endpoint in health ready ready/rag; do
  curl \
    --fail \
    --silent \
    --show-error \
    --retry 3 \
    --retry-delay 2 \
    --max-time 15 \
    --resolve "${public_host}:443:127.0.0.1" \
    "https://${public_host}/${endpoint}" \
    > /dev/null
done

disk_usage="$(df -P / | awk 'NR == 2 {gsub(/%/, "", $5); print $5}')"
if [[ ! "$disk_usage" =~ ^[0-9]+$ ]]; then
  echo "Could not parse root disk usage: ${disk_usage}" >&2
  exit 1
fi
if ((disk_usage > 70)); then
  echo "Root disk usage ${disk_usage}% exceeds the 70% limit." >&2
  exit 1
fi

printf 'status=ok\nchecked_at=%s\ndisk_usage_percent=%s\n' \
  "$checked_at" "$disk_usage" > "$status_file"

echo "Staging monitor passed at ${checked_at}; root disk usage: ${disk_usage}%."
