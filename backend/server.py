import logging
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from mini_grid_solver.src.solvers.registry import SOLVER_REGISTRY  # or wherever
from mini_grid_solver.src.utils.models import SolverRequest, Solver

logger = logging.getLogger(__name__)

app = FastAPI(title="Mini Grid Optimization Tool")

# Allow frontend to call this (update for production domain)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "https://c4g-renewvia.vercel.app",
        "https://mini-grid-optimization-tool.vercel.app",
        "https://mini-grid-tool.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/solve")
async def solve(request: SolverRequest):
    """
    Handles the POST request to solve a problem using a specified solver and data input.

    This endpoint receives a request payload containing the solver to be
    used and the required data points. It checks the validity of the
    input and computes the solution using the selected solver.

    Raises:
        HTTPException: If the number of provided points is less than 2,
        a 400 error is raised. If any exception occurs during processing,
        a 500 error is raised with the exception details.

    Arguments:
        request (SolverRequest): The request data containing solver information
        and input points.

    Returns:
        dict: The result of the computation from the selected solver.
    """
    if len(request.points) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 points")

    try:
        solver_class = SOLVER_REGISTRY[request.solver]

        logger.info(solver_class)

        result = solver_class(request).solve()

        return result
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/solvers", response_model=List[Solver])
async def get_solvers() -> List[Solver]:
    """
    Handles the retrieval of available solvers and their input parameters.

    The endpoint fetches solvers programmatically from the SOLVER_REGISTRY
    and returns a dictionary containing the list of solvers and their respective
    input parameters. If no solvers are available, an HTTPException is raised
    indicating an internal server error.

    Raises:
        HTTPException: If there are no registered solvers in the SOLVER_REGISTRY.

    Returns:
        dict: A dictionary containing a list of solvers with their input parameters.
    """
    # get solvers programmatically from import

    if len(SOLVER_REGISTRY) == 0 or SOLVER_REGISTRY is None:
        raise HTTPException(status_code=500, detail="No solvers available")

    solvers: List[Solver] = []
    for solver_name, solver_class in SOLVER_REGISTRY.items():
        params = solver_class.get_input_params()
        solvers.append(Solver(name = str(solver_name), params = params))

    return solvers
