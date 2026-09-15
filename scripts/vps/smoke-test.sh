#!/usr/bin/env bash

set -Eeuo pipefail

PUBLIC_URL="${1:-${PUBLIC_URL:-}}"
MAX_ATTEMPTS="${2:-30}"

if [[ -z "$PUBLIC_URL" ]]; then
  echo "Usage: smoke-test.sh https://api.example.com [max-attempts]" >&2
  exit 1
fi

PUBLIC_URL="${PUBLIC_URL%/}"

for ((attempt = 1; attempt <= MAX_ATTEMPTS; attempt++)); do
  health_body="$(curl --fail --silent --show-error --max-time 10 "${PUBLIC_URL}/health" 2>/dev/null || true)"
  ready_body="$(curl --fail --silent --show-error --max-time 10 "${PUBLIC_URL}/ready" 2>/dev/null || true)"

  if [[ "$health_body" == *'"status":"ok"'* && "$ready_body" == *'"status":"ready"'* ]]; then
    echo "Smoke test passed: ${PUBLIC_URL}"
    exit 0
  fi

  echo "Attempt ${attempt}/${MAX_ATTEMPTS}: service is not ready yet."
  sleep 2
done

echo "Smoke test failed: ${PUBLIC_URL}" >&2
exit 1
