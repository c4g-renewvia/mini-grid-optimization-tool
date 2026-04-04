# # backend/mst.py

import numpy as np
from scipy.spatial import Delaunay

from .base_mini_grid_solver import *
from ..utils.models import *


class CandidateMSTSolver(BaseMiniGridSolver):
    """
    Re-implementation of your original MST + Fermat candidates + pruning + fragmentation logic.
    Exists mainly as reference / regression test baseline.
    """

    def __init__(self, request: SolverRequest):
        """

        Args:
            - request: SolverRequest object containing all necessary parameters.
            - candidate_algorithm: specifying the algorithm to use for generating candidates.
                `fermat` for Fermat-Torricelli points - can be extended.
        """
        super().__init__(request)
        self.candidate_algorithm = request.params.get("candidate_algorithm", "fermat")

    def generate_collinear_candidates(
            self,
            coords,  # usually np.ndarray (n, 2)
            current_tree_edges,
            max_length: float = 30.0,
            num_per_edge: int = 3
    ) -> np.ndarray:
        """
        Generate ~num_per_edge intermediate candidates per long edge.
        """
        candidates = []

        for u, v in current_tree_edges:
            p1 = coords[u]  # [lat, lon]
            p2 = coords[v]
            d = self.haversine_meters(p1[0], p1[1], p2[0], p2[1])

            if d <= max_length:
                continue

            # We want ~ num_per_edge intermediate points
            # → number of segments = num_per_edge + 1
            n_segments_desired = num_per_edge + 1
            segment_length = d / n_segments_desired

            # But never make segments shorter than, say, 5–10 m
            # segment_length = max(segment_length, 8.0)  # adjust as needed

            intermediates = self._great_circle_intermediates(
                p1[0], p1[1],
                p2[0], p2[1],
                max_length=segment_length  # ← this is the key fix
            )

            # intermediates includes start + end → take only the middle ones
            for pt in intermediates[1:-1]:
                candidates.append(np.array(pt))

        if not candidates:
            return np.empty((0, 2), dtype=float)

        candidates_array = np.array(candidates)
        # Remove near-duplicates (floating point)
        return np.unique(np.round(candidates_array, decimals=6), axis=0)

    def fermat_torricelli_point(self, pts: np.ndarray) -> np.ndarray:
        """
        Compute approximate Fermat-Torricelli point for a triangle (3 points).
        If any angle ≥ 120°, returns the vertex with that angle.
        Otherwise returns a rough approximation (centroid fallback for simplicity).
        """
        if len(pts) != 3:
            raise ValueError("Need exactly 3 points")

        A, B, C = pts

        # Compute side lengths
        a = np.linalg.norm(B - C)
        b = np.linalg.norm(A - C)
        c = np.linalg.norm(A - B)

        # Cosines of angles
        cosA = (b ** 2 + c ** 2 - a ** 2) / (2 * b * c) if b * c != 0 else 1
        cosB = (a ** 2 + c ** 2 - b ** 2) / (2 * a * c) if a * c != 0 else 1
        cosC = (a ** 2 + b ** 2 - c ** 2) / (2 * a * b) if a * b != 0 else 1

        # If any angle ≥ 120° (cos ≤ -0.5), minimum is at that vertex
        if cosA <= -0.5:
            return A
        if cosB <= -0.5:
            return B
        if cosC <= -0.5:
            return C

        # Otherwise: simple centroid approximation (good enough for our purpose)
        # (Real 120° construction is more involved — this is fast & reasonable)
        return np.mean(pts, axis=0)

    def generate_fermat_candidates(self, coords: np.ndarray, max_candidates: int = 30) -> np.ndarray:
        """
        Generate candidate pole markers using approximate Fermat-Torricelli points
        from Delaunay triangles.

        Args:
            coords: (n, 2) array of terminal points [lat, lon]
            max_candidates: limit number of generated points (avoid too many)

        Returns:
            np.ndarray: candidate points (m, 2)
        """
        if len(coords) < 3:
            return np.empty((0, 2), dtype=float)

        # Compute Delaunay triangulation
        tri = Delaunay(coords)

        candidates = []

        for simplex in tri.simplices:
            if len(candidates) >= max_candidates:
                break
            pts = coords[simplex]
            # Get approximate Steiner/Fermat point for this triangle
            st_pt = self.fermat_torricelli_point(pts)
            candidates.append(st_pt)

        if not candidates:
            return np.empty((0, 2), dtype=float)

        candidates = np.array(candidates)

        # mask candidates too close to terminals
        mask = (CandidateMSTSolver.haversine_vec(candidates, coords) >= MIN_DIST_TO_TERMINAL).prod(axis=1)

        candidates = candidates[mask]

        print(f"Generated {len(candidates)} Fermat-Steiner candidate poles "
              f"(limited to {max_candidates}, after min separation filter)")

        return candidates

    def _solve(self, input_tuple) -> Union[nx.Graph, nx.DiGraph]:
        """
        Solves the problem by processing candidate points, building a graph, and computing a
        minimum spanning arborescence (MST) before postprocessing the result.

        Args:
            input_tuple: A tuple containing the parsed input data


        Returns:
            SolverResult: The result containing details such as edges, node information,
            and computed metrics including lengths and count of used poles.

        Raises:
            ValueError: If an unsupported candidate algorithm is specified.
        """
        nodes, coords, source_idx, terminal_indices, names, costs = input_tuple

        if self.candidate_algorithm == 'fermat':
            candidates = self.generate_fermat_candidates(coords, max_candidates=100)
        else:
            raise ValueError(f"Unsupported candidate algorithm: {self.candidate_algorithm}")

        # 4. Graph + arborescence
        nodes = self._build_nodes(coords, candidates, names)

        DG = self.build_directed_graph_for_arborescence(nodes)

        arbo_graph = self._minimum_spanning_arborescence_w_attrs(DG)

        # 5. Prune
        mst = self.prune_dead_end_pole_branches(arbo_graph)

        # 6. break long line segments
        mst = self.split_long_edges_with_coords(graph=mst)

        return mst
