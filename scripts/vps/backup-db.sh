#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

prepare_compose
export BACKEND_IMAGE="${BACKEND_IMAGE:-busybox:1.36}"

timestamp="$(date -u +'%Y%m%dT%H%M%SZ')"
backup_file="${BACKUP_DIR}/pgonboarding-${timestamp}.dump"
partial_file="${backup_file}.partial"
checksum_file="${backup_file}.sha256"

cleanup_partial() {
  rm -f -- "$partial_file"
}
trap cleanup_partial EXIT

compose exec -T db sh -c 'exec pg_dump --format=custom --no-owner --no-privileges --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"' \
  > "$partial_file"

if [[ ! -s "$partial_file" ]]; then
  echo "Database backup is empty." >&2
  exit 1
fi

mv -- "$partial_file" "$backup_file"
trap - EXIT
sha256sum "$backup_file" > "$checksum_file"
chmod 0600 "$backup_file" "$checksum_file"

retention_count="$(env_value BACKUP_RETENTION_COUNT 3)"
if [[ ! "$retention_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "BACKUP_RETENTION_COUNT must be a positive integer." >&2
  exit 1
fi

# The trial uses no paid object storage. Keep only the newest dumps on the VM;
# a weekly workstation download provides the off-VM copy.
mapfile -d '' -t backup_files < <(
  find "$BACKUP_DIR" -maxdepth 1 -type f -name '*.dump' -printf '%T@ %p\0' | sort -zrn
)
for ((index = retention_count; index < ${#backup_files[@]}; index++)); do
  expired_file="${backup_files[$index]#* }"
  rm -f -- "$expired_file" "${expired_file}.sha256"
done

echo "Database backup created: ${backup_file}"
