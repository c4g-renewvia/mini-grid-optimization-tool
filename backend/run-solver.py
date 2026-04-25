"""Entry point for the bundled solver binary."""

import os
import tempfile

# Pin matplotlib's writable cache to a stable, OS-appropriate user dir so the
# font cache built on first launch persists across runs. Without this, the
# PyInstaller --onefile bundle's matplotlib hook points MPLCONFIGDIR at the
# bundle's temp extraction dir, which is purged when the process exits — so
# the 80s font-cache rebuild repeats on every launch. Direct assignment (not
# setdefault) is required to override the bundled hook's value.
#
# Must run before any matplotlib import, which happens transitively via
# server.py.
def _resolve_mpl_cache_dir() -> str:
    try:
        from platformdirs import user_data_dir

        path = os.path.join(user_data_dir("minigrid-solver"), "mpl")
        os.makedirs(path, exist_ok=True)
        # confirm writable
        probe = os.path.join(path, ".write-probe")
        with open(probe, "w") as f:
            f.write("")
        os.remove(probe)
        return path
    except Exception:
        fallback = os.path.join(tempfile.gettempdir(), "minigrid-solver", "mpl")
        os.makedirs(fallback, exist_ok=True)
        return fallback


os.environ["MPLCONFIGDIR"] = _resolve_mpl_cache_dir()

import uvicorn  # noqa: E402

from server import app  # noqa: E402


def main() -> None:
    host = os.environ.get("SOLVER_HOST", "0.0.0.0")
    port = int(os.environ.get("SOLVER_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
