from typing import List

import numpy as np
from scipy.spatial import KDTree
from sklearn.cluster import KMeans, DBSCAN

from .base_mini_grid_solver import BaseMiniGridSolver


class CandidateGeneration(BaseMiniGridSolver):

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
