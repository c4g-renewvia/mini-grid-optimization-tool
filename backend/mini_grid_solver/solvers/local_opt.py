# src/solvers/simple_mst_solver.py
from typing import List, Union

import networkx as nx

from ..utils.models import Node
from .base_mini_grid_solver import BaseMiniGridSolver


class LocalOptimization(BaseMiniGridSolver):
    """
    Implements a solver for local optimization problems.

    This class is designed to perform local optimization on a given graph
    structure. It utilizes specific algorithms to process and manipulate
    the graph in order to achieve an optimized solution. The primary use
    case involves complex scenarios where local adjustments to a graph
    improve the overall solution quality.

    """

    def _solve(self) -> Union[nx.DiGraph, List[Node]]:
        graph = self.build_graph_from_nodes(self._nodes, self._edges, directed=True)

        final_graph = self._post_solver_local_opt(graph)

        return final_graph
