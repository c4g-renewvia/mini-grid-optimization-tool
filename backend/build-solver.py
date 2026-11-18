"""Build a single-file PyInstaller binary for the FastAPI solver."""

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIST = HERE / "dist"
BUILD = HERE / "build"
SPEC = HERE / "minigrid-solver.spec"


def main() -> int:
    """Clean previous build artifacts and bundle the solver with PyInstaller.

    Returns:
        int: The PyInstaller exit code on failure, or zero on success.

    Raises:
        OSError: If build artifacts cannot be removed or the process cannot start.
    """
    if DIST.exists():
        shutil.rmtree(DIST)
    if BUILD.exists():
        shutil.rmtree(BUILD)
    if SPEC.exists():
        SPEC.unlink()

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        "minigrid-solver",
        "--collect-all",
        "mini_grid_solver",
        "--collect-submodules",
        "uvicorn",
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        "--hidden-import",
        "uvicorn.lifespan.on",
        "--hidden-import",
        "platformdirs",
        "--exclude-module",
        "tkinter",
        str(HERE / "run-solver.py"),
    ]

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=HERE)
    if result.returncode != 0:
        return result.returncode

    binary = DIST / "minigrid-solver"
    if binary.exists():
        print(f"Built: {binary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
