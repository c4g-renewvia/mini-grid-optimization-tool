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

        dist_matrix = self.compute_distance_matrix(self._coords)

        if len(self._pole_indices) > 0:
            DG = self.build_directed_graph_for_arborescence(self._nodes)
            arbo_graph = self._minimum_spanning_arborescence_w_attrs(DG)
            mst = self.prune_dead_end_pole_branches(arbo_graph)

        else:
            n = len(self._nodes)
            G = nx.Graph()
            for node in self._nodes:
                G.add_node(node.index)
                G.nodes[node.index]["name"] = node.name
                G.nodes[node.index]["type"] = node.type
                G.nodes[node.index]["lat"] = node.lat
                G.nodes[node.index]["lng"] = node.lng
            for i in G.nodes:
                for j in G.nodes:
                    G.add_edge(i, j)
                    d = dist_matrix[i, j]
                    cost = self.get_cost_per_meter()

                    weight = d * cost
                    G.edges[i, j]["weight"] = weight
                    G.edges[i, j]["length"] = d
                    G.edges[i, j]["voltage"] = self.request.voltageLevel
            mst = nx.minimum_spanning_tree(G, weight="weight")

        if self.steinerize:
            mst = self.split_long_edges_with_coords(mst)

        return mst
