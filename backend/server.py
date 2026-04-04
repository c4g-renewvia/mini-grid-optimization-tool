import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from mini_grid_solver.src.solvers.registry import SOLVER_REGISTRY  # or wherever
from mini_grid_solver.src.utils.models import SolverRequest, Solver

logger = logging.getLogger(__name__)

app = FastAPI(title="Renewvia MST Solver")

# Allow frontend to call this (update for production domain)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "https://c4g-renewvia.vercel.app",
        "https://mini-grid-optimization-tool.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/solve")
async def solve(request: SolverRequest):
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


@app.get("/solvers")
async def get_solvers() -> dict:
    # get solvers programatically from import

    if len(SOLVER_REGISTRY) == 0 or SOLVER_REGISTRY is None:
        raise HTTPException(status_code=500, detail="No solvers available")

    solvers = {"solvers": []}
    for solver_name, solver_class in SOLVER_REGISTRY.items():
        params = solver_class.get_input_params()
        solvers['solvers'].append(Solver(name = str(solver_name), params = params))

    return solvers
