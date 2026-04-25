"""Entry point for the bundled solver binary."""

import os

import uvicorn

from server import app


def main() -> None:
    host = os.environ.get("SOLVER_HOST", "0.0.0.0")
    port = int(os.environ.get("SOLVER_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
