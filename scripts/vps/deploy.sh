#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

new_image="${1:-}"
expected_prefix="ghcr.io/ductin25/ralion@sha256:"
local_image=false
if [[ "$new_image" =~ ^sha256:[a-f0-9]{64}$ ]]; then
  if ! docker image inspect "$new_image" >/dev/null 2>&1; then
    echo "Local content-addressed image is not present: ${new_image}" >&2
    exit 1
  fi
  local_image=true
elif [[ ! "$new_image" =~ ^${expected_prefix}[a-f0-9]{64}$ ]]; then
  echo "Usage: deploy.sh ${expected_prefix}<64 lowercase hex characters> | sha256:<local image ID>" >&2
  exit 1
fi

prepare_compose
exec 9>"${STATE_DIR}/deploy.lock"
if ! flock -n 9; then
  echo "Another deployment is already running." >&2
  exit 1
fi

public_url="$(env_value PUBLIC_URL)"
if [[ -z "$public_url" ]]; then
  echo "PUBLIC_URL is required in ${COMPOSE_ENV_FILE}." >&2
  exit 1
fi

previous_image=""
if [[ -f "${STATE_DIR}/current-image" ]]; then
  previous_image="$(<"${STATE_DIR}/current-image")"
fi

rollback() {
  local exit_code=$?
  trap - ERR
  echo "Deployment failed for ${new_image}." >&2
  export BACKEND_IMAGE="$new_image"
  compose logs --no-color --tail=150 backend migrate 2>/dev/null || true

  if [[ -n "$previous_image" ]]; then
    echo "Rolling the application back to ${previous_image}." >&2
    export BACKEND_IMAGE="$previous_image"
    compose up -d --no-deps backend
    "${SCRIPT_DIR}/smoke-test.sh" "$public_url" 30 || true
  else
    echo "No previous application image is available for rollback." >&2
  fi
  exit "$exit_code"
}
trap rollback ERR

export BACKEND_IMAGE="$new_image"
if [[ "$local_image" == "true" ]]; then
  # Manual fallback for unavailable GitHub Actions/GHCR credentials. The image
  # arrives over pinned SSH and is addressed by its verified Docker content ID.
  compose pull db caddy
else
  compose pull db backend caddy
fi
compose up -d db

if [[ -n "$previous_image" ]]; then
  "${SCRIPT_DIR}/backup-db.sh"
fi

compose run --rm migrate
compose up -d --remove-orphans backend caddy

# Verify readiness inside the container before relying on public DNS and TLS.
for attempt in {1..30}; do
  if compose exec -T backend python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready', timeout=5)"; then
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    echo "Backend did not become internally ready." >&2
    false
  fi
  sleep 2
done

"${SCRIPT_DIR}/smoke-test.sh" "$public_url" 45

if [[ -n "$previous_image" ]]; then
  printf '%s\n' "$previous_image" > "${STATE_DIR}/previous-image"
fi
printf '%s\n' "$new_image" > "${STATE_DIR}/current-image"
chmod 0600 "${STATE_DIR}/current-image"
[[ ! -f "${STATE_DIR}/previous-image" ]] || chmod 0600 "${STATE_DIR}/previous-image"

trap - ERR
docker image prune --force --filter "until=168h" >/dev/null
echo "Deployment succeeded: ${new_image}"
