from .base_mini_grid_solver import BaseMiniGridSolver
SOLVER_REGISTRY: dict[str, type["BaseMiniGridSolver"]] = {}

def register_solver(cls: type["BaseMiniGridSolver"]):
    SOLVER_REGISTRY[cls.__name__] = cls
    return cls