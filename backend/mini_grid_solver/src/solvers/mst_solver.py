# src/solvers/simple_mst_solver.py
from typing import List, Tuple

import networkx as nx

from .base_mini_grid_solver import BaseMiniGridSolver
from .registry import register_solver
from ..utils.models import (
    Node, SolverInputParams,
)


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

    def _solve(self) -> Tuple[nx.DiGraph, List[Node]]:

        n = len(self._coords)
        if n < 2:
            raise ValueError("Need at least source + 1 terminal")

        # 3. Compute full distance matrix
        dist_matrix = self.compute_distance_matrix(self._coords)

        pole_indices = [n.index for n in self._nodes if n.type == "pole"]

        if len(pole_indices) > 0:

            DG = self.build_directed_graph_for_arborescence(self._nodes)

            arbo_graph = self._minimum_spanning_arborescence_w_attrs(DG)
            mst = self.prune_dead_end_pole_branches(arbo_graph)

        else:
            G = nx.complete_graph(n)
            for node in self._nodes:
                G.nodes[node.index]["name"] = node.name
                G.nodes[node.index]["type"] = node.type
                G.nodes[node.index]["lat"] = node.lat
                G.nodes[node.index]["lng"] = node.lng
                G.nodes[node.index]["used"] = node.used
            for i in range(n):
                for j in range(i + 1, n):
                    d = dist_matrix[i, j]
                    cost = (self._costs.lowVoltageCostPerMeter
                            if self.request.params.get("voltage","low") == "low"
                            else self._costs.highVoltageCostPerMeter)

                    weight = d * cost
                    G.edges[i, j]["weight"] = weight
                    G.edges[i, j]["length"] = d
                    G.edges[i, j]["voltage"] = "low"
            mst = nx.minimum_spanning_tree(G, weight="weight")

        if self.steinerize:
            mst = self.split_long_edges_with_coords(mst)

        return mst
