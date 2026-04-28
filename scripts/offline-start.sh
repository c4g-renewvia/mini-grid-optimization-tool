#!/usr/bin/env bash
# Launcher for the offline distribution. Spawns the solver binary (port 8000)
# and the Next.js standalone server (port 3000), opens the user's browser,
# and waits for either to exit. Forwards signals to children on Ctrl+C.
set -euo pipefail

cd "$(dirname "$0")"
APP_DIR="$(pwd)"

if [ ! -f "$APP_DIR/.env" ]; then
  echo "Missing $APP_DIR/.env. Run ./setup.sh first." >&2
  exit 1
fi

case "$(uname -s)" in
  Darwin) LOG_DIR="$HOME/Library/Logs/minigrid-solver" ;;
  Linux)  LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/minigrid-solver/logs" ;;
  *)
    echo "Error: unsupported platform $(uname -s). Layer 2 supports macOS and Linux." >&2
    exit 1
    ;;
esac
mkdir -p "$LOG_DIR"

set -a
# shellcheck disable=SC1091
source "$APP_DIR/.env"
set +a

cleanup() {
  if [ -n "${SOLVER_PID:-}" ]; then kill "$SOLVER_PID" 2>/dev/null || true; fi
  if [ -n "${NEXT_PID:-}" ];   then kill "$NEXT_PID"   2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

echo "Starting solver on :8000..."
"$APP_DIR/solver/minigrid-solver" >"$LOG_DIR/solver.log" 2>&1 &
SOLVER_PID=$!

echo "Starting web server on :3000..."
node "$APP_DIR/server/server.js" >"$LOG_DIR/server.log" 2>&1 &
NEXT_PID=$!

# Wait for the web server to come up before opening the browser.
for _ in $(seq 1 30); do
  if curl -sf -o /dev/null http://localhost:3000/api/health 2>/dev/null; then
    break
  fi
  sleep 1
done

URL="http://localhost:3000"
echo "Opening $URL..."
case "$(uname)" in
  Darwin) open "$URL" ;;
  Linux)  xdg-open "$URL" >/dev/null 2>&1 || true ;;
esac

echo
echo "Logs:  $LOG_DIR/solver.log   $LOG_DIR/server.log"
echo "Press Ctrl+C to stop."

# Wait for either child to exit, then trigger cleanup. `wait -n` is bash 4.3+;
# macOS ships bash 3.2, so we fall back to a polling loop that exits as soon
# as one of the two PIDs disappears.
while kill -0 "$SOLVER_PID" 2>/dev/null && kill -0 "$NEXT_PID" 2>/dev/null; do
  sleep 1
done
