# src/solvers/simple_mst_solver.py
from typing import List, Tuple

import networkx as nx

from .base_mini_grid_solver import BaseMiniGridSolver
from .registry import register_solver
from ..utils.models import (
    Node, SolverInputParams,
)


# @register_solver
class LocalOptimization(BaseMiniGridSolver):
    
    def _solve(self) -> Tuple[nx.DiGraph, List[Node]]:

        return
