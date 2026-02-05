#!/usr/bin/env bash
set -euo pipefail

# Generate a strong JWT secret and write it to .env.
# Usage:
#   ./scripts/gen_jwt_secret_to_env.sh

ENV_FILE="${1:-.env}"

secret="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"

if [[ -f "$ENV_FILE" ]]; then
  # Remove existing JWT_SECRET line(s)
  tmp="$(mktemp)"
  rg -v '^JWT_SECRET=' "$ENV_FILE" > "$tmp" || true
  mv "$tmp" "$ENV_FILE"
fi

echo "JWT_SECRET=$secret" >> "$ENV_FILE"
echo "Wrote JWT_SECRET to $ENV_FILE"
