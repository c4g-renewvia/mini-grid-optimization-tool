import logging
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import mini_grid_solver.solvers  # noqa: F401 - import for solver registration side effects
from mini_grid_solver.solvers.local_opt import LocalOptimization
from mini_grid_solver.utils.registry import SOLVER_REGISTRY
from mini_grid_solver.utils.models import SolverRequest, Solver, SolverResult

logger = logging.getLogger(__name__)

app = FastAPI(title="Mini Grid Optimization Tool")

# Allow frontend to call this (update for production domain)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "https://mini-grid-optimization-tool.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/solve", response_model=SolverResult)
async def solve(request: SolverRequest):
    """Solve a network layout using the requested registered solver.

    Args:
        request: Solver selection, nodes, costs, and length constraints.

    Returns:
        SolverResult: The computed network layout and cost estimates.

    Raises:
        HTTPException: With status 400 for fewer than two nodes, or status
            500 if solver lookup or execution fails.
    """
    if len(request.nodes) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 nodes")

    try:
        solver_class = SOLVER_REGISTRY[request.solver]

        logger.info(solver_class)

        result = solver_class(request).solve()

        return result
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/local_optimization", response_model=SolverResult)
def local_optimization(request: SolverRequest):
    """Refine an existing network layout with local optimization.

    Args:
        request: The layout, costs, and constraints to optimize.

    Returns:
        SolverResult: The optimized network layout and cost estimates.

    Raises:
        HTTPException: With status 500 if optimization fails.
    """
    try:
        result = LocalOptimization(request).solve()

        return result
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/solvers", response_model=List[Solver])
async def get_solvers() -> List[Solver]:
    """List registered solvers and their input parameter metadata.

    Returns:
        List[Solver]: Available solver names and parameter definitions.

    Raises:
        HTTPException: With status 500 if no solvers are registered.
    """
    # get solvers programmatically from import

    if len(SOLVER_REGISTRY) == 0 or SOLVER_REGISTRY is None:
        raise HTTPException(status_code=500, detail="No solvers available")

    solvers: List[Solver] = []
    for solver_name, solver_class in SOLVER_REGISTRY.items():
        params = solver_class.get_input_params()
        solvers.append(Solver(name=str(solver_name), params=params))

    return solvers
