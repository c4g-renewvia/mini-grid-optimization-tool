# src/solvers/simple_mst_solver.py
from typing import List, Union
import networkx as nx

from .base_mini_grid_solver import BaseMiniGridSolver
from ..utils.models import (Node, SolverInputParams, )
from ..utils.registry import register_solver


@register_solver
class SimpleMSTSolver(BaseMiniGridSolver):
    """
    Very simple MST solver that:

    - Uses **only the original points** (no candidate poles)
    - Computes an undirected MST on all points
    - Orients edges away from the source (makes it a tree rooted at source)
    - Assigns all connections as "low voltage" (can be changed later)
    - No fragmentation, no pruning, no extra poles

    Good as a baseline / lower bound reference.

    Args:
        steinerize
    """

    def __init__(self, request):
        super().__init__(request)
        self.steinerize = request.params.get("steinerize", False)

    @staticmethod
    def get_input_params():
        return [
            SolverInputParams(
                name="steinerize",
                type="bool",
                default="false",
                options=[True, False],
                description='Steinerize the graph edges',
            )
        ]

    def _solve(self) -> Union[nx.DiGraph, List[Node]]:

        if len(self._pole_indices) > 0:
            DG = self.build_graph_from_nodes(self._nodes, directed=True)
            arbo_graph = self._minimum_spanning_arborescence_w_attrs(DG)
            mst = self.prune_dead_end_pole_branches(arbo_graph)

        else:
            graph = self.build_graph_from_nodes(self._nodes, include_terminals=True, directed=False)
            mst = nx.minimum_spanning_tree(graph, weight="weight")

        if self.steinerize:
            mst = self.split_long_edges_with_coords(mst)

        return mst
