#!/usr/bin/env bash
# Build the standalone solver binary using PyInstaller via uv.
set -euo pipefail
cd "$(dirname "$0")"

# Use uv to run inside the project's virtual environment, installing pyinstaller as needed.
uv run --with pyinstaller python build-solver.py

echo "Binary: $(pwd)/dist/minigrid-solver"
