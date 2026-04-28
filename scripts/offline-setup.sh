#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
APP_DIR="$(pwd)"
ENV_FILE="$APP_DIR/.env"

case "$(uname -s)" in
  Darwin) DATA_DIR="$HOME/Library/Application Support/minigrid-solver" ;;
  Linux)  DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/minigrid-solver" ;;
  *)
    echo "Error: unsupported platform $(uname -s). Layer 2 supports macOS and Linux." >&2
    exit 1
    ;;
esac
DB_PATH="$DATA_DIR/offline.db"

if [ -f "$ENV_FILE" ] && grep -q '^GOOGLE_MAPS_API_KEY=' "$ENV_FILE"; then
  echo "Setup already done: $ENV_FILE exists with GOOGLE_MAPS_API_KEY set."
  echo "Delete .env to re-run setup."
  exit 0
fi

echo "Mini-Grid Optimizer — first-run setup"
echo
echo "Section 1 of 2: Maps (required)"
read -r -p "  Google Maps API key: " MAPS_KEY
if [ -z "$MAPS_KEY" ]; then
  echo "Error: Google Maps API key is required." >&2
  exit 1
fi

echo
echo "Section 2 of 2: Authentication (optional)"
echo "  Leave blank to use a single local anonymous account."
echo "  Provide both values to enable Google sign-in."
read -r -p "  Google OAuth client ID (or blank): " GOOGLE_ID
GOOGLE_SECRET=""
if [ -n "$GOOGLE_ID" ]; then
  read -r -p "  Google OAuth client secret: " GOOGLE_SECRET
  if [ -z "$GOOGLE_SECRET" ]; then
    echo "Error: client secret is required when client ID is provided." >&2
    exit 1
  fi
fi

mkdir -p "$DATA_DIR"
if [ ! -f "$DB_PATH" ]; then
  cp "$APP_DIR/prisma/offline.db" "$DB_PATH"
  echo "Initialized database at $DB_PATH"
else
  echo "Reusing existing database at $DB_PATH"
fi

AUTH_SECRET="$(openssl rand -base64 32)"

{
  echo "OFFLINE_MODE=true"
  echo "DATABASE_URL=\"file:$DB_PATH\""
  echo "NEXTAUTH_URL=http://localhost:3000"
  echo "AUTH_TRUST_HOST=true"
  echo "AUTH_SECRET=\"$AUTH_SECRET\""
  echo "GOOGLE_MAPS_API_KEY=\"$MAPS_KEY\""
  if [ -n "$GOOGLE_ID" ]; then
    echo "AUTH_GOOGLE_ID=\"$GOOGLE_ID\""
    echo "AUTH_GOOGLE_SECRET=\"$GOOGLE_SECRET\""
  fi
  echo "PORT=3000"
  echo "HOSTNAME=127.0.0.1"
  echo "SOLVER_HOST=127.0.0.1"
  echo "SOLVER_PORT=8000"
} > "$ENV_FILE"

echo
echo "Wrote $ENV_FILE"
echo "Run ./start.sh to launch."
