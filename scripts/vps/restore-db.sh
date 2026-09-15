#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

backup_input="${1:-}"
confirmation="${2:-}"
if [[ -z "$backup_input" || "$confirmation" != "--confirm-restore" ]]; then
  echo "Usage: restore-db.sh /opt/p040/backups/file.dump --confirm-restore" >&2
  exit 1
fi

prepare_compose
export BACKEND_IMAGE="${BACKEND_IMAGE:-busybox:1.36}"

backup_file="$(realpath -- "$backup_input")"
resolved_backup_dir="$(realpath -- "$BACKUP_DIR")"
case "$backup_file" in
  "${resolved_backup_dir}"/*.dump) ;;
  *)
    echo "Refusing to restore a file outside ${resolved_backup_dir}." >&2
    exit 1
    ;;
esac
require_file "$backup_file"

if [[ -f "${backup_file}.sha256" ]]; then
  (cd -- "$(dirname -- "$backup_file")" && sha256sum --check "$(basename -- "${backup_file}.sha256")")
fi

compose up -d db
compose stop backend 2>/dev/null || true

cat "$backup_file" | compose exec -T db sh -c \
  'exec pg_restore --clean --if-exists --no-owner --no-privileges --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"'

if [[ -f "${STATE_DIR}/current-image" ]]; then
  export BACKEND_IMAGE="$(<"${STATE_DIR}/current-image")"
  compose run --rm migrate
  compose up -d backend caddy
fi

echo "Database restore completed from ${backup_file}. Run smoke-test.sh before reopening traffic."
