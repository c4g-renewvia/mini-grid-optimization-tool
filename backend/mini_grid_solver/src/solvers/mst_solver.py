# src/solvers/simple_mst_solver.py
from typing import List, Tuple

import networkx as nx

from .base_mini_grid_solver import BaseMiniGridSolver
from .registry import register_solver
from ..utils.models import (
    Node,
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

    Args: voltage: High or low voltage MST?
    """


    def _solve(self, input_tuple) -> Tuple[nx.DiGraph, List[Node]]:

        nodes, coords, source_idx, terminal_indices, names, costs = input_tuple

        n = len(coords)
        if n < 2:
            raise ValueError("Need at least source + 1 terminal")

        # 3. Compute full distance matrix
        dist_matrix = self.compute_distance_matrix(coords)

        pole_indices = [n.index for n in nodes if n.type == "pole"]

        if len(pole_indices) > 0:

            DG = self.build_directed_graph_for_arborescence(nodes)

            arbo_graph = self._minimum_spanning_arborescence_w_attrs(DG)
            mst = self.prune_dead_end_pole_branches(arbo_graph)

        else:
            G = nx.complete_graph(n)
            for node in nodes:
                G.nodes[node.index]["name"] = node.name
                G.nodes[node.index]["type"] = node.type
                G.nodes[node.index]["lat"] = node.lat
                G.nodes[node.index]["lng"] = node.lng
                G.nodes[node.index]["used"] = node.used
            for i in range(n):
                for j in range(i + 1, n):
                    d = dist_matrix[i, j]
                    cost = costs.lowVoltageCostPerMeter if self.request.params.get("voltage", "low") == "low" else costs.highVoltageCostPerMeter
                    weight = d * cost
                    G.edges[i, j]["weight"] = weight
                    G.edges[i, j]["length"] = d
                    G.edges[i, j]["voltage"] = "low"
            mst = nx.minimum_spanning_tree(G, weight="weight")

        return mst
