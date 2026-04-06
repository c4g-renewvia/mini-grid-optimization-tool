from .base_mini_grid_solver import BaseMiniGridSolver
from typing import Dict, Type
SOLVER_REGISTRY: Dict[str, Type["BaseMiniGridSolver"]] = {}

def register_solver(cls: Type["BaseMiniGridSolver"]):
    SOLVER_REGISTRY[cls.__name__] = cls
    return cls