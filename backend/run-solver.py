"""Entry point for the bundled solver binary."""

import os

# Pin matplotlib's cache to a stable user dir so the font cache built on first
# launch persists across runs. Without this, PyInstaller --onefile rebuilds the
# cache every launch (60-90s) because the bundle's temp dir is purged on exit.
# Must be set before any matplotlib import (which happens transitively via server.py).
os.environ.setdefault(
    "MPLCONFIGDIR", os.path.expanduser("~/.cache/minigrid-solver/mpl")
)
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import uvicorn  # noqa: E402

from server import app  # noqa: E402


def main() -> None:
    host = os.environ.get("SOLVER_HOST", "0.0.0.0")
    port = int(os.environ.get("SOLVER_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
