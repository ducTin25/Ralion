#!/usr/bin/env bash

set -Eeuo pipefail

P040_BASE_DIR="${P040_BASE_DIR:-/opt/p040}"
COMPOSE_FILE="${COMPOSE_FILE:-${P040_BASE_DIR}/deploy/compose.vps.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-${P040_BASE_DIR}/env/compose.env}"
STATE_DIR="${STATE_DIR:-${P040_BASE_DIR}/state}"
BACKUP_DIR="${BACKUP_DIR:-${P040_BASE_DIR}/backups}"

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "Required file not found: $path" >&2
    exit 1
  fi
}

env_value() {
  local key="$1"
  local fallback="${2:-}"
  local value

  value="$(awk -v key="$key" '
    index($0, key "=") == 1 {
      print substr($0, length(key) + 2)
      exit
    }
  ' "$COMPOSE_ENV_FILE" | tr -d '\r')"
  printf '%s' "${value:-$fallback}"
}

prepare_compose() {
  require_file "$COMPOSE_FILE"
  require_file "$COMPOSE_ENV_FILE"
  mkdir -p "$STATE_DIR" "$BACKUP_DIR"

  COMPOSE_PROJECT_NAME="$(env_value COMPOSE_PROJECT_NAME p040)"
  export COMPOSE_PROJECT_NAME

  if [[ -z "${BACKEND_IMAGE:-}" && -f "${STATE_DIR}/current-image" ]]; then
    BACKEND_IMAGE="$(<"${STATE_DIR}/current-image")"
    export BACKEND_IMAGE
  fi
}

compose() {
  docker compose \
    --env-file "$COMPOSE_ENV_FILE" \
    --project-name "$COMPOSE_PROJECT_NAME" \
    --file "$COMPOSE_FILE" \
    "$@"
}
