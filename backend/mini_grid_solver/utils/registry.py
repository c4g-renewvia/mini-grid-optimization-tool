"""Map registered solver names to their implementation classes."""

from typing import Dict, Type

from ..solvers.base_mini_grid_solver import BaseMiniGridSolver

SOLVER_REGISTRY: Dict[str, Type["BaseMiniGridSolver"]] = {}


def register_solver(cls: Type["BaseMiniGridSolver"]):
    """Register a solver class under its class name.

    Args:
        cls: The solver class to register.

    Returns:
        Type[BaseMiniGridSolver]: The unchanged class, for use as a decorator.
    """
    SOLVER_REGISTRY[cls.__name__] = cls
    return cls