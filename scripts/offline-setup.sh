#!/usr/bin/env bash
# First-run setup for the offline distribution.
# Idempotent: re-running with .env already present just verifies it.
set -euo pipefail

cd "$(dirname "$0")"
APP_DIR="$(pwd)"
ENV_FILE="$APP_DIR/.env"

if [ -f "$ENV_FILE" ] && grep -q '^GOOGLE_MAPS_API_KEY=' "$ENV_FILE"; then
  echo "Setup already done: $ENV_FILE exists with GOOGLE_MAPS_API_KEY set."
  echo "Delete .env to re-run setup."
  exit 0
fi

echo "Mini-Grid Optimization Tool — first-run setup"
echo
read -r -p "Enter your Google Maps API key: " MAPS_KEY
if [ -z "$MAPS_KEY" ]; then
  echo "Error: Google Maps API key is required." >&2
  exit 1
fi

# Generate a per-install AUTH_SECRET. Used by NextAuth's machinery; we never
# actually authenticate (offline mode bypasses NextAuth) but the runtime
# refuses to boot without one.
AUTH_SECRET="$(openssl rand -base64 32)"

cat > "$ENV_FILE" <<EOF
OFFLINE_MODE=true
DATABASE_URL=file:$APP_DIR/prisma/offline.db
NEXTAUTH_URL=http://localhost:3000
AUTH_TRUST_HOST=true
AUTH_SECRET=$AUTH_SECRET
GOOGLE_MAPS_API_KEY=$MAPS_KEY
PORT=3000
HOSTNAME=0.0.0.0
EOF

echo
echo "Wrote $ENV_FILE"
echo "Run ./start.sh to launch."
