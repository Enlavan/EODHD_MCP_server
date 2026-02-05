#!/usr/bin/env bash
set -euo pipefail

# Generate a strong JWT secret and export it for the current shell session.
# Usage:
#   source scripts/gen_jwt_secret.sh

secret="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"

export JWT_SECRET="$secret"
echo "JWT_SECRET exported for this shell session."
