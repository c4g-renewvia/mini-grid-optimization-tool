from typing import List

import numpy as np
from scipy.spatial import KDTree
from sklearn.cluster import KMeans, DBSCAN

from .base_mini_grid_solver import BaseMiniGridSolver


class CandidateGeneration(BaseMiniGridSolver):
    """Provide shared geometric candidate generators for Steiner solvers.

    The helpers create candidate pole coordinates from edges, clusters,
    proximities, and triangle geometry, then filter candidates against the
    current network and configured constraints.
    """

    @staticmethod
    def fermat_torricelli_point(pts: np.ndarray) -> np.ndarray:
        """Approximate the Fermat-Torricelli point for a triangle.

        If an angle is at least 120 degrees, returns its vertex; otherwise returns
        the centroid as a simple approximation.

        Args:
            pts: Array of exactly three point coordinates.

        Returns:
            The selected vertex or approximate Fermat-Torricelli point.

        Raises:
            ValueError: If ``pts`` does not contain exactly three points.
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
        """Return the cached KDTree, rebuilding it when coordinates change.

        Args:
            coords: Coordinates used to build or validate the cached tree.

        Returns:
            A KDTree containing the supplied coordinates.
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
        """Generate candidate projections of terminals onto graph edges.

        Projections farther than the maximum edge distance or too close to an
        existing point are discarded. Results are rounded and deduplicated.

        Args:
            coords_array: Point coordinates indexed by edge and terminal indices.
            edge_list: Edges represented by pairs of coordinate indices.
            terminal_indices: Indices of terminals to project.
            max_dist_to_line: Maximum terminal-to-edge distance in meters.
            min_dist_to_existing: Minimum projection-to-existing-point distance
                in meters.

        Returns:
            Unique candidate coordinates, or an empty array if none qualify.
        """
        candidates = []

        def point_to_segment_distance_and_projection(p, a, b):
            """Find a point's distance and projection onto a line segment.

            Args:
                p: Point to project.
                a: First endpoint of the segment.
                b: Second endpoint of the segment.

            Returns:
                The distance in meters and the closest coordinate on the segment.
            """
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
        """Generate intermediate coordinates along sufficiently long tree edges.

        Points are interpolated along great-circle paths, rounded, and deduplicated.

        Args:
            coords: Latitude-longitude coordinates indexed by the edge endpoints.
            current_tree_edges: Edges represented by pairs of coordinate indices.
            max_length: Edges at or below this length in meters are skipped.
            num_per_edge: Desired number of intermediate points per qualifying edge.

        Returns:
            An ``(m, 2)`` array of candidate coordinates, or an empty ``(0, 2)``
            array when no edges qualify.
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
        """Generate unique cluster-center candidates with K-means.

        K-means is run for several cluster counts, retaining centers whose clusters
        contain at least two points.

        Args:
            coords: Input point coordinates.
            n_init: Number of K-means initializations for each cluster count.

        Returns:
            A deduplicated array of candidate centers, or an empty array if the
            input is too small or no clusters are usable.
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
        """Generate cluster-center candidates with distance-based DBSCAN.

        Clusters are computed from haversine distances, and their coordinate
        centroids are returned.

        Args:
            coords: Latitude-longitude coordinates to cluster.
            eps_meters: Maximum neighbor distance in meters.
            min_samples: Minimum number of points required for a cluster.

        Returns:
            An ``(m, 2)`` array of unique cluster centers, or an empty array if no
            valid clusters are found.
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
        """Generate Fermat candidates from nearby pole-terminal pairs.

        Candidate triples are constrained by distance and minimum angle, then
        filtered for separation from existing coordinates.

        Args:
            current_coords: Coordinates of current poles and terminals.
            terminal_indices: Indices of terminals in ``current_coords``.
            pole_indices: Indices of poles around which to generate candidates.
            max_distance: Maximum pole-to-terminal distance in meters.
            max_per_pole: Maximum candidates generated around each pole.
            min_angle_deg: Minimum terminal-pair angle in degrees.

        Returns:
            An ``(m, 2)`` array of candidate coordinates, or an empty array if
            no candidates qualify.
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
        """Generate Fermat candidates from nearby coordinate triplets.

        Small inputs use brute-force enumeration; larger inputs use a cached KDTree.
        Candidates close to existing points are removed.

        Args:
            coords: Latitude-longitude coordinates to search.
            max_distance: Maximum distance in meters for nearby points.
            max_candidates: Maximum number of candidates to return.

        Returns:
            An ``(m, 2)`` array of candidate coordinates, or an empty array if
            no candidates qualify.
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
        """Generate Fermat candidates by checking every nearby point triplet.

        The method reuses a distance matrix, then filters, deduplicates, and caps
        the candidate set.

        Args:
            coords: Latitude-longitude coordinates to search.
            max_distance: Maximum pairwise distance in meters for a triplet.
            max_candidates: Maximum number of candidates to return.

        Returns:
            An ``(m, 2)`` array of candidate coordinates, or an empty array if
            no triplets qualify.
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
        """Filter candidates by bounds, spacing, and duplication.

        Candidates outside the terminal bounding box, too close to terminals or
        existing poles, or already added are removed.

        Args:
            candidates: Candidate latitude-longitude coordinates.
            current_coords: Coordinates of existing nodes.
            added_candidates: Previously added candidate coordinates.
            pole_indices: Indices of existing poles in ``current_coords``.
            terminal_indices: Indices of terminals in ``current_coords``.

        Returns:
            The filtered and deduplicated candidate coordinates.
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
