# optimizers/steinerized_mst.py

from typing import Tuple

import networkx as nx

from .base_mini_grid_solver import BaseMiniGridSolver
from .registry import register_solver
from ..utils.models import SolverRequest


@register_solver
class SteinerizedMSTSolver(BaseMiniGridSolver):
    """
    Mini-grid power network optimizer using the Steinerized Minimum Spanning Tree heuristic.

    This solver provides a practical, fast approximation for laying out a mini-grid
    under a strict maximum edge length constraint (e.g., 30 meters per cable segment
    due to voltage drop, safety, or installation rules).

    Algorithm overview:
    1. Compute the Euclidean (haversine) Minimum Spanning Tree (MST) on the original
       set of points: 1 power source + N buildings/terminals.
    2. For every MST edge longer than max_edge_length, insert evenly spaced intermediate
       "pole" nodes along the great-circle path to ensure no single cable segment exceeds
       the allowed length.
    3. The resulting structure is a tree rooted at the power source, connecting all
       terminals with only short edges.

    Strengths:
    - Guarantees all edges ≤ max_edge_length
    - Fast (O(n² log n) worst-case, but practical for hundreds of points)
    - Simple to implement and debug
    - Provides a good baseline (often within 1.5–2× optimal number of extra poles in practice)

    Limitations:
    - Does not attempt to add "true" Steiner points at optimal 120° junctions
    - Pole placement is purely linear along MST edges (no merging or optimization)
    - Uses linear interpolation in lat/lon for intermediates (sufficient for short segments)

    Typical use case: Rural mini-grids where pole installation cost dominates and
    maximum span is constrained (e.g., 30 m due to low-voltage cable limits).
    """

    def __init__(self, request: SolverRequest, max_edge_length: float = 30.0):
        """
        Initialize the solver with the input request and edge length constraint.

        Args:
            request: SolverRequest containing points (lat/lng), solver, etc.
            max_edge_length: Maximum allowed length (meters) for any single cable segment.
                             Defaults to 30.0 meters.
        """
        super().__init__(request)
        self.max_edge_length = max_edge_length

    def _solve(self, input_tuple) -> nx.DiGraph:
        """
        Execute the full Steinerized MST algorithm and produce a SolverResult.

        Returns:
            graph, nodes, coords: The resulting graph structure,
                list of nodes (including any new poles),
                the actual coordinates themselves
        """
        # ─── 1. Parse input once and cache results ──────────────────────────────
        nodes, coords, source_idx, terminal_indices, names, costs = input_tuple

        # ─── 2. Compute full distance matrix using vectorized haversine ─────────
        # This avoids O(n²) scalar calls and is much faster for moderate n
        dist_matrix = self.compute_distance_matrix(coords)

        n = len(coords)

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
                cost = (costs.lowVoltageCostPerMeter
                            if self.request.params.get("voltage","low") == "low"
                        else costs.highVoltageCostPerMeter)
                weight = d * cost
                G.edges[i, j]["weight"] = weight
                G.edges[i, j]["length"] = d
                G.edges[i, j]["voltage"] = "low"
        mst = nx.minimum_spanning_tree(G, weight="weight")

        mst = self.split_long_edges_with_coords(mst)

        return mst
