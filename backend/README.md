# Mini-Grid Optimization Tool - Backend

This project provides a comprehensive framework for designing and optimizing rural power distribution networks. It focuses on minimizing total project costs by balancing wire lengths and pole placements while adhering to strict geographical and physical constraints.

## Overview

The Mini-Grid Solver is a Python-based optimization engine that uses various algorithms (from simple MST to advanced Steiner Tree heuristics) to design efficient micro-grid topologies. It provides a REST API built with FastAPI to interact with frontend applications.

## Stack & Technologies

- **Language:** Python >= 3.13
- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) for the REST API
- **Data Validation:** [Pydantic](https://docs.pydantic.dev/)
- **Optimization & Graph Libraries:**
  - [NumPy](https://numpy.org/) & [SciPy](https://scipy.org/): Vectorized calculations and spatial optimization.
  - [NetworkX](https://networkx.org/): Graph theory algorithms.
  - [Shapely](https://shapely.readthedocs.io/): Geometric operations.
  - [scikit-learn](https://scikit-learn.org/): Clustering and candidate generation.
- **Visualization:** [Matplotlib](https://matplotlib.org/) (mainly for debugging and local analysis).
- **Package Manager:** [uv](https://github.com/astral-sh/uv)

## Project Structure

```text
backend/
├── mini_grid_solver/
│   ├── src/
│   │   ├── solvers/
│   │   │   ├── base_mini_grid_solver.py    # Abstract base class for all solvers
│   │   │   ├── candidate_generation.py     # Base for solvers needing pole candidates
│   │   │   ├── disk_based_steiner_solver.py # Advanced disk-covering Steiner heuristic
│   │   │   ├── greedy_iter_steiner_solver.py # Iterative Steiner Tree refinement
│   │   │   ├── local_opt.py                # Local search / Gradient descent optimization
│   │   │   ├── mst_solver.py               # Simple MST baseline solver
│   │   │   └── registry.py                 # Solver registration utility
│   │   └── utils/
│   │       └── models.py                   # Pydantic data models (Request/Response)
│   ├── tests/                              # Pytest suite
│       ├── solvers/                        # Unit and integration tests for solvers
│       └── test_data_sets/                 # KML and CSV data for testing
    └── pyproject.toml                          # Project metadata and dependencies
├── Dockerfile                              # Multi-stage build using uv

├── server.py                               # FastAPI entry point
└── uv.lock                                 # Lockfile for reproducible environments
```

## Setup & Run

### Prerequisites

- [uv](https://github.com/astral-sh/uv) installed on your system.
- Python 3.13 (uv can manage this for you).

### Installation

```bash
# Clone the repository and navigate to the backend directory
cd backend

# Install dependencies and create a virtual environment
uv sync
```

### Running the Server

```bash
# Using uv to run the server with uvicorn
uv run uvicorn server:app --reload
```

The API will be available at `http://localhost:8000`. You can access the interactive documentation at `http://localhost:8000/docs`.

### Running with Docker

```bash
docker build -t mini-grid-backend .
docker run -p 8000:8000 mini-grid-backend
```

## Scripts

- **`uv run uvicorn server:app`**: Starts the FastAPI development server.
- **`pytest`**: Runs the test suite.

## Environment Variables

Currently, the application uses default configurations. TODO: Add documentation for any upcoming environment variables (e.g., `DATABASE_URL`, `CORS_ORIGINS`).

## API Endpoints

- `POST /solve`: Computes a solution using a specified solver.
- `POST /local_optimization`: Applies local search optimization to an existing layout.
- `GET /solvers`: Returns a list of available solvers and their parameters.

## Tests

The project uses `pytest` for testing. Tests include validation against ground truth data from KML files.

```bash
# Run all tests
uv run pytest

# Run specific solver tests
uv run pytest mini_grid_solver/tests/solvers/test_solvers.py
```

## Solvers

| Solver | Description |
| :--- | :--- |
| **`SimpleMSTSolver`** | Computes a standard Minimum Spanning Tree; used as a baseline. |
| **`GreedyIterSteinerSolver`** | Iteratively adds candidate poles to reduce total cost. |
| **`DiskBasedSteinerSolver`** | Uses a minimum disk cover approach to group terminals before Steiner optimization. |
| **`LocalOptimization`** | Refines existing topologies using gradient-descent-like local moves. |

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Future Development (TODO)

- [ ] Add High Voltage (HV) distribution support.
- [ ] Implement Genetic Algorithms for global optimization.
- [ ] Add support for voltage drop constraints in costing.
- [ ] Integrate with external GIS data providers.
