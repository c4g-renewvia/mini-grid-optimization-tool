import itertools
from typing import Tuple, List

import networkx as nx
import numpy as np
from matplotlib import pyplot as plt
from scipy.spatial import Delaunay
from sklearn.cluster import KMeans

from .base_mini_grid_solver import BaseMiniGridSolver
from .registry import register_solver
from ..utils.models import SolverRequest, Node


@register_solver
class GreedyIterSteinerSolver(BaseMiniGridSolver):
    """
    Solver implementation using a greedy approach for refining the Minimum Spanning Tree (MST)
    based on Steiner points.

    This class provides mechanisms for solving tree optimization problems using Steiner
    points, by identifying and adding projection, cluster center, and Fermat point
    candidates.

    Attributes:
         None
    """

    def __init__(self, request: SolverRequest):
        super().__init__(request)
        self._delaunay_cache = None  # scipy.spatial.Delaunay object
        self._cached_coords = None  # the coords used to build the cache

    @staticmethod
    def get_input_params():
        return []

    @staticmethod
    def fermat_torricelli_point(pts: np.ndarray) -> np.ndarray:
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

    def _get_delaunay(self, coords: np.ndarray) -> Delaunay:
        """
        Returns a Delaunay triangulation, rebuilding only when the point set changed significantly.
        """
        if (self._delaunay_cache is None or
                self._cached_coords is None or
                len(coords) != len(self._cached_coords) or
                np.max(np.abs(coords - self._cached_coords)) > 1e-6):  # points actually changed

            if self.request.debug >= 1:
                print(f"Rebuilding Delaunay triangulation for {len(coords)} points")

            self._delaunay_cache = Delaunay(coords)
            self._cached_coords = coords.copy()

        return self._delaunay_cache

    def _compute_coords_hash(self, coords: np.ndarray) -> str:
        """Create a simple hash to detect if coordinates have changed."""
        # Round to 6 decimals (meter-level precision) and hash
        rounded = np.round(coords, decimals=6)
        return str(rounded.tobytes())

    def _get_distance_matrix(self, coords: np.ndarray) -> np.ndarray:
        """
        Returns the distance matrix for current coordinates.
        Recomputes only when points have actually changed.
        """
        if coords is None or len(coords) == 0:
            return np.zeros((0, 0))

        current_hash = self._compute_coords_hash(coords)

        # Recompute only if cache is missing or points changed
        if (self._dist_matrix is None or
                self._cached_coords_hash != current_hash or
                self._dist_matrix.shape[0] != len(coords)):

            if self.request.debug >= 1:
                print(f"Recomputing distance matrix for {len(coords)} points")

            self._dist_matrix = self.haversine_vec(coords, coords)  # vectorized, fast
            self._cached_coords_hash = current_hash

        return self._dist_matrix

    def generate_projection_candidates(
            self,
            coords_array,
            edge_list,
            terminal_indices,
            max_dist_to_line=40.0,
            min_dist_to_existing=5.0
    ):
        """

        Args:
            coords_array:  np.array (n_total, 2) current points [lat, lng]
            edge_list:  list of (u_idx, v_idx) from current tree
            terminal_indices: original terminal indices (fixed)
            max_dist_to_line: meters — how close a terminal must be to the line
            min_dist_to_existing: avoid adding very close to existing points

        Returns:

        """
        candidates = []

        def point_to_segment_distance_and_projection(p, a, b):
            """Return distance from point p to segment [a,b] and closest point on segment."""
            # Vector math (all in lat/lng — approximate for small areas)
            ab = b - a
            ap = p - a
            proj = np.dot(ap, ab) / np.dot(ab, ab)
            proj = np.clip(proj, 0.0, 1.0)
            closest = a + proj * ab

            dist_to_closest = self.haversine_meters(p[0], p[1], closest[0], closest[1])
            return dist_to_closest, closest

        for u, v in edge_list:
            a = coords_array[u]
            b = coords_array[v]

            for h_idx in terminal_indices:
                h = coords_array[h_idx]
                dist, proj_point = point_to_segment_distance_and_projection(h, a, b)

                if dist <= max_dist_to_line:
                    # Check not too close to existing points
                    dists_to_existing = np.min(
                        self.haversine_vec(np.array([proj_point]), coords_array)
                    )
                    if dists_to_existing >= min_dist_to_existing:
                        candidates.append(proj_point)

        if not candidates:
            return np.array([])

        projs = np.array(candidates)
        projs = np.unique(np.round(projs, decimals=6), axis=0)  # dedup

        return projs

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
                max_length=segment_length
            )

            # intermediates includes start + end → take only the middle ones
            for pt in intermediates[1:-1]:
                candidates.append(np.array(pt))

        if not candidates:
            return np.empty((0, 2), dtype=float)

        candidates_array = np.array(candidates)
        # Remove near-duplicates (floating point)
        return np.unique(np.round(candidates_array, decimals=6), axis=0)

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
        tri = self._get_delaunay(coords)

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
        mask = (self.haversine_vec(candidates,
                                   coords) >= self.request.lengthConstraints.low.poleToTerminalMinimumLength).prod(
            axis=1)

        candidates = candidates[mask]

        if self.request.debug >= 1:
            print(f"Generated {len(candidates)} Fermat-Steiner candidate poles "
                  f"(limited to {max_candidates}, after min separation filter)")

        return candidates

    @staticmethod
    def generate_cluster_center_candidates(coords, n_init=10):
        """
        Generate candidate pole markers as centers of K-Means clusters.

        - Tries multiple k values and takes all unique centers
        - Filters very small clusters (e.g. < 3 points)
        """
        if len(coords) < 6:
            return np.array([])  # too few points → no meaningful clusters

        candidates = []
        coords_array = np.array(coords)  # shape (n, 2) [lat, lng] or [lng, lat]

        for k in range(len(coords) // 2, len(coords) // 2 + 2):
            try:
                kmeans = KMeans(n_clusters=k, n_init=n_init, random_state=42)
                kmeans.fit(coords_array)
                centers = kmeans.cluster_centers_

                # Optional: only keep centers of clusters with >= min_points
                labels, counts = np.unique(kmeans.labels_, return_counts=True)
                valid_centers = centers[counts >= 2]  # at least  points per cluster

                candidates.extend(valid_centers)
            except Exception as e:
                print(f"K-Means k={k} failed: {e}")
                continue

        if not candidates:
            return np.array([])

        cluster_centers = np.array(candidates)

        # Deduplicate (very close centers from different k)
        cluster_centers = np.unique(np.round(cluster_centers, decimals=6), axis=0)

        return cluster_centers

    def generate_adaptive_fermat_candidates(
            self,
            current_coords: np.ndarray,
            terminal_indices: List[int],
            pole_indices: List[int],
            max_distance: float = 60.0
    ) -> np.ndarray:
        """
        Generates Fermat points for triplets consisting of:
        - 1 existing pole + 2 terminals
        - 2 existing poles + 1 terminal
        """
        candidates = []

        # Iterate through each existing pole to see if it can 'bridge' nearby terminals
        for p_idx in pole_indices:
            pole_coord = current_coords[p_idx]

            # Find terminals within reach of this specific pole
            nearby_terminals = [
                t_idx for t_idx in terminal_indices
                if self.haversine_meters(pole_coord[0], pole_coord[1],
                                         current_coords[t_idx][0], current_coords[t_idx][1]) <= max_distance
            ]

            # If we have at least 2 nearby terminals, try forming a Steiner junction
            if len(nearby_terminals) >= 2:
                for i, j in itertools.combinations(nearby_terminals, 2):
                    pts = np.array([
                        pole_coord,
                        current_coords[i],
                        current_coords[j]
                    ])

                    st_pt = self.fermat_torricelli_point(pts)
                    candidates.append(st_pt)

        if not candidates:
            return np.empty((0, 2))

        # Filter by minimum separation from existing points to avoid redundancy
        candidates_array = np.array(candidates)
        mask = (self.haversine_vec(candidates_array, current_coords) >= 10.0).all(axis=1)

        return np.unique(np.round(candidates_array[mask], decimals=6), axis=0)

    def generate_proximity_fermat_candidates(
            self,
            coords: np.ndarray,
            max_distance: float = 50.0,
            max_candidates: int = 100,
    ) -> np.ndarray:
        """
        Generate candidate pole markers using approximate Fermat-Torricelli points
        for ANY triplet of nodes where all three nodes are within `max_distance` of each other.
        """
        n = len(coords)
        if n < 3:
            return np.empty((0, 2), dtype=float)

        # 1. Precompute a localized distance matrix for the coordinates
        dist_matrix = self._get_distance_matrix(coords)

        candidates = []

        # 2. Find all valid triplets (i, j, k) where all pairwise distances are <= max_distance
        # We use strict combinations (i < j < k) to avoid permutations of the same triangle
        for i in range(n):
            for j in range(i + 1, n):
                if dist_matrix[i, j] > max_distance:
                    continue  # Skip early if i and j are already too far apart

                for k in range(j + 1, n):
                    # Check if k is close to BOTH i and j
                    if dist_matrix[i, k] <= max_distance and dist_matrix[j, k] <= max_distance:
                        pts = np.array([coords[i], coords[j], coords[k]])

                        # Use your existing fermat calculation
                        st_pt = self.fermat_torricelli_point(pts)
                        candidates.append(st_pt)

                        if len(candidates) >= max_candidates:
                            break
                if len(candidates) >= max_candidates:
                    break
            if len(candidates) >= max_candidates:
                break

        if not candidates:
            return np.empty((0, 2), dtype=float)

        candidates = np.array(candidates)

        # 3. Filter candidates that are too close to existing terminals
        # (Enforcing MIN_DIST_TO_TERMINAL, assuming it's 10.0m)
        valid_candidates = []
        for cand in candidates:
            # Check the minimum distance to any original coordinate
            min_d = min(self.haversine_meters(cand[0], cand[1], c[0], c[1]) for c in coords)
            if min_d >= 10.0:
                valid_candidates.append(cand)

        candidates = np.array(valid_candidates)

        # 4. Deduplicate close overlapping candidates
        if len(candidates) > 0:
            candidates = np.unique(np.round(candidates, decimals=6), axis=0)
        else:
            candidates = np.empty((0, 2), dtype=float)

        if self.request.debug >= 1:
            print(f"Generated {len(candidates)} Fermat-Steiner candidates from proximity triplets "
                  f"(max_dist={max_distance}m)")

        return candidates

    def generate_candidates(self,
                            coords,
                            cur_edges,
                            terminal_cluster_centers,
                            added_candidates,
                            num_per_edge=2):
        """
        Generates a pool of candidate points for network optimization based on various methods.

        This method synthesizes several types of candidates, including Fermat points, adaptive Fermat
        points, collinear points, and projection candidates. The method also filters candidates based
        on constraints such as bounding boxes of terminal nodes and removes already added candidates.

        Parameters:
            coords (list): A list of [latitude, longitude] coordinates representing existing points.
            cur_edges (list): A list of current edges represented by indices of the coordinates.
            terminal_cluster_centers (numpy.ndarray): Array of cluster centers derived from terminal nodes.
            added_candidates (list): A list of candidates already added, each as a [latitude, longitude] pair.
            num_per_edge (int, optional): Number of candidates to generate per edge. Default is 2.

        Returns:
            numpy.ndarray: A 2D array where each row represents a generated candidate point as
                           [latitude, longitude].

        Raises:
            None
        """

        # remove candidates outside of terminal bounding box
        def mask_outside_terminal_bb(_coords, _cands):
            if len(_cands) > 0:
                coords_bb = self.compute_bounding_box(_coords)
                lat_mask = (coords_bb['min_lat'] <= _cands[:, 0]) * (_cands[:, 0] <= coords_bb['max_lat'])
                lng_mask = (coords_bb['min_lng'] <= _cands[:, 1]) * (_cands[:, 1] <= coords_bb['max_lng'])
                mask = lat_mask * lng_mask
                _cands = _cands[mask]
            return _cands

        # === 1. Generate raw candidates (exactly as before) ===
        fermat_candidates = self.generate_proximity_fermat_candidates(np.array(coords), max_candidates=100)

        n_terminals = len(self._terminal_indices) + 1  # +1 for source
        pole_indices = list(range(n_terminals, len(coords)))
        terminal_indices = list(range(n_terminals))

        adaptive_fermat = self.generate_adaptive_fermat_candidates(
            np.array(coords),
            terminal_indices,
            pole_indices
        )

        projection_candidates = np.empty((0, 2))
        collinear_candidates = np.empty((0, 2))

        if cur_edges is not None:
            collinear_candidates = self.generate_collinear_candidates(np.array(coords),
                                                                      cur_edges,
                                                                      num_per_edge=num_per_edge)

            projection_candidates = self.generate_projection_candidates(
                np.array(coords),
                cur_edges,
                terminal_indices=self._terminal_indices,
                max_dist_to_line=40.0,
                min_dist_to_existing=5.0
            )

        # === 2. Store ALL candidates in a dictionary (raw, before any masking) ===
        candidate_dict = {
            'Fermat Candidates': fermat_candidates,
            'Adaptive Fermat Candidates': adaptive_fermat,
            'Collinear Candidates': collinear_candidates,
            'Projection Candidates': projection_candidates,
            'Cluster Candidates': terminal_cluster_centers,
        }

        # === 3. Mask each set individually (for the actual candidate pool) ===
        masked_dict = {}
        for label, cands in candidate_dict.items():
            if len(cands) > 0:
                masked_dict[label] = mask_outside_terminal_bb(coords, cands)
            else:
                masked_dict[label] = np.empty((0, 2), dtype=float)

        # === 4. Build final candidate pool by concatenating only the sets we actually use ===
        to_concat = [
            masked_dict['Fermat Candidates'],
            masked_dict['Adaptive Fermat Candidates'],
            masked_dict['Collinear Candidates'],
            masked_dict['Cluster Candidates'],
            # masked_dict['Projection Candidates'],   # ← still disabled (uncomment when ready)
        ]

        if any(len(arr) > 0 for arr in to_concat):
            candidates = np.concatenate([arr for arr in to_concat if len(arr) > 0])
        else:
            candidates = np.empty((0, 2), dtype=float)

        # -------------- FILTER CANDIDATES --------------
        # remove candidates already added
        ac = [tuple(c) for c in added_candidates]
        candidates = np.array([c for c in candidates if tuple(c) not in ac])

        # dedupe
        candidates = np.unique(candidates, axis=0)

        # === 5. Debug plot using the dictionary (loop instead of 5 separate scatters) ===
        if self.request.debug >= 1 and len(candidates) > 0:
            fig, ax = plt.subplots(figsize=(10, 8))
            ax.set_title("Generated Candidates")
            ax.set_xlabel("Longitude")
            ax.set_ylabel("Latitude")
            ax.set_aspect('equal')

            # Loop through the dictionary — one scatter per candidate type
            for label, cands in candidate_dict.items():  # using raw (pre-mask) just like original
                if len(cands) > 0:
                    ax.scatter(cands[:, 1], cands[:, 0], s=100, marker='o', label=label)

            ax.scatter(coords[:, 1], coords[:, 0], c='black', s=100, marker='o', label='Existing Points')
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3)
            plt.show()

        return candidates

    def _evaluate_rollout(self, current_coords, current_names, candidate, depth=1):
        """
        Evaluates the improvement of a rollout operation for graph optimization tasks, calculating
        potential future configurations and their associated costs.

        This method computes the total cost of a graph after adding a candidate node to the current
        coordinates and recursively looks ahead to test possible next steps (up to the specified depth).
        It is primarily used for optimization tasks where graph traversal or node ordering is key.

        Parameters:
            current_coords (numpy.ndarray): A 2D array representing the coordinates of the current nodes
                in the graph.
            current_names (list of str): A list of names representing the current nodes in the graph.
            candidate (numpy.ndarray): A 1D array representing the coordinate of the candidate node being
                evaluated.
            depth (int): An integer specifying the recursion depth for rollout or look-ahead evaluations
                of future configurations (default is 1).

        Returns:
            float: The best total cost computed for graph configurations after evaluating the rollout
            operation with the candidate node and potential future configurations.
        """
        temp_coords = np.vstack([current_coords, candidate])
        temp_names = current_names + ['pole']

        # Precompute base dist matrix once
        base_dist = self._get_distance_matrix(current_coords)
        cand_dists = self._distances_from_new_point(current_coords, candidate)

        # Initial cost with fast graph builder
        trial_nodes = self._build_nodes(current_coords, [candidate], temp_names)
        DG_init = self._build_directed_graph_with_new_point(
            trial_nodes, base_dist, cand_dists, new_point_idx=len(current_coords)
        )
        arbo_init = self._minimum_spanning_arborescence_w_attrs(DG_init)
        best_future_cost = self._compute_total_cost(arbo_init)

        # Look-ahead steps
        for d in range(depth):
            look_ahead_cands = self.generate_proximity_fermat_candidates(temp_coords, max_candidates=10)
            if len(look_ahead_cands) == 0:
                break

            best_step_cand = None
            for fc in look_ahead_cands:
                # For second-level candidates, we can fall back to full method or extend the fast builder
                f_nodes = self._build_nodes(current_coords, np.vstack([candidate, fc]),
                                            temp_names + ['pole'])

                # For simplicity in rollout, use the original method (or extend later)
                DG = self.build_directed_graph_for_arborescence(f_nodes)
                arbo = self._minimum_spanning_arborescence_w_attrs(DG)
                cost = self._compute_total_cost(arbo)

                if cost < best_future_cost:
                    best_future_cost = cost
                    best_step_cand = fc

            if best_step_cand is not None:
                temp_coords = np.vstack([temp_coords, best_step_cand])
                temp_names.append('pole')
            else:
                break

        return best_future_cost

    def _distances_from_new_point(self, current_coords: np.ndarray, new_point: np.ndarray) -> np.ndarray:
        """
        Calculates the distances from a new point to a series of current coordinates using the Haversine formula.

        This method computes the pairwise distances between a new point and a collection of current coordinates,
        leveraging the vectorized implementation of the Haversine formula.

        Args:
            current_coords (np.ndarray): A 2D array of shape (n, 2) where each row represents the latitude and
                longitude of a point in radians.
            new_point (np.ndarray): A 1D array-like object of shape (2,) representing the latitude and longitude
                of a single point in radians.

        Returns:
            np.ndarray: A flattened 1D array of shape (n,) containing the calculated distances from the new point
            to each point in the `current_coords` array.
        """
        new_point = np.array(new_point).reshape(1, 2)  # shape (1, 2)
        return self.haversine_vec(new_point, current_coords).flatten()

    def _build_directed_graph_with_new_point(
            self,
            nodes,
            base_dist_matrix: np.ndarray,
            cand_dists: np.ndarray,
            new_point_idx: int
    ) -> nx.DiGraph:
        """
        Builds a directed graph representing a network with an additional node.

        This method constructs a directed graph (DiGraph) to represent connections between
        various types of nodes such as source, pole, and terminal nodes. It incorporates both
        existing nodes and a new node, updating edges and weights based on distances and
        connection rules.

        Parameters:
        nodes: List
            A list of Node objects representing the elements in the network. Each Node object
            must have attributes like index, name, type, lat, and lng for the graph.
        base_dist_matrix: np.ndarray
            A 2D array representing the base distance matrix between the existing nodes.
        cand_dists: np.ndarray
            A 1D array representing the distances between the new candidate point and other nodes.
        new_point_idx: int
            The index of the new candidate point that needs to be added to the graph.

        Returns:
        nx.DiGraph
            A directed graph with nodes and edges representing the network structure,
            including the newly added point.

        Raises:
        N/A
        """
        DG = nx.DiGraph()

        source_idx = nodes[self._source_idx].index
        pole_indices = [n.index for n in nodes if n.type == "pole"]
        terminal_indices = [n.index for n in nodes if n.type == "terminal"]

        # Add all nodes
        for node in nodes:
            DG.add_node(node.index,
                        name=node.name,
                        type=node.type,
                        lat=node.lat,
                        lng=node.lng)

        # 1. Source → existing poles + new pole
        for p in pole_indices:
            if p == new_point_idx:
                d = cand_dists[source_idx]  # distance from source to new candidate
            else:
                d = base_dist_matrix[source_idx, p]

            if 0.1 < d:
                w = self.calc_edge_weight(d, voltage="low")
                DG.add_edge(source_idx, p, weight=w, length=d, voltage="low")

        # 2. Pole ↔ Pole (including new pole)
        for i in range(len(pole_indices)):
            for j in range(i + 1, len(pole_indices)):
                p1 = pole_indices[i]
                p2 = pole_indices[j]

                if p1 == new_point_idx:
                    d = cand_dists[p2]
                elif p2 == new_point_idx:
                    d = cand_dists[p1]
                else:
                    d = base_dist_matrix[p1, p2]

                if 0.1 < d:
                    w = self.calc_edge_weight(d, voltage="low")
                    DG.add_edge(p1, p2, weight=w, length=d, voltage="low")
                    DG.add_edge(p2, p1, weight=w, length=d, voltage="low")

        # 3. Poles → Terminals (including new pole)
        for p in pole_indices:
            for h in terminal_indices:
                if p == new_point_idx:
                    d = cand_dists[h]
                else:
                    d = base_dist_matrix[p, h]

                if 0.1 < d:
                    w = self.calc_edge_weight(d, voltage="low", to_terminal=True)
                    DG.add_edge(p, h, weight=w, length=d, voltage="low")

        # 4. Source → Terminals (unchanged, can use base matrix)
        for h in terminal_indices:
            d = base_dist_matrix[source_idx, h]
            if 0.1 < d:
                w = self.calc_edge_weight(d, voltage="low", to_terminal=True)
                DG.add_edge(source_idx, h, weight=w, length=d, voltage="low")

        return DG

    def _solve(self, input_tuple) -> nx.DiGraph:
        """
        Solves the optimization problem of constructing the minimum spanning arborescence with additional candidate nodes
        from an initial set of nodes and edges. The algorithm iteratively improves upon the solution by adding and pruning
        nodes efficiently to minimize total weight.

        Args:
            input_tuple (Tuple): A tuple containing the following parameters:
                - nodes (Iterable): Initial nodes of the graph.
                - coords (np.ndarray): Coordinates of the nodes.
                - source_idx (int): Index of the source node in the graph.
                - terminal_indices (List[int]): Indices of the terminal nodes.
                - names (List[str]): List of node names corresponding to `coords`.
                - solver (np.ndarray): Cost matrix used for the spanning arborescence calculation.

        Returns:
            Tuple[nx.DiGraph, List[Node], np.ndarray]: A tuple containing:
                - Directed graph representing the optimized spanning arborescence.
                - List of Node objects based on the optimized graph.
                - Numpy array of the final coordinate set including additional nodes.

        """
        nodes, coords, source_idx, terminal_indices, names, costs = input_tuple

        # Initial state tracking
        current_coords = np.array(coords)
        current_names = list(names)
        added_candidates = np.empty((0, 2), dtype=float)

        # Constants for Beam Search and Rollout
        BEAM_WIDTH = 3  # Evaluate top 3 immediate candidates deeper
        ROLLOUT_DEPTH = 5  # Look ahead 1 step beyond the current choice
        MAX_STAGNATION = 3
        IMPROVEMENT_THRESHOLD = 0.05  # Minimum meters to keep iterating

        iteration = 0
        stagnation_counter = 0
        cur_total_weight = np.inf

        # Persist the best state found
        best_pruned_graph = None
        cur_edges = None

        # 1. Initial Cluster Center Generation
        terminal_cluster_centers = self.generate_cluster_center_candidates(current_coords, n_init=5)

        while True:
            iteration += 1
            if self.request.debug >= 1:
                print(f"\n--- Iteration {iteration} (Stagnation: {stagnation_counter}/{MAX_STAGNATION}) ---")

            # 2. Generate candidates (including Adaptive Fermat and Projections)
            candidates = self.generate_candidates(
                current_coords, cur_edges, terminal_cluster_centers,
                added_candidates,
                num_per_edge=3
            )

            if len(candidates) == 0:
                if self.request.debug: print("No more candidates to evaluate.")
                break

            # --- STEP 1: IMMEDIATE FILTERING (The "Beam" Selection) ---
            immediate_results = []

            # Get current distance matrix once per iteration (cached)
            dist_matrix = self._get_distance_matrix(current_coords)

            for cand in candidates:
                # Compute only distances from this candidate to all existing points (O(n))
                cand_dists = self._distances_from_new_point(current_coords, cand)

                trial_names = current_names + ['pole']

                # Construct temporary nodes for this specific candidate
                trial_nodes = self._build_nodes(current_coords, [cand], trial_names)

                # Build graph and solve for immediate cost
                DG = self._build_directed_graph_with_new_point(
                    trial_nodes, dist_matrix, cand_dists, new_point_idx=len(current_coords)
                )

                arbo_graph = self._minimum_spanning_arborescence_w_attrs(DG)
                pruned = self.prune_dead_end_pole_branches(arbo_graph)

                imm_cost = self._compute_total_cost(pruned)
                immediate_results.append({
                    "cost": imm_cost,
                    "cand": cand,
                    "graph": pruned,
                    "nodes": trial_nodes
                })

            # Sort by cost and take the top candidates for the Beam
            immediate_results.sort(key=lambda x: x["cost"])
            beam = immediate_results[:BEAM_WIDTH]

            # --- STEP 2: ROLLOUT EVALUATION ---
            best_rollout_score = np.inf
            winner = None

            for item in beam:
                # Look into the future for this specific candidate
                rollout_score = self._evaluate_rollout(
                    current_coords, current_names, item["cand"], depth=ROLLOUT_DEPTH
                )

                if rollout_score < best_rollout_score:
                    best_rollout_score = rollout_score
                    winner = item

            # --- STEP 3: SELECTION & STAGNATION CHECK ---
            if winner is None: break

            improvement = cur_total_weight - winner["cost"]

            if improvement < IMPROVEMENT_THRESHOLD:
                stagnation_counter += 1
                if self.request.debug: print(f"Stagnating: improvement of {improvement:.4f}m is below threshold.")
            else:
                stagnation_counter = 0

            if stagnation_counter >= MAX_STAGNATION:
                if self.request.debug: print("Stopping due to stagnation.")
                break

            # --- STEP 4: COMMIT WINNER ---
            if self.request.debug >= 1:
                print(
                    f"Winner selected via Rollout: Imm Cost: {winner['cost']:.2f} | Rollout Potential: {best_rollout_score:.2f}")

            added_candidates = np.vstack([added_candidates, winner["cand"]])
            current_coords = np.vstack([current_coords, winner["cand"]])
            current_names.append('pole')

            # Invalidate distance matrix cache
            self._dist_matrix = None
            self._cached_coords_hash = None

            cur_total_weight = winner["cost"]
            best_pruned_graph = winner["graph"]
            cur_edges = list(best_pruned_graph.edges())

            # Visualization for debugging
            if self.request.debug >= 1:
                self._plot_current_tree(best_pruned_graph, added_points=[winner["cand"]],
                                        title=f"Iteration {iteration} (Δ {improvement:+.2f} m)")

        return best_pruned_graph
