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

echo "Mini-Grid Optimization Tool — first-run setup"
echo
read -r -p "Enter your Google Maps API key: " MAPS_KEY
if [ -z "$MAPS_KEY" ]; then
  echo "Error: Google Maps API key is required." >&2
  exit 1
fi

mkdir -p "$DATA_DIR"
if [ ! -f "$DB_PATH" ]; then
  cp "$APP_DIR/prisma/offline.db" "$DB_PATH"
  echo "Initialized database at $DB_PATH"
else
  echo "Reusing existing database at $DB_PATH"
fi

AUTH_SECRET="$(openssl rand -base64 32)"

cat > "$ENV_FILE" <<EOF
OFFLINE_MODE=true
DATABASE_URL="file:$DB_PATH"
NEXTAUTH_URL=http://localhost:3000
AUTH_TRUST_HOST=true
AUTH_SECRET="$AUTH_SECRET"
GOOGLE_MAPS_API_KEY="$MAPS_KEY"
PORT=3000
HOSTNAME=127.0.0.1
SOLVER_HOST=127.0.0.1
SOLVER_PORT=8000
EOF

echo
echo "Wrote $ENV_FILE"
echo "Run ./start.sh to launch."
