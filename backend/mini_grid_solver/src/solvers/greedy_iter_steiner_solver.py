from typing import Tuple, List

import networkx as nx
import numpy as np
import scipy.sparse as sp
from joblib import Parallel, delayed
from matplotlib import pyplot as plt
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy.spatial import Delaunay, KDTree
from sklearn.cluster import KMeans, DBSCAN

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
        self._kdtree_cache = None  # will hold the KDTree object
        self._cached_kd_coords = None  # copy of coords used to build it

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

    def _get_kdtree(self, coords: np.ndarray) -> KDTree:
        """
        Returns a cached KDTree, rebuilding only when coordinates actually changed.
        """
        if (self._kdtree_cache is None or
                self._cached_kd_coords is None or
                len(coords) != len(self._cached_kd_coords) or
                np.max(np.abs(coords - self._cached_kd_coords)) > 1e-6):

            if self.request.debug >= 2:
                print(f"Rebuilding KDTree for {len(coords)} points")

            self._kdtree_cache = KDTree(coords)
            self._cached_kd_coords = coords.copy()

        return self._kdtree_cache

    def _compute_coords_hash(self, coords: np.ndarray) -> str:
        """
        Computes a hash representing the provided coordinates array.

        The method rounds the given coordinates to six decimal places to ensure
        a meter-level precision and creates a hash from the rounded values. The
        resulting hash is represented as a string.

        Parameters:
        coords : np.ndarray
            A NumPy array containing coordinate values to be hashed.

        Returns:
        str
            A hash represented as a string that corresponds to the input
            coordinates after rounding.
        """
        # Round to 6 decimals (meter-level precision) and hash
        rounded = np.round(coords, decimals=6)
        return str(rounded.tobytes())

    def _get_distance_matrix(self, coords: np.ndarray) -> np.ndarray:
        """
        Computes and caches a distance matrix for a set of coordinates.

        This method calculates the pairwise distances between all points in a given
        set of coordinates using the Haversine formula. The distance matrix is cached
        to optimize performance, and it is recomputed only if the input coordinates
        change or if no valid cache is available.

        Parameters:
        coords (np.ndarray): A 2D numpy array where each row represents the latitude
        and longitude of a point.

        Returns:
        np.ndarray: A 2D numpy array containing the pairwise distances between all
        points in the input coordinates.

        Raises:
        ValueError: If the input coordinates are invalid or improperly formatted.
        """
        if coords is None or len(coords) == 0:
            return np.zeros((0, 0))

        current_hash = self._compute_coords_hash(coords)

        # Recompute only if cache is missing or points changed
        if (self._dist_matrix is None or
                self._cached_coords_hash != current_hash or
                self._dist_matrix.shape[0] != len(coords)):

            if self.request.debug >= 2:
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
        Generate candidate projection points near graph edges for terminal points.

        This method calculates candidate projection points for a given set of terminal
        points and edges in a graph. The projection points are computed based on their
        distance from the terminal points to the edges, ensuring they comply with
        maximum distance constraints. Additionally, candidates too close to existing
        points are excluded.

        Arguments:
            coords_array (np.ndarray): Array of coordinates, where each row corresponds
                to a point in the graph (e.g., nodes and terminal points). Each row is
                represented as an [x, y] or [lat, lon] pair.
            edge_list (list[tuple[int, int]]): List of edges where each edge is a tuple
                of two integers representing the indices of points in `coords_array`
                that form the edge.
            terminal_indices (list[int]): List of indices in `coords_array` representing
                the terminal points for which projections are to be generated.
            max_dist_to_line (float): Maximum allowable distance in meters for terminal
                points to project onto an edge. Defaults to 40.0.
            min_dist_to_existing (float): Minimum allowable distance in meters from the
                projected point to existing points to avoid duplication. Defaults to
                5.0.

        Returns:
            np.ndarray: A 2D array where each row corresponds to a unique candidate
                projection point. Rows are deduplicated and rounded up to 6 decimal
                places. Returns an empty array if no viable candidates are found.

        Raises:
            None.
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
        Generates collinear candidate points along existing edges in a graph.

        This method computes intermediate collinear points along the edges of
        a given tree structure in a 2D coordinate space, based on specified
        distance constraints and the desired number of intermediate points
        per edge. These points may serve as candidate nodes for further graph
        augmentation or analysis.

        Parameters:
            coords (np.ndarray): A 2D array of shape (n, 2), where each row
                contains the latitude and longitude of a node in the graph.
            current_tree_edges (Iterable[Tuple[int, int]]): A collection of
                tuples, where each tuple represents an edge in the tree,
                using indices of the nodes in the `coords` array.
            max_length (float): The maximum allowable length (in meters) of
                edges to be considered for generating intermediate points.
                Any edges shorter than this length will not have candidates
                generated. Defaults to 30.0.
            num_per_edge (int): The desired number of intermediate points to
                generate per edge. This influences the number of segments
                created along each edge. Defaults to 3.

        Returns:
            np.ndarray: A 2D array where each row represents an intermediate
                candidate point, defined by its latitude and longitude. The
                array is deduplicated and rounded to six decimal places. If no
                suitable candidates are found, returns an empty array with
                shape (0, 2).

        Raises:
            ValueError: If any input has mismatched shape or incompatible
            data type.

        Notes:
            - The method employs the Haversine formula to calculate distances
              on a spherical Earth model, ensuring accurate computations
              for geographic coordinates.
            - Intermediate points are computed using a great-circle
              interpolation strategy, which accounts for the curvature of the
              Earth.
            - Near-duplicate points are automatically removed from the output
              for improved robustness.
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

    @staticmethod
    def kmeans_generate_cluster_center_candidates(coords, n_init=10):
        """
        Generates candidate cluster centers using the K-means clustering algorithm.

        This method processes the given coordinates and applies the K-means clustering
        algorithm to generate possible cluster center points. It uses multiple values
        for the number of clusters to improve the outcomes and to avoid scenarios where
        a single configuration might not provide meaningful clusters. Duplicates among
        generated candidates are filtered out.

        Parameters:
            coords (list of tuple or numpy.ndarray): A list or array of coordinates, where
                each coordinate is represented as a tuple or array of floats (latitude and
                longitude or longitude and latitude).
            n_init (int): The number of times the K-means algorithm will be run with
                different centroid seeds. The final result will be the best output of
                n_init consecutive runs in terms of inertia. Default is 10.

        Returns:
            numpy.ndarray: A numpy array of unique candidate cluster centers. Each row
                of the array represents a cluster center as a pair of coordinates. If no
                meaningful cluster centers can be generated, an empty array is returned.
        """
        if len(coords) < 6:
            return np.array([])  # too few points → no meaningful clusters

        candidates = []
        coords_array = np.array(coords)  # shape (n, 2) [lat, lng] or [lng, lat]

        for k in range(len(coords) // 2, len(coords) // 2 + 3):
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

    def dbscan_generate_cluster_center_candidates(self, coords, eps_meters=40.0, min_samples=2):
        """
        Generates cluster center candidates using the DBSCAN clustering algorithm based on geospatial
        coordinate data. This function identifies clusters of points and computes their geometric centroids
        as candidate cluster centers.

        Arguments:
        coords (list[tuple[float, float]]): List of geospatial coordinates represented as tuples
            of latitude and longitude.
        eps_meters (float): Maximum distance in meters within which points are considered to
            be neighbors in the clustering process. The default is 40.0 meters.
        min_samples (int): Minimum number of data points required to form a cluster. The
            default is 2.

        Returns:
        numpy.ndarray: A 2D array of cluster-center coordinates, where each row corresponds to a
            cluster center. If no valid clusters are found, an empty array with shape (0, 2) is returned.

        Raises:
        None
        """
        coords_array = np.array(coords)
        n = len(coords_array)

        if n < 3:
            if self.request.debug >= 1:
                print("DBSCAN cluster centers: too few points → returning empty")
            return np.empty((0, 2), dtype=float)

        # Precompute full distance matrix once (very fast for your n ≤ 50)
        dist_matrix = self.haversine_vec(coords_array, coords_array)

        # Run DBSCAN with precomputed metric (exact meter distances)
        db = DBSCAN(
            eps=eps_meters,
            min_samples=min_samples,
            metric='precomputed',
            n_jobs=1
        )
        db.fit(dist_matrix)

        labels = db.labels_
        unique_labels = set(labels) - {-1}  # exclude noise

        candidates = []
        for label in unique_labels:
            cluster_mask = labels == label
            cluster_points = coords_array[cluster_mask]

            if len(cluster_points) >= min_samples:
                # Use geometric centroid as the candidate pole location
                center = np.mean(cluster_points, axis=0)
                candidates.append(center)

        if not candidates:
            if self.request.debug >= 1:
                print("DBSCAN cluster centers: no valid clusters found")
            return np.empty((0, 2), dtype=float)

        cluster_centers = np.array(candidates)

        # Final deduplication (~1 cm precision)
        cluster_centers = np.unique(np.round(cluster_centers, decimals=6), axis=0)

        if self.request.debug >= 1:
            print(f"DBSCAN generated {len(cluster_centers)} cluster-center candidates "
                  f"(eps={eps_meters}m, min_samples={min_samples}, "
                  f"clusters found={len(unique_labels)})")

        return cluster_centers

    def generate_adaptive_fermat_candidates(
            self,
            current_coords: np.ndarray,
            terminal_indices: List[int],
            pole_indices: List[int],
            max_distance: float = 60.0,
            max_per_pole: int = 10,  # ← New: hard limit per pole
            min_angle_deg: float = 60.0  # ← New: avoid very flat angles
    ) -> np.ndarray:
        """
        Generates adaptive Fermat point candidates based on current coordinates and input constraints.

        This method computes potential locations for Fermat-Torricelli points, which minimize the
        total distance to a set of given input points under various constraints such as maximum
        distance, minimum angular separation, and other geometric considerations.

        Arguments:
            current_coords (np.ndarray): Array of coordinates representing current points of
              interest (e.g., poles or terminals). Shape is (n, 2), where n is the number of points.
            terminal_indices (List[int]): List of indices identifying terminal points in
              `current_coords` to be considered for Fermat point calculation.
            pole_indices (List[int]): List of indices identifying pole points in `current_coords`
              around which Fermat point candidates are generated.
            max_distance (float): Maximum allowed distance (in meters) for a terminal point
              to be considered near a given pole. Default is 60.0.
            max_per_pole (int): Maximum number of Fermat point candidates generated per pole.
              Default is 8.
            min_angle_deg (float): Minimum allowed angular separation (in degrees) between
              terminal connections to avoid very flat configurations. Default is 30.0.

        Returns:
            np.ndarray: Array of generated Fermat point candidates. Shape is (m, 2), where `m`
              is the total number of candidates. Returns an empty array if no candidates are found.

        Raises:
            None.
        """
        if not pole_indices or len(terminal_indices) < 2:
            return np.empty((0, 2), dtype=float)

        candidates = []
        max_dist_sq = max_distance ** 2  # for faster comparison if needed

        for p_idx in pole_indices:
            pole_coord = current_coords[p_idx]
            pole_term_dists = []

            # Collect nearby terminals with distances (for sorting)
            for t_idx in terminal_indices:
                dist = self.haversine_meters(pole_coord[0], pole_coord[1],
                                             current_coords[t_idx][0], current_coords[t_idx][1])
                if dist <= max_distance and dist > 5.0:  # avoid too close
                    pole_term_dists.append((dist, t_idx))

            if len(pole_term_dists) < 2:
                continue

            # Sort by distance — closer pairs are usually more useful
            pole_term_dists.sort()

            local_cands = []
            count = 0

            for idx1 in range(len(pole_term_dists)):
                for idx2 in range(idx1 + 1, len(pole_term_dists)):
                    if count >= max_per_pole:
                        break

                    dist1, i = pole_term_dists[idx1]
                    dist2, j = pole_term_dists[idx2]

                    # Optional: skip if the two terminals are very far from each other
                    d_term_term = self.haversine_meters(
                        current_coords[i][0], current_coords[i][1],
                        current_coords[j][0], current_coords[j][1]
                    )
                    if d_term_term > max_distance * 1.5:  # too spread out
                        continue

                    # Optional: angle check to avoid very flat configurations
                    if min_angle_deg > 0:
                        a = dist1
                        b = dist2
                        c = d_term_term
                        if a > 0 and b > 0 and c > 0:
                            cos_angle = (a * a + b * b - c * c) / (2 * a * b)
                            cos_angle = np.clip(cos_angle, -1.0, 1.0)
                            angle_deg = np.degrees(np.arccos(cos_angle))
                            if angle_deg < min_angle_deg:
                                continue

                    pts = np.array([pole_coord, current_coords[i], current_coords[j]])
                    st_pt = self.fermat_torricelli_point(pts)
                    local_cands.append(st_pt)
                    count += 1

                if count >= max_per_pole:
                    break

            candidates.extend(local_cands)

        if not candidates:
            return np.empty((0, 2), dtype=float)

        candidates_array = np.array(candidates)

        # Final global filtering
        min_sep = 10.0
        mask = (self.haversine_vec(candidates_array, current_coords) >= min_sep).all(axis=1)
        candidates_array = candidates_array[mask]

        # Deduplicate
        if len(candidates_array) > 0:
            candidates_array = np.unique(np.round(candidates_array, decimals=6), axis=0)

        if self.request.debug >= 1:
            print(f"Adaptive Fermat: generated {len(candidates_array)} candidates "
                  f"(from {len(pole_indices)} poles, max_per_pole={max_per_pole})")

        return candidates_array

    def generate_proximity_fermat_candidates(
            self,
            coords: np.ndarray,
            max_distance: float = 50.0,
            max_candidates: int = 30,
    ) -> np.ndarray:
        """
        Generates proximity Fermat candidates based on input coordinates and constraints.

        This method identifies Fermat points (or generalized Steiner points) from a given
        set of coordinates where three points have an associated spatial relationship. It uses
        either a brute-force approach for small datasets or a cached KDTree implementation for
        efficient processing in larger datasets. The candidates are filtered based on proximity
        constraints relative to the input data to ensure valid and distinct results.

        Parameters:
            coords (np.ndarray): A 2D array of shape (n, 2) containing the coordinates of
                the points in a format where each row represents a point (latitude, longitude).
            max_distance (float): The maximum distance in meters within which points are
                considered close for generating candidates (default: 50.0).
            max_candidates (int): The maximum number of Fermat points to return after all
                filtering and deduplication (default: 30).

        Returns:
            np.ndarray: A 2D array of shape (m, 2) containing the generated Fermat point
                candidates, where each row represents a candidate coordinate (latitude, longitude).
                Returns an empty array if no points can be generated.
        """
        n = len(coords)
        if n < 3:
            return np.empty((0, 2), dtype=float)

        if self.request.debug >= 2:
            print(f"Generating proximity Fermat candidates for {n} points "
                  f"(max_dist={max_distance}m)")

        # ─── ADAPTIVE THRESHOLD ─────────────────────────────────────
        if n <= 25:  # ← tune this value (20–30 works great for your size)
            return self._brute_force_proximity_fermat(coords, max_distance, max_candidates)

        # ─── CACHED KDTREE PATH (for n > 25) ───────────────────────
        tree = self._get_kdtree(coords)  # cached — rebuilds only when coords change

        candidates = []
        close_pairs = tree.query_pairs(r=max_distance)

        if len(close_pairs) == 0:
            if self.request.debug >= 1:
                print("No close pairs found.")
            return np.empty((0, 2), dtype=float)

        for i, j in close_pairs:
            neighbors_i = tree.query_ball_point(coords[i], r=max_distance)
            neighbors_j = tree.query_ball_point(coords[j], r=max_distance)

            common = set(neighbors_i) & set(neighbors_j)
            common.discard(i)
            common.discard(j)

            for k in common:
                if k <= j:  # enforce i < j < k to avoid duplicates
                    continue

                pts = coords[[i, j, k]]
                st_pt = self.fermat_torricelli_point(pts)
                candidates.append(st_pt)

                if len(candidates) >= max_candidates * 3:  # oversample before filtering
                    break
            if len(candidates) >= max_candidates * 3:
                break

        if not candidates:
            return np.empty((0, 2), dtype=float)

        candidates = np.array(candidates)

        # Filter candidates too close to any existing point
        min_dists = np.min(self.haversine_vec(candidates, coords), axis=1)
        candidates = candidates[min_dists >= 10.0]

        # Deduplicate (≈1 cm precision) and limit
        if len(candidates) > 0:
            candidates = np.unique(np.round(candidates, decimals=6), axis=0)
        if len(candidates) > max_candidates:
            candidates = candidates[:max_candidates]

        if self.request.debug >= 2:
            print(f"KDTree (cached) generated {len(candidates)} Fermat candidates "
                  f"from {len(close_pairs)} close pairs")

        return candidates

    def _brute_force_proximity_fermat(
            self,
            coords: np.ndarray,
            max_distance: float = 50.0,
            max_candidates: int = 100,
    ) -> np.ndarray:
        """
        Determine candidate Fermat-Torricelli points for triplets of coordinates within
        a specified maximum distance using a brute-force approach.

        The function computes potential Fermat-Torricelli points, which minimize the sum
        of distances to three given points. It uses precomputed distance matrices for efficiency
        and applies filtering and deduplication to refine the results.

        Attributes:
            coords: np.ndarray
                Array containing the coordinates of points (latitude and longitude)
                as an (n, 2) dimensional array.
            max_distance: float, default 50.0
                Maximum allowable distance between any two points in a triplet to be
                considered for candidate generation.
            max_candidates: int, default 100
                Maximum number of Fermat-Torricelli point candidates to return in the
                result after filtering and deduplication.

        Returns:
            np.ndarray:
                Array of unique Fermat-Torricelli point candidates for the input
                coordinates, limited to the specified maximum count and filtered by
                distance constraints. If no candidates are generated, returns an empty
                array with shape (0, 2).

        Raises:
            None explicitly, but the function may raise errors related to the numpy
            operations or the invocation of other instance methods.
        """
        n = len(coords)
        candidates = []

        # Reuse your cached distance matrix if available
        dist_matrix = self._get_distance_matrix(coords)

        for i in range(n):
            for j in range(i + 1, n):
                if dist_matrix[i, j] > max_distance:
                    continue
                for k in range(j + 1, n):
                    if (dist_matrix[i, k] <= max_distance and
                            dist_matrix[j, k] <= max_distance):

                        pts = coords[[i, j, k]]
                        st_pt = self.fermat_torricelli_point(pts)
                        candidates.append(st_pt)

                        if len(candidates) >= max_candidates * 2:  # slight oversample
                            break
                if len(candidates) >= max_candidates * 2:
                    break
            if len(candidates) >= max_candidates * 2:
                break

        if not candidates:
            return np.empty((0, 2), dtype=float)

        candidates = np.array(candidates)

        # Filter too close to existing points
        min_dists = np.min(self.haversine_vec(candidates, coords), axis=1)
        candidates = candidates[min_dists >= 10.0]

        # Deduplicate and limit
        if len(candidates) > 0:
            candidates = np.unique(np.round(candidates, decimals=6), axis=0)
        if len(candidates) > max_candidates:
            candidates = candidates[:max_candidates]

        if self.request.debug >= 1:
            print(f"Brute-force generated {len(candidates)} Fermat candidates")

        return candidates

    def filter_candidates(
            self,
            candidates: np.ndarray,
            current_coords: np.ndarray,
            added_candidates: np.ndarray,
            pole_indices: List[int],
            terminal_indices: List[int]
    ) -> np.ndarray:
        """
        Filters a set of candidate coordinates based on various criteria, such as bounding box constraints,
        minimum distance thresholds, and duplicate elimination. The function applies successive filters to
        reduce the set of candidates while ensuring compliance with the specified constraints.

        Parameters:
        candidates (np.ndarray): A 2D numpy array of candidate coordinates, where each row represents a
            latitude-longitude coordinate pair.
        current_coords (np.ndarray): A 2D numpy array of current coordinates in the system, where each
            row is a latitude-longitude coordinate pair.
        added_candidates (np.ndarray): A 2D numpy array of already-added candidate coordinates to be excluded
            from the results.
        pole_indices (List[int]): A list of indices referencing existing pole coordinates within the
            current_coords array.
        terminal_indices (List[int]): A list of indices referencing terminal coordinates within the
            current_coords array.

        Returns:
        np.ndarray: A 2D numpy array of filtered candidate coordinates, where each row represents a
            latitude-longitude coordinate pair.
        """
        if len(candidates) == 0:
            return np.empty((0, 2), dtype=float)

        original_count = len(candidates)

        # ─── 1. Bounding-box filter (moved here from generate_candidates) ───
        if len(terminal_indices) > 0:
            # Use ONLY terminal coordinates for the bounding box
            # (this is what "terminal bounding box" originally meant)
            terminal_coords = current_coords[terminal_indices]
            bb = self.compute_bounding_box(terminal_coords)

            lat_mask = (bb['min_lat'] <= candidates[:, 0]) & (candidates[:, 0] <= bb['max_lat'])
            lng_mask = (bb['min_lng'] <= candidates[:, 1]) & (candidates[:, 1] <= bb['max_lng'])
            mask_bb = lat_mask & lng_mask

            candidates = candidates[mask_bb]
            if self.request.debug >= 2:
                print(f"    BB filter removed {original_count - len(candidates)} candidates outside terminal bbox")
        else:
            mask_bb = np.ones(len(candidates), dtype=bool)

        # ─── 2. Minimum pole-to-terminal distance (voltage aware) ───
        min_pole_to_term = self.get_min_pole_to_term()

        if len(terminal_indices) > 0 and len(candidates) > 0:
            terminal_coords = current_coords[terminal_indices]
            dists_to_terminals = self.haversine_vec(candidates, terminal_coords)
            mask_term = np.min(dists_to_terminals, axis=1) >= min_pole_to_term
            candidates = candidates[mask_term]

        # ─── 3. Minimum pole-to-pole distance (existing poles) ───
        min_pole_to_pole = 5.0  # you can later expose this in constraints if you want
        if len(pole_indices) > 0 and len(candidates) > 0:
            pole_coords = current_coords[pole_indices]
            dists_to_poles = self.haversine_vec(candidates, pole_coords)
            mask_poles = np.min(dists_to_poles, axis=1) >= min_pole_to_pole
            candidates = candidates[mask_poles]

        # ─── 4. Remove already-added candidates ───
        if len(added_candidates) > 0 and len(candidates) > 0:
            ac_set = {tuple(np.round(c, decimals=6)) for c in added_candidates}
            candidates = np.array([
                c for c in candidates
                if tuple(np.round(c, decimals=6)) not in ac_set
            ])

        # ─── 5. Final deduplication ───
        if len(candidates) > 0:
            candidates = np.unique(np.round(candidates, decimals=6), axis=0)

        # ─── Debug summary ───
        if self.request.debug >= 1:
            kept = len(candidates)
            removed = original_count - kept
            print(f"filter_candidates: kept {kept}/{original_count} candidates "
                  f"(removed {removed} — BB + min-distance + duplicates)")

        return candidates

    def generate_candidates(self,
                            coords,
                            cur_edges,
                            fermat_candidates,
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

        # if cur_edges is not None:
        #     collinear_candidates = self.generate_collinear_candidates(np.array(coords),
        #                                                               cur_edges,
        #                                                               num_per_edge=num_per_edge)

        # projection_candidates = self.generate_projection_candidates(
        #     np.array(coords),
        #     cur_edges,
        #     terminal_indices=self._terminal_indices,
        #     max_dist_to_line=40.0,
        #     min_dist_to_existing=5.0
        # )

        # === 2. Store ALL candidates in a dictionary (raw, before any masking) ===
        candidate_dict = {
            'Fermat Candidates': fermat_candidates,
            'Adaptive Fermat Candidates': adaptive_fermat,
            # 'Collinear Candidates': collinear_candidates,
            # 'Projection Candidates': projection_candidates,
            'Cluster Candidates': terminal_cluster_centers,
        }

        # === 4. Build final candidate pool by concatenating only the sets we actually use ===
        to_concat = [
            candidate_dict['Fermat Candidates'],
            candidate_dict['Adaptive Fermat Candidates'],
            # masked_dict['Collinear Candidates'],
            candidate_dict['Cluster Candidates'],
            # masked_dict['Projection Candidates'],
        ]

        if any(len(arr) > 0 for arr in to_concat):
            candidates = np.concatenate([arr for arr in to_concat if len(arr) > 0])
        else:
            candidates = np.empty((0, 2), dtype=float)

        # -------------- FILTER CANDIDATES --------------
        n_terminals = len(self._terminal_indices) + 1  # +1 for source
        pole_indices = list(range(n_terminals, len(coords)))
        terminal_indices_for_filter = self._terminal_indices  # real homes only

        candidates = self.filter_candidates(
            candidates=candidates,
            current_coords=np.array(coords),
            added_candidates=np.array(added_candidates),
            pole_indices=pole_indices,
            terminal_indices=terminal_indices_for_filter
        )

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

    def _fast_scipy_rollout_eval(self, coords: np.ndarray) -> float:
        """
        Evaluates the cost of a network rollout using a fast implementation relying on
        SciPy's minimum spanning tree (MST) computation.

        This method computes the total cost of the network rollout, including the
        wire cost, pole cost, and penalties for exceeding length constraints. It uses
        optimized, vectorized operations for calculating costs and constraints, and
        employs the MST algorithm to minimize the overall cost. Pruning is then applied
        to remove redundant dead-end poles.

        Parameters:
        coords: numpy.ndarray
            A 2D array representing geographic coordinates (latitude and longitude)
            of network nodes.

        Returns:
        float
            The total cost of the network rollout, considering wire costs, pole costs,
            and penalties.

        Raises:
        None
        """
        n = len(coords)
        source_idx = self._source_idx
        terminals = self._terminal_indices
        poles = [i for i in range(n) if i != source_idx and i not in terminals]

        # 1. Fast Distance Matrix
        dist = self.haversine_vec(coords, coords)

        # 2. Extract Constraints & Costs
        low_cost = self.request.costs.lowVoltageCostPerMeter
        pole_cost = self.request.costs.poleCost
        max_pole_pole = self.request.lengthConstraints.low.poleToPoleLengthConstraint
        max_pole_term = self.request.lengthConstraints.low.poleToTerminalLengthConstraint
        MAX_PENALTY = 10000.0  # From your base class

        # 3. Vectorized Edge Weight Calculations
        wire_cost = dist * low_cost

        # Trunk Cost (Pole-Pole, Source-Pole)
        extra_poles_trunk = np.maximum(0, np.ceil(dist / max_pole_pole) - 1)
        excess_trunk = np.maximum(0, dist - max_pole_pole)
        trunk_cost = wire_cost + (extra_poles_trunk * pole_cost) + (excess_trunk * MAX_PENALTY)

        # Terminal Drop Cost (Pole-Terminal, Source-Terminal)
        dist_adj = np.maximum(0, dist - max_pole_term)
        extra_poles_term = np.maximum(0, np.ceil(dist_adj / max_pole_pole) - 1)
        excess_term = np.maximum(0, dist - max_pole_term)
        term_cost = wire_cost + (extra_poles_term * pole_cost) + (excess_term * MAX_PENALTY)

        # 4. Assemble Adjacency Matrix (0 means no edge in SciPy MST)
        adj = np.zeros((n, n), dtype=float)

        # Source <-> Poles
        if poles:
            adj[source_idx, poles] = trunk_cost[source_idx, poles]
            adj[poles, source_idx] = trunk_cost[poles, source_idx]

        # Pole <-> Pole
        if len(poles) > 1:
            p_grid = np.ix_(poles, poles)
            adj[p_grid] = trunk_cost[p_grid]

        # Source/Pole <-> Terminals
        valid_sources = [source_idx] + poles
        if valid_sources and terminals:
            st_grid = np.ix_(valid_sources, terminals)
            ts_grid = np.ix_(terminals, valid_sources)
            adj[st_grid] = term_cost[st_grid]
            adj[ts_grid] = term_cost[ts_grid]

        # Remove very short invalid edges and self-loops
        adj[dist < 0.1] = 0.0
        np.fill_diagonal(adj, 0.0)

        # 5. Compute MST using SciPy's C-backend
        csr_adj = sp.csr_matrix(adj)
        mst = minimum_spanning_tree(csr_adj)

        # 6. Fast Pruning of Dead-End Poles
        # Convert upper-triangular MST to full symmetric matrix to get true degrees
        mst_dense = mst.toarray()
        undirected_mst = mst_dense + mst_dense.T

        # Count non-zero edges for each node
        degrees = np.count_nonzero(undirected_mst, axis=1)

        pruned_nodes = set()
        removed = True
        while removed:
            removed = False
            for p in poles:
                if p not in pruned_nodes and degrees[p] == 1:
                    pruned_nodes.add(p)
                    # Find the single neighbor and sever the connection
                    neighbors = np.nonzero(undirected_mst[p])[0]
                    if len(neighbors) > 0:
                        neighbor = neighbors[0]
                        undirected_mst[p, neighbor] = 0.0
                        undirected_mst[neighbor, p] = 0.0
                        degrees[p] = 0
                        degrees[neighbor] -= 1
                    removed = True

        # 7. Final Cost Calculation
        # undirected_mst contains symmetric edge weights, so sum / 2 is the exact total
        total_wire_and_extra_pole_cost = np.sum(undirected_mst) / 2.0
        num_active_poles = len(poles) - len(pruned_nodes)

        return total_wire_and_extra_pole_cost + (num_active_poles * pole_cost)

    def _evaluate_rollout(self, current_coords, candidate, depth=2):
        """
        Evaluates the rollout cost for a candidate location in relation to current coordinates.

        This method performs a multi-level look-ahead to determine the best cost achievable by
        adding a candidate location to the current set of coordinates. The evaluation is completed
        using a recursive approach, iterating up to the given depth. The process includes generating
        and testing proximity candidates at each level to improve the overall cost. The method
        returns the best cost achieved at the end of the evaluation.

        Parameters:
            current_coords (np.ndarray): A 2D array representing the current coordinates.
            candidate (np.ndarray): A 1D array representing the candidate coordinate to evaluate.
            depth (int, optional): The number of look-ahead levels to evaluate. Defaults to 2.

        Returns:
            float: The best achievable cost after evaluating the candidate and performing look-ahead
            up to the specified depth.
        """
        # First level: add the primary candidate
        temp_coords = np.vstack([current_coords, candidate])

        # Evaluate primary candidate cost
        best_future_cost = self._fast_scipy_rollout_eval(temp_coords)

        # Look-ahead (second level and beyond)
        for d in range(depth):
            look_ahead_cands = self.generate_proximity_fermat_candidates(temp_coords, max_candidates=8)

            if len(look_ahead_cands) == 0:
                break

            best_step_cand = None
            for fc in look_ahead_cands:
                # Add the future candidate to the temporary test stack
                test_coords = np.vstack([temp_coords, fc])

                # Lightning-fast evaluation
                cost = self._fast_scipy_rollout_eval(test_coords)

                if cost < best_future_cost:
                    best_future_cost = cost
                    best_step_cand = fc

            # If a future step improves the score, commit it to the local temporary stack and dig deeper
            if best_step_cand is not None:
                temp_coords = np.vstack([temp_coords, best_step_cand])
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
        Constructs a directed graph (DiGraph) with a new node added to represent a new point,
        alongside existing nodes and their relationships as defined by distances and parameters.

        This function integrates the new point into the graph, updates edge weights and
        attributes, and maintains relationships between different node types (source, poles,
        and terminals). It calculates the appropriate weights for edges based on distance
        and voltage levels.

        Parameters:
        nodes : list
            A list of node objects where each node defines attributes such as index, name,
            type, latitude, and longitude.
        base_dist_matrix : np.ndarray
            A 2D array representing the base distance matrix between existing nodes.
        cand_dists : np.ndarray
            A 1D array representing candidate distances from the new point to all nodes.
        new_point_idx : int
            The index of the newly added point in the nodes list.

        Returns:
        nx.DiGraph
            A directed graph representing the updated relationships and attributes of nodes,
            including the newly integrated point.
        """
        DG = nx.DiGraph()

        source_idx = self._source_idx
        n = len(nodes)

        # Add all nodes with attributes
        for node in nodes:
            DG.add_node(node.index,
                        name=node.name,
                        type=node.type,
                        lat=node.lat,
                        lng=node.lng)

        pole_indices = [i for i, node in enumerate(nodes) if node.type == "pole"]
        terminal_indices = [i for i, node in enumerate(nodes) if node.type == "terminal"]

        # 1. Source → all poles (including the new one)
        for p in pole_indices:
            if p == new_point_idx:
                d = cand_dists[source_idx]
            else:
                d = base_dist_matrix[source_idx, p]

            if 0.1 < d < 1e6:  # safety upper bound
                w = self.calc_edge_weight(d)
                DG.add_edge(source_idx, p, weight=w, length=d, voltage=self.request.voltageLevel)

        # 2. Pole ↔ Pole (bidirectional)
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

                if 0.1 < d < 1e6:
                    w = self.calc_edge_weight(d)
                    DG.add_edge(p1, p2, weight=w, length=d, voltage=self.request.voltageLevel)
                    DG.add_edge(p2, p1, weight=w, length=d, voltage=self.request.voltageLevel)

        # 3. Poles → Terminals (service drops)
        for p in pole_indices:
            for h in terminal_indices:
                if p == new_point_idx:
                    d = cand_dists[h]
                else:
                    d = base_dist_matrix[p, h]

                if 0.1 < d < 1e6:
                    w = self.calc_edge_weight(d, to_terminal=True)
                    DG.add_edge(p, h, weight=w, length=d, voltage=self.request.voltageLevel)

        # 4. Source → Terminals (unchanged, can use base matrix)
        for h in terminal_indices:
            d = base_dist_matrix[source_idx, h]
            if 0.1 < d < 1e6:
                w = self.calc_edge_weight(d, to_terminal=True)
                DG.add_edge(source_idx, h, weight=w, length=d, voltage=self.request.voltageLevel)

        return DG

    def _evaluate_candidate_fast(self, cand, current_coords, current_names, dist_matrix):
        """
        Fast path for evaluating one candidate.
        Uses the optimized builder. Falls back only if something goes wrong.
        """
        try:
            cand_dists = self._distances_from_new_point(current_coords, cand)
            trial_names = current_names + ['pole']
            trial_nodes = self._build_nodes(current_coords, [cand], trial_names)

            DG = self._build_directed_graph_with_new_point(
                trial_nodes, dist_matrix, cand_dists, new_point_idx=len(current_coords)
            )

            arbo_graph = self._minimum_spanning_arborescence_w_attrs(DG)
            pruned = self.prune_dead_end_pole_branches(arbo_graph)
            cost = self._compute_total_cost(pruned)

            return {
                "cost": cost,
                "cand": cand.copy(),
                "graph": pruned,
                "nodes": trial_nodes,
                "success": True
            }

        except Exception as e:
            if self.request.debug >= 1:
                print(f"Fast evaluation failed for candidate: {e}. Falling back to full method.")

            # Fallback to the slower full method
            trial_nodes = self._build_nodes(current_coords, [cand], current_names + ['pole'])
            DG = self.build_directed_graph_for_arborescence(trial_nodes)
            arbo_graph = self._minimum_spanning_arborescence_w_attrs(DG)
            pruned = self.prune_dead_end_pole_branches(arbo_graph)
            cost = self._compute_total_cost(pruned)

            return {
                "cost": cost,
                "cand": cand.copy(),
                "graph": pruned,
                "nodes": trial_nodes,
                "success": False
            }

    def _solve(self) -> nx.DiGraph:
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

        # Initial state tracking
        current_coords = np.array(self._coords)
        current_names = list(self._names)
        added_candidates = np.empty((0, 2), dtype=float)

        # Constants for Beam Search and Rollout
        BEAM_WIDTH = 5  # Evaluate top 3 immediate candidates deeper
        ROLLOUT_DEPTH = 3  # Look ahead 1 step beyond the current choice
        MAX_STAGNATION = 3
        IMPROVEMENT_THRESHOLD = 0.05  # Minimum meters to keep iterating

        iteration = 0
        stagnation_counter = 0
        cur_total_weight = np.inf

        # Persist the best state found
        best_pruned_graph = None
        cur_edges = None

        # 1. Initial Cluster Center Generation
        # terminal_cluster_centers = self.kmeans_generate_cluster_center_candidates(current_coords, n_init=5)
        terminal_cluster_centers = self.dbscan_generate_cluster_center_candidates(current_coords, eps_meters=30,
                                                                                  min_samples=2)
        fermat_candidates = self.generate_proximity_fermat_candidates(np.array(current_coords),
                                                                      max_distance=40,
                                                                      max_candidates=50)

        fermat_candidates = self.filter_candidates(fermat_candidates, current_coords, [], [], [])
        terminal_cluster_centers = self.filter_candidates(terminal_cluster_centers, current_coords, [], [], [])

        while True:
            iteration += 1
            if self.request.debug >= 1:
                print(f"\n--- Iteration {iteration} (Stagnation: {stagnation_counter}/{MAX_STAGNATION}) ---")

            # 2. Generate candidates (including Adaptive Fermat and Projections)
            candidates = self.generate_candidates(
                current_coords, cur_edges,
                fermat_candidates, terminal_cluster_centers,
                added_candidates,
                num_per_edge=3
            )

            if len(candidates) == 0:
                if self.request.debug: print("No more candidates to evaluate.")
                break

            # --- STEP 1: IMMEDIATE FILTERING (The "Beam" Selection) ---
            def eval_wrapper(cand):
                # Instantly evaluate the candidate purely in NumPy/SciPy
                temp_coords = np.vstack([current_coords, cand])
                cost = self._fast_scipy_rollout_eval(temp_coords)
                return {"cost": cost, "cand": cand}

            if self.request.debug >= 1:
                print(f"Evaluating {len(candidates)} candidates sequentially using SciPy...")

            # Small problems → serial is faster
            if len(candidates) > 0:
                if self.request.debug >= 1:
                    print(f"Evaluating {len(candidates)} candidates serially")
                immediate_results = [eval_wrapper(c) for c in candidates]
            else:
                n_jobs = -1
                if self.request.debug >= 1:
                    print(f"Evaluating {len(candidates)} candidates in parallel (n_jobs={n_jobs}, threading)")

                immediate_results = Parallel(
                    n_jobs=n_jobs,
                    backend="loky",
                    verbose=self.request.debug
                )(delayed(eval_wrapper)(cand) for cand in candidates)

            # Sort by cost and take the top candidates for the Beam
            immediate_results.sort(key=lambda x: x["cost"])
            beam = immediate_results[:BEAM_WIDTH]

            # --- STEP 2: ROLLOUT EVALUATION ---
            best_rollout_score = np.inf
            winner = None

            for item in beam:
                # Look into the future for this specific candidate using SciPy
                rollout_score = self._evaluate_rollout(
                    current_coords, item["cand"], depth=ROLLOUT_DEPTH
                )

                if rollout_score < best_rollout_score:
                    best_rollout_score = rollout_score
                    winner = item

            # --- STEP 3: SELECTION & STAGNATION CHECK ---
            if winner is None: break

            improvement = cur_total_weight - winner["cost"]

            if self.request.debug >= 1:
                print(f"Rollout Score: {rollout_score:.2f} (Improvement: {improvement:.2f})")

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

            # 1. Build the formal NetworkX graph ONLY for the chosen winner
            trial_names = current_names + ['pole']
            trial_nodes = self._build_nodes(current_coords, [winner["cand"]], trial_names)

            DG = self.build_directed_graph_for_arborescence(trial_nodes)
            arbo_graph = self._minimum_spanning_arborescence_w_attrs(DG)
            best_pruned_graph = self.prune_dead_end_pole_branches(arbo_graph)

            if iteration % 3:
                best_pruned_graph = self._drop_redundant_poles(best_pruned_graph)

            # 2. Update state tracking variables
            added_candidates = np.vstack([added_candidates, winner["cand"]])
            current_coords = np.vstack([current_coords, winner["cand"]])
            current_names = trial_names

            # 3. Invalidate caches
            self._kdtree_cache = None
            self._cached_kd_coords = None
            self._dist_matrix = None
            self._cached_coords_hash = None

            cur_total_weight = winner["cost"]
            cur_edges = list(best_pruned_graph.edges())

            # Visualization for debugging
            if self.request.debug >= 1:
                self._plot_current_graph(best_pruned_graph, added_points=[winner["cand"]],
                                         title=f"Iteration {iteration} (Δ {improvement:+.2f} m)")

        # Finally Gradient Decent each pole placement to ensure not local optimization is left on the table
        final_graph = self._post_solver_local_opt(best_pruned_graph)

        return final_graph
