import math
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.patches import Ellipse
from mini_grid_solver.src.utils.models import *

from .candidate_generation import CandidateGeneration
from ..utils.registry import register_solver


@register_solver
class DiskBasedSteinerSolver(CandidateGeneration):
    """
    Represents a solver to compute approximate Steiner tree solutions using a disk-based heuristic approach.

    This class extends the CandidateGeneration class to integrate disk-covering algorithms for network
    optimization problems, particularly for problems involving terminals and their coverage with minimal
    resources. It employs techniques such as bounding-box checks, exclusion of redundant or infeasible
    candidates, and optimized disk center selection via tie-breaking mechanisms. The primary purpose of
    the class is to enable efficient determination of disk-based Steiner points for constructing approximate
    solutions to minimum Steiner tree problems in geometric networks.
    """

    def __init__(self, request: SolverRequest):
        super().__init__(request)
        # Caches from GreedyIterSteinerSolver for KDTree / Delaunay reuse
        self._delaunay_cache = None
        self._cached_coords = None
        self._kdtree_cache = None
        self._cached_kd_coords = None

    @staticmethod
    def get_input_params():
        return []

    def _plot_disk_cover(self,
                         term_coords: np.ndarray,
                         disk_centers: np.ndarray,
                         R: float,
                         candidates: Optional[np.ndarray] = None,
                         title: str = "Minimum Disk Cover"):
        """
        Plots a visual representation of the minimum disk cover for a given set of points on a 2D plane.
        (Exactly as in original DiskBasedSteinerSolver – all plotting calls restored)
        """
        fig, ax = plt.subplots(figsize=(11, 9))
        ax.set_title(title)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_aspect('equal')

        # 1. Terminals
        ax.scatter(term_coords[:, 1], term_coords[:, 0],
                   c='red', s=90, marker='o', edgecolors='darkred', linewidth=1,
                   label=f'Terminals ({len(term_coords)})')

        # 2. All candidate centers (light gray – helps see greedy selection)
        if candidates is not None and len(candidates) > 0:
            ax.scatter(candidates[:, 1], candidates[:, 0],
                       c='gray', s=25, marker='.', alpha=1,
                       label=f'All Candidates ({len(candidates)})')

        # 3. Selected disk centers + accurate coverage circles
        if len(disk_centers) > 0:
            ax.scatter(disk_centers[:, 1], disk_centers[:, 0],
                       c='blue', s=180, marker='*', edgecolors='black', linewidth=1.5,
                       label=f'Disk Centers ({len(disk_centers)})')

            # ─── Proper R (meters) → degrees conversion for plotting ───
            if len(term_coords) > 0:
                avg_lat = float(np.mean(term_coords[:, 0]))
            else:
                avg_lat = 45.0  # fallback (Portland area)

            METERS_PER_DEG_LAT = 111111.0
            METERS_PER_DEG_LON = METERS_PER_DEG_LAT * np.cos(np.radians(avg_lat))

            # Radius in degrees for lat and lon axes
            r_lat_deg = R / METERS_PER_DEG_LAT
            r_lon_deg = R / METERS_PER_DEG_LON

            for center in disk_centers:
                # Ellipse centered at (lon, lat) with correct aspect ratio
                ellipse = Ellipse(
                    xy=(center[1], center[0]),  # (lon, lat)
                    width=2 * r_lon_deg,  # full width in longitude degrees
                    height=2 * r_lat_deg,  # full height in latitude degrees
                    fill=False,
                    color='blue',
                    alpha=0.25,
                    linewidth=2,
                    linestyle='--'
                )
                ax.add_patch(ellipse)

        ax.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.show()
        plt.close(fig)

    def filter_candidates(
            self,
            candidates: np.ndarray,
            current_coords: np.ndarray,
            added_candidates: np.ndarray,
            pole_indices: List[int],
            terminal_indices: List[int]
    ) -> np.ndarray:
        """
        Filters candidate coordinates based on bounding-box constraints, pole-to-terminal and pole-to-pole
        minimum distance conditions, removal of already added candidates, and deduplication.

        Parameters:
            candidates (np.ndarray): A 2D array of candidate coordinates, where each row represents a
                coordinate pair (latitude, longitude).
            current_coords (np.ndarray): A 2D array containing current coordinates of relevant entities
                (e.g., terminals, poles).
            added_candidates (np.ndarray): A 2D array of already added candidate coordinates, which should
                be excluded from the result.
            pole_indices (List[int]): A list of indices specifying the positions of poles within
                current_coords.
            terminal_indices (List[int]): A list of indices specifying the positions of terminal points
                within current_coords.

        Returns:
            np.ndarray: A filtered 2D array of candidate coordinates that satisfy all constraints.
        """
        if len(candidates) == 0:
            return np.empty((0, 2), dtype=float)

        original_count = len(candidates)

        # 1. Bounding-box filter (only terminals)
        if len(terminal_indices) > 0:
            terminal_coords = current_coords[terminal_indices]
            bb = self.compute_bounding_box(terminal_coords)

            lat_mask = (bb['min_lat'] <= candidates[:, 0]) & (candidates[:, 0] <= bb['max_lat'])
            lng_mask = (bb['min_lng'] <= candidates[:, 1]) & (candidates[:, 1] <= bb['max_lng'])
            mask_bb = lat_mask & lng_mask

            candidates = candidates[mask_bb]
            if self.request.debug >= 2:
                print(f"    BB filter removed {original_count - len(candidates)} candidates outside terminal bbox")

        # 2. Minimum pole-to-terminal distance
        min_pole_to_term = self.get_min_pole_to_term()

        if len(terminal_indices) > 0 and len(candidates) > 0:
            terminal_coords = current_coords[terminal_indices]
            dists_to_terminals = self.haversine_vec(candidates, terminal_coords)
            mask_term = np.min(dists_to_terminals, axis=1) >= min_pole_to_term
            candidates = candidates[mask_term]

        # 3. Minimum pole-to-pole distance (existing poles – none yet in disk phase, but kept for future-proofing)
        min_pole_to_pole = 5.0
        if len(pole_indices) > 0 and len(candidates) > 0:
            pole_coords = current_coords[pole_indices]
            dists_to_poles = self.haversine_vec(candidates, pole_coords)
            mask_poles = np.min(dists_to_poles, axis=1) >= min_pole_to_pole
            candidates = candidates[mask_poles]

        # 4. Remove already-added candidates
        if len(added_candidates) > 0 and len(candidates) > 0:
            ac_set = {tuple(np.round(c, decimals=6)) for c in added_candidates}
            candidates = np.array([
                c for c in candidates
                if tuple(np.round(c, decimals=6)) not in ac_set
            ])

        # 5. Final deduplication
        if len(candidates) > 0:
            candidates = np.unique(np.round(candidates, decimals=6), axis=0)

        if self.request.debug >= 1:
            kept = len(candidates)
            removed = original_count - kept
            print(f"filter_candidates: kept {kept}/{original_count} disk centers "
                  f"(removed {removed} — BB + min-distance + duplicates)")

        return candidates

    def _minimum_disk_cover(self, term_coords: np.ndarray, R: float) -> Tuple[np.ndarray, list]:
        """
        Determines an optimal set of disk centers that covers all specified terminal coordinates
        within a given radius, using a greedy set-cover algorithm with tie-breaking for optimality.

        The algorithm identifies candidate disk centers using pairwise intersections of disks, as well as
        source-biased circumference points for each terminal. Each candidate center is evaluated based on
        how many uncovered terminals it can cover, with tie-breaking based on minimizing overlap with already
        covered terminals or proximity to a source coordinate. This ensures an efficient coverage while
        remaining computationally feasible even for larger datasets.

        Debugging plots and logs are generated if debug levels are set higher than 1 in the request object,
        providing intermediate states like candidate generation, coverage matrix, and final selected centers.

        Examples of debug output include:
        - Candidate generation: pairwise intersections and source-biased points.
        - Building a coverage matrix using vectorized operations.
        - Coverage optimization with greedy set-cover and tie-breaking for optimal selection.

        Args:
        term_coords : np.ndarray
            A 2D array representing the terminal coordinates, where each row contains the latitude
            and longitude of a terminal.
        R : float
            The radius of the disk, in units consistent with the coordinates (e.g., meters for geospatial
            data using Haversine distance).

        Returns:
            Tuple[np.ndarray, list]
                A tuple containing two elements:
                - A 2D array of shape (m, 2), where `m` is the number of selected disk centers, and each row
                  represents the latitude and longitude of a disk center.
                - A list of descriptive names for each disk center, indicating its identifier (e.g.,
                  "DiskCenterPole 1", "DiskCenterPole 2").

        Raises:
            ValueError
                If no candidate centers are found or no disk centers can be determined to cover the terminals.

        """
        if len(term_coords) == 0:
            return np.empty((0, 2), dtype=float)

        term_coords = np.asarray(term_coords, dtype=float)
        n_term = len(term_coords)

        source_coord = self._coords[self._source_idx]

        # ─── 1. Generate candidate disk centers ─────────────────────────────
        candidates_list = []

        # (a) Pairwise two-circle candidates
        for i in range(n_term):
            for j in range(i + 1, n_term):
                pair_centers = self._two_circle_centers(term_coords[i], term_coords[j], R)
                candidates_list.extend(pair_centers)

        # (b) TWO source-biased circumference points per terminal
        for t in term_coords:
            circ_points = self._generate_biased_circumference_point(
                terminal=t,
                bias_point=source_coord,
                R=R
            )
            candidates_list.extend(circ_points)

        if not candidates_list:
            raise ValueError("No candidate centers found")

        candidates = np.array(candidates_list)
        candidates = np.unique(np.round(candidates, decimals=6), axis=0)

        if self.request.debug >= 2:
            print(f"  Disk cover: generated {len(candidates)} candidate centers "
                  f"({n_term}×2 source-biased circumference + pairwise)")

        # ─── 2. Vectorized coverage matrix ─────────────────────────────────
        dist_matrix = self.haversine_vec(candidates, term_coords)
        covers = dist_matrix <= R

        if self.request.debug >= 2:
            print(f"  Vectorized coverage matrix built: {covers.shape}")

        # ─── 3. Greedy Set-Cover with tie-breaking ────────────────
        uncovered_mask = np.ones(n_term, dtype=bool)
        selected_centers = []

        while np.any(uncovered_mask):
            # Primary score: number of NEW uncovered terminals covered
            new_coverage_counts = np.sum(covers[:, uncovered_mask], axis=1)
            max_new = np.max(new_coverage_counts)

            if max_new <= 0:
                break

            best_candidates_idx = np.where(new_coverage_counts == max_new)[0]

            if len(best_candidates_idx) == 1:
                chosen_idx = best_candidates_idx[0]
            else:
                # Secondary tie-breaker: minimize coverage of ALREADY covered terminals
                already_mask = ~uncovered_mask
                if np.any(already_mask):
                    overlap_counts = np.sum(
                        covers[best_candidates_idx][:, already_mask], axis=1
                    )
                    min_overlap = np.min(overlap_counts)
                    best_candidates_idx = best_candidates_idx[overlap_counts == min_overlap]

                # Tertiary tie-breaker: closest to source
                if len(best_candidates_idx) > 1:
                    dists_to_source = self.haversine_vec(
                        candidates[best_candidates_idx],
                        np.array([source_coord])
                    ).flatten()
                    chosen_idx = best_candidates_idx[np.argmin(dists_to_source)]
                else:
                    chosen_idx = best_candidates_idx[0]

            best_center = candidates[chosen_idx].copy()
            selected_centers.append(best_center)

            newly_covered = covers[chosen_idx] & uncovered_mask
            uncovered_mask[newly_covered] = False

            if self.request.debug >= 2:
                self._plot_disk_cover(
                    term_coords=term_coords,
                    disk_centers=np.array(selected_centers),
                    R=R,
                    candidates=candidates,
                    title=f"New Candidate Selected disk Cover – {n_term} terminals → {len(selected_centers)} disks (R={R:.1f}m)"
                )

            if self.request.debug >= 2:
                print(f"    Selected center {chosen_idx} → covers {max_new} new terminals "
                      f"({np.sum(uncovered_mask)} remaining)")

        selected_centers = np.array(selected_centers)

        # Debug plots – exactly as in original
        if self.request.debug >= 2:
            self._plot_disk_cover(
                term_coords=term_coords,
                disk_centers=selected_centers,
                R=R,
                candidates=candidates,
                title=f"Before filtered disk Cover – {n_term} terminals → {len(selected_centers)} disks (R={R:.1f}m)"
            )

        if self.request.debug >= 2:
            self._plot_disk_cover(
                term_coords=term_coords,
                disk_centers=selected_centers,
                R=R,
                candidates=candidates,
                title=f"Filtered disk Cover – {n_term} terminals → {len(selected_centers)} disks (R={R:.1f}m)"
            )

        if self.request.debug >= 2:
            self._plot_disk_cover(
                term_coords=term_coords,
                disk_centers=selected_centers,
                R=R,
                candidates=candidates,
                title=f"FINAL Disk Cover (source-biased) – {n_term} terminals → {len(selected_centers)} disks (R={R:.1f}m)"
            )

        if self.request.debug >= 1:
            print(f"  Disk cover complete: {len(selected_centers)} disks cover "
                  f"{n_term} terminals (R = {R:.1f} m)")

        if self.request.debug >= 1:
            print(f"   → Selected {len(selected_centers)} disk-center poles")

        if len(selected_centers) == 0:
            raise ValueError("No disk centers found.")

        disk_center_pole_coords = selected_centers.tolist()
        disk_center_names = [f"DiskCenterPole {i + 1}" for i in range(len(disk_center_pole_coords))]

        return disk_center_pole_coords, disk_center_names

    def _two_circle_centers(self, p1: np.ndarray, p2: np.ndarray, R: float) -> List[np.ndarray]:
        """
        Computes the centers of two possible circles that have a given radius and pass
        through two points on the Earth's surface. The calculation assumes a spherical
        Earth and uses the Haversine formula to measure distances.

        Args:
            p1 (np.ndarray): A 2D point (latitude, longitude) on the Earth's surface.
            p2 (np.ndarray): A 2D point (latitude, longitude) on the Earth's surface.
            R (float): The radius of the circle in meters.

        Returns:
            List[np.ndarray]: A list of two 2D points (latitude, longitude) representing
            the centers of the possible circles. If the two points cannot define two
            intersection circles with the given radius, an empty list is returned.

        Raises:
            ValueError: If the input points are invalid.
        """
        p1 = np.asarray(p1, dtype=float)
        p2 = np.asarray(p2, dtype=float)

        d_meters = self.haversine_meters(p1[0], p1[1], p2[0], p2[1])

        if d_meters > 2 * R or d_meters < 0.1:
            return []

        mid_lat = (p1[0] + p2[0]) / 2.0
        METERS_PER_DEG_LAT = 111111.0
        METERS_PER_DEG_LON = METERS_PER_DEG_LAT * np.cos(np.radians(mid_lat))

        dlat_m = (p2[0] - p1[0]) * METERS_PER_DEG_LAT
        dlon_m = (p2[1] - p1[1]) * METERS_PER_DEG_LON

        a = d_meters / 2.0
        hh = R * R - a * a
        if hh < 0:
            return []

        h = math.sqrt(hh)

        dir_vec = np.array([dlon_m, dlat_m])
        dir_unit = dir_vec / d_meters
        perp_unit = np.array([-dir_unit[1], dir_unit[0]])

        mid_m = np.array([dlon_m / 2, dlat_m / 2])

        c1_m = mid_m + h * perp_unit
        c2_m = mid_m - h * perp_unit

        c1 = np.array([
            p1[0] + c1_m[1] / METERS_PER_DEG_LAT,
            p1[1] + c1_m[0] / METERS_PER_DEG_LON
        ])
        c2 = np.array([
            p1[0] + c2_m[1] / METERS_PER_DEG_LAT,
            p1[1] + c2_m[0] / METERS_PER_DEG_LON
        ])

        return [c1, c2]

    def _generate_biased_circumference_point(self,
                                             terminal: np.ndarray,
                                             bias_point: np.ndarray,
                                             R: float) -> List[np.ndarray]:
        """
        Generates a list of points biased toward a specific direction on a circle's
        circumference in geographic space.

        This function calculates a set of points located on a circle's circumference,
        biased in the direction of a specified point. The terminal and bias points are
        expected to be in latitude-longitude coordinates. The function computes distances
        in meter space using a latitude-to-meter and longitude-to-meter conversion.

        Args:
            terminal (np.ndarray): A 2D array containing the latitude and longitude
                of the circle's center in degrees.
            bias_point (np.ndarray): A 2D array containing the latitude and longitude
                of the bias point in degrees.
            R (float): The radius of the circle in meters.

        Returns:
            List[np.ndarray]: A list of 2D arrays where each array contains the latitude
                and longitude of a biased point on the circle's circumference.
        """
        points = []
        vec = bias_point - terminal
        dist = np.linalg.norm(vec)

        R *= .99  # A bit of tolerance

        if dist < 1e-6:
            # fallback – two arbitrary points
            METERS_PER_DEG_LAT = 111111.0
            points.append(np.array([terminal[0] + R / METERS_PER_DEG_LAT, terminal[1]]))
            points.append(np.array([terminal[0] - R / METERS_PER_DEG_LAT, terminal[1]]))
            return points

        METERS_PER_DEG_LAT = 111111.0
        METERS_PER_DEG_LON = METERS_PER_DEG_LAT * np.cos(np.radians(terminal[0]))

        # Vector toward source (meter space)
        vec_m = np.array([vec[1] * METERS_PER_DEG_LON, vec[0] * METERS_PER_DEG_LAT])
        unit_m = vec_m / np.linalg.norm(vec_m)

        # Point 1: toward source
        offset_m = unit_m * R
        dlat = offset_m[1] / METERS_PER_DEG_LAT
        dlon = offset_m[0] / METERS_PER_DEG_LON
        points.append(np.array([terminal[0] + dlat, terminal[1] + dlon]))

        return points

    def generate_candidates(self,
                            coords,
                            cur_edges,
                            fermat_candidates,
                            terminal_cluster_centers,
                            added_candidates,
                            num_per_edge=2):
        """
        Generates a pool of candidate points based on provided coordinates, current edges, and
        several predefined candidate types.

        This method aims to build a composite pool of potential candidates by combining different
        sets of candidate points (e.g., Fermat points, adaptive Fermat points, cluster centers).
        The combined pool is then filtered based on specific constraints to ensure only valid
        candidate points are included. Optionally, a debug visualization of the generated
        candidate points can be displayed when debug mode is enabled.

        Args:
            coords (list): A list of coordinates representing the current points in the graph.
            cur_edges (object): The current set of edges in the graph.
            fermat_candidates (ndarray): An array of Fermat points to consider as candidates.
            terminal_cluster_centers (ndarray): An array of cluster centers to consider as candidates.
            added_candidates (ndarray): An array of coordinates corresponding to the previously
                added candidates.
            num_per_edge (int, optional): The number of intermediate candidates to generate per
                edge. Default is 2.

        Returns:
            ndarray: A filtered array of candidate coordinates, suitable for further processing
            or selection.

        Raises:
            None explicitly raised but downstream exceptions may occur depending on the validity
            of the input data.

        """

        n_terminals = len(self._terminal_indices) + 1  # +1 for source
        pole_indices = list(range(n_terminals, len(coords)))
        terminal_indices = list(range(n_terminals))

        adaptive_fermat = self.generate_adaptive_fermat_candidates(
            np.array(coords),
            terminal_indices,
            pole_indices
        )

        # === 2. Store ALL candidates in a dictionary (raw, before any masking) ===
        candidate_dict = {
            'Fermat Candidates': fermat_candidates,
            'Adaptive Fermat Candidates': adaptive_fermat,
            'Cluster Candidates': terminal_cluster_centers,
        }

        # === 4. Build final candidate pool by concatenating only the sets we actually use ===
        to_concat = [
            candidate_dict['Fermat Candidates'],
            candidate_dict['Adaptive Fermat Candidates'],
            candidate_dict['Cluster Candidates'],
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

    def _distances_from_new_point(self, current_coords: np.ndarray, new_point: np.ndarray) -> np.ndarray:
        """
        Haversine distances from a new point (kept for completeness).
        """
        new_point = np.array(new_point).reshape(1, 2)
        return self.haversine_vec(new_point, current_coords).flatten()

    def _build_directed_graph_with_new_point(
            self,
            nodes,
            base_dist_matrix: np.ndarray,
            cand_dists: np.ndarray,
            new_point_idx: int
    ) -> nx.DiGraph:
        """
        Builds a directed graph by incorporating a new point into the network and updating connections between source, poles,
        and terminals based on distance matrices and certain conditions. The graph represents a network for utility or
        infrastructure systems.

        Args:
            nodes (list): A list of node objects, where each node object must have the attributes index, name, type, lat,
                and lng. The type attribute determines whether a node is a "pole" or "terminal".
            base_dist_matrix (np.ndarray): A 2D square numpy array representing the base distance matrix between all points
                before considering the new point.
            cand_dists (np.ndarray): A 1D numpy array containing the distances from the new point to existing points in the
                network, including the source.
            new_point_idx (int): The index representing the new point being added to the network.

        Returns:
            nx.DiGraph: A directed graph where nodes and directed edges represent the network structure. Each edge has
                attributes such as weight, length, and voltage level based on the distances and network conditions.

        Raises:
            AttributeError: If input nodes lack required attributes like index, name, type, lat, or lng.
            ValueError: If the provided distance matrices or new point index have invalid dimensions or values.
        """
        DG = nx.DiGraph()

        source_idx = self._source_idx

        for node in nodes:
            DG.add_node(node.index,
                        name=node.name,
                        type=node.type,
                        lat=node.lat,
                        lng=node.lng)

        pole_indices = [i for i, node in enumerate(nodes) if node.type == "pole"]
        terminal_indices = [i for i, node in enumerate(nodes) if node.type == "terminal"]

        # 1. Source → all poles
        for p in pole_indices:
            if p == new_point_idx:
                d = cand_dists[source_idx]
            else:
                d = base_dist_matrix[source_idx, p]

            if 0.1 < d < 1e6:
                w = self.calc_edge_weight(d)
                DG.add_edge(source_idx, p, weight=w, length=d, voltage=self.request.voltageLevel)

        # 2. Pole ↔ Pole
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

        # 3. Poles → Terminals
        for p in pole_indices:
            for h in terminal_indices:
                if p == new_point_idx:
                    d = cand_dists[h]
                else:
                    d = base_dist_matrix[p, h]

                if 0.1 < d < 1e6:
                    w = self.calc_edge_weight(d, to_terminal=True)
                    DG.add_edge(p, h, weight=w, length=d, voltage=self.request.voltageLevel)

        # 4. Source → Terminals
        for h in terminal_indices:
            d = base_dist_matrix[source_idx, h]
            if 0.1 < d < 1e6:
                w = self.calc_edge_weight(d, to_terminal=True)
                DG.add_edge(source_idx, h, weight=w, length=d, voltage=self.request.voltageLevel)

        return DG

    def greedy_steiner(self, disk_center_pole_coords, disk_center_names):
        """
        Optimize disk-center pole placement using a greedy iterative approach.

        This method performs iterative optimization to connect disk-center poles
        to an existing source node while minimizing the total cost. It follows a
        greedy strategy to find and incorporate new candidates that improve the
        current cost. The optimization stops when no further improvements can be
        made or when the maximum iteration limit is reached.

        Args:
            disk_center_pole_coords (list[tuple[float, float]]): Coordinates of the central poles within disks, specified as a list of (x, y) tuples.
            disk_center_names (list[str]): Names corresponding to the disk-center poles.

        Returns:
            tuple:
                - current_mst (networkx.Graph): The resulting minimum spanning tree connecting the source and optimized poles.
                - current_coords (numpy.ndarray): Coordinates of the source and resulting poles.
                - current_names (list[str]): Names corresponding to the source and resulting poles.
        """
        if self.request.debug >= 1:
            print("Step 2: Greedy iterative optimization over disk centers "
                  f"(initialized with {len(disk_center_pole_coords)} disk-center poles)")

        # === Backbone only (source + disk centers) ===
        source_only = self._coords[[self._source_idx]]
        disk_array = np.array(disk_center_pole_coords) if len(disk_center_pole_coords) > 0 else np.empty((0, 2))

        current_coords = np.vstack([source_only, disk_array]) if len(disk_array) > 0 else source_only.copy()
        current_names = [self._names[self._source_idx]] + disk_center_names
        added_candidates = disk_array.copy()

        # Save terminals for later restoration
        original_terminal_indices = self._terminal_indices[:]
        self._terminal_indices = []  # ← terminals removed during greedy backbone opt

        # Initial MST on backbone
        backbone_nodes = self._build_nodes(current_coords, np.empty((0, 2)), current_names)
        G = self.build_graph_from_nodes(backbone_nodes)  # undirected complete graph
        current_mst = nx.minimum_spanning_tree(G, weight='weight')
        current_cost = self._compute_total_cost_poles_only(current_mst)

        if self.request.debug >= 1:
            print(f"  Initial backbone MST cost: {current_cost:.2f} €")
            self._plot_current_graph(current_mst, title="Initial MST – source + disk centers")

        # Greedy iteration constants
        MAX_ITERS = 12
        IMPROVEMENT_THRESHOLD = 0.5  # Minimum cost improvement to accept a candidate

        for it in range(MAX_ITERS):
            if self.request.debug >= 1:
                print(f"\n  Greedy iter {it + 1}/{MAX_ITERS} – current poles: {len(current_coords) - 1}")

            # Generate candidates on current backbone only
            fermat_cands = self.generate_proximity_fermat_candidates(
                current_coords, max_distance=120.0, max_candidates=80
            )
            adaptive_cands = self.generate_adaptive_fermat_candidates(
                current_coords, list(range(len(current_coords))), [], max_distance=100.0
            )
            cluster_cands = self.dbscan_generate_cluster_center_candidates(
                current_coords, eps_meters=50, min_samples=2
            )

            all_cands_list = [fermat_cands, adaptive_cands, cluster_cands]
            all_cands = np.vstack([c for c in all_cands_list if len(c) > 0]) if any(
                len(c) > 0 for c in all_cands_list) else np.empty((0, 2))

            # Filter duplicates / bounds
            all_cands = self.filter_candidates(
                candidates=all_cands,
                current_coords=current_coords,
                added_candidates=added_candidates,
                pole_indices=list(range(1, len(current_coords))),  # all except source
                terminal_indices=[]  # no terminals during backbone phase
            )

            if len(all_cands) == 0:
                if self.request.debug >= 1:
                    print("  No new candidates – stopping")
                break

            if self.request.debug >= 1:
                print(f"  Generated {len(all_cands)} candidate points this iteration")

            # === Test every candidate with a fresh MST ===
            best_cand = None
            best_cost = current_cost
            best_idx = -1

            for idx, cand in enumerate(all_cands):
                trial_coords = np.vstack([current_coords, cand])
                trial_names = current_names + [f"SteinerPole_{len(current_names)}"]
                trial_nodes = self._build_nodes(trial_coords, np.empty((0, 2)), trial_names)

                trial_DG = self.build_graph_from_nodes(trial_nodes)
                trial_mst = nx.minimum_spanning_tree(trial_DG, weight='weight')
                trial_cost = self._compute_total_cost_poles_only(trial_mst)

                if trial_cost < best_cost - IMPROVEMENT_THRESHOLD:
                    best_cost = trial_cost
                    best_cand = cand
                    best_idx = idx

                if self.request.debug >= 3:
                    self._plot_current_graph(trial_mst, added_points=[cand],
                                             title=f"Trial candidate {idx} – cost {trial_cost:.2f} €")

            # Accept best candidate if any improvement
            if best_cand is not None:
                added_candidates = np.vstack([added_candidates, best_cand])
                current_coords = np.vstack([current_coords, best_cand])
                current_names = current_names + [f"SteinerPole_{len(current_names)}"]

                # Rebuild MST with the new point
                backbone_nodes = self._build_nodes(current_coords, np.empty((0, 2)), current_names)
                DG = self.build_graph_from_nodes(backbone_nodes)
                current_mst = nx.minimum_spanning_tree(DG, weight='weight')
                current_cost = best_cost

                if self.request.debug >= 1:
                    print(f"    → BEST candidate accepted (index {best_idx}) – cost ↓ {current_cost:.2f} €")

                if self.request.debug >= 2:
                    self._plot_current_graph(current_mst, added_points=None,
                                             title=f"Backbone after iter {it + 1} – cost {current_cost:.2f} €")
            else:
                if self.request.debug >= 1:
                    print("  No improving candidate found – backbone converged")
                break

        # Restore original terminal indices for the caller
        self._terminal_indices = original_terminal_indices

        if self.request.debug >= 1:
            print(f"Greedy backbone converged – {len(current_coords) - 1} poles, final cost {current_cost:.2f} €")
            self._plot_current_graph(current_mst, title="Final Greedy Backbone MST")

        return current_mst, current_coords, current_names  # ← now returns coords + names too

    def attach_terminals(self, backbone_coords, backbone_names):
        """
        Attaches terminal nodes to the closest backbone nodes in the graph.

        The method enhances an existing graph representing a backbone network
        by connecting terminal points to it. It involves several sequential steps:
        1. Builds an initial directed graph for arborescence generation.
        2. Modifies the graph by splitting long backbone edges.
        3. Updates backbone node coordinates after graph modifications.
        4. Attaches terminal nodes to the closest available backbone nodes
           using updated coordinates.

        Args:
            backbone_coords: numpy.ndarray
                A 2D array containing coordinates of the backbone nodes in the format
                [[latitude, longitude], ...].
            backbone_names: list[str]
                A list of names corresponding to the backbone nodes.

        Returns:
            networkx.DiGraph
                A directed graph with the terminal nodes attached to the backbone network.
        """
        if self.request.debug >= 1:
            print(f"Attaching {len(self._terminal_indices)} terminals to closest backbone poles...")

        # ── Step A: Build proper arborescence (one-way edges from source) ──
        backbone_nodes = self._build_nodes(
            backbone_coords,
            np.empty((0, 2)),
            backbone_names
        )

        temp_DG = self.build_directed_graph_for_arborescence(backbone_nodes)
        best_graph = self._minimum_spanning_arborescence_w_attrs(temp_DG)

        # ── Step B: Split long backbone edges FIRST ────────────────────────
        if self.request.debug >= 1:
            print("   Splitting long backbone edges first...")
        best_graph = self.split_long_edges_with_coords(best_graph)

        if self.request.debug >= 2:
            self._plot_current_graph(best_graph, title="Backbone after splitting long edges (before attaching terminals)")

        # ── IMPORTANT: Update backbone_coords to include the new split poles ──
        # Extract current coordinates of ALL backbone nodes (source + poles)
        backbone_coords_updated = []
        for node_id, data in best_graph.nodes(data=True):
            if data['type'] in ('source', 'pole'):
                backbone_coords_updated.append([data['lat'], data['lng']])
        backbone_coords_updated = np.array(backbone_coords_updated, dtype=float)

        if self.request.debug >= 1:
            print(f"   Backbone now has {len(backbone_coords_updated)} nodes after splitting "
                  f"({len(backbone_coords_updated) - len(backbone_coords)} new intermediate poles)")

        # ── Step C: Attach terminals using the UPDATED coordinates ─────────
        for i, term_idx in enumerate(self._terminal_indices):
            term_coord = self._coords[term_idx]
            term_name = self._names[term_idx]

            # New terminal gets the next available index
            term_node_id = max(best_graph.nodes) + 1

            best_graph.add_node(
                term_node_id,
                name=term_name,
                type='terminal',
                lat=float(term_coord[0]),
                lng=float(term_coord[1])
            )

            # Find closest backbone node using the UPDATED coordinates
            dists = self.haversine_vec(
                np.array([term_coord]),
                backbone_coords_updated
            ).flatten()
            closest_idx = int(np.argmin(dists))
            dist = float(dists[closest_idx])

            weight = self.calc_edge_weight(dist, to_terminal=True)
            best_graph.add_edge(
                closest_idx,
                term_node_id,
                weight=weight,
                length=dist,
                voltage=self.request.voltageLevel
            )

            if self.request.debug >= 2:
                print(f"  Terminal {term_name} attached to node {closest_idx} "
                      f"(dist {dist:.1f}m)")

        if self.request.debug >= 1:
            print(f"   → Added {len(self._terminal_indices)} service-drop edges. "
                  f"Final graph has {best_graph.number_of_nodes()} nodes.")

            self._plot_current_graph(best_graph,
                                     added_points=self._coords[self._terminal_indices],
                                     title="Backbone (split) + Terminals Attached")

        return best_graph

    def _solve(self) -> nx.DiGraph:
        """
        Computes and returns the Steiner tree solution based on the given input data.

        This method implements a three-step process to solve the Steiner tree problem:
        1. Computes a minimum disk cover for a given set of terminal coordinates to
           reduce the problem complexity.
        2. Applies a greedy Steiner tree algorithm to construct an initial approximation
           of the tree structure.
        3. Performs post-solve gradient descent optimization to improve the resulting
           tree's configuration.

        Raises:
            ValueError: If no terminals were provided in the input coordinates.

        Returns:
            nx.DiGraph: A directed graph object representing the optimized Steiner tree
            with information such as edge lengths and node types.
        """
        coords = self._coords
        term_indices = self._terminal_indices
        R = self.get_max_pole_to_term()

        term_coords = coords[term_indices]

        if len(term_coords) == 0:
            raise ValueError("No terminals found in the input coordinates")

        # ── Step 1: Minimum disk cover ─────────────────────────────────────
        if self.request.debug >= 1:
            print(f"Step 1: Disk cover with R={R:.1f}m for {len(term_coords)} terminals")

        disk_center_pole_coords, disk_center_names = self._minimum_disk_cover(term_coords, R=R)

        final_mst, backbone_coords, backbone_names = self.greedy_steiner(
            disk_center_pole_coords, disk_center_names
        )

        # ── Attach terminals to closest poles (FIXED node indexing) ────────
        best_graph = self.attach_terminals(backbone_coords, backbone_names)

        # ── Step 3: Post-solve gradient descent optimization ────────────────
        if self.request.debug >= 1:
            print("Step 3: Post-solve gradient descent optimization")
        final_graph = self._post_solver_local_opt(best_graph)

        if self.request.debug >= 1:
            n_poles = sum(1 for _, d in final_graph.nodes(data=True) if d['type'] == 'pole')
            print(f"NewDiskBasedSteinerSolver finished – final poles: {n_poles}")
            print("Longest edge:", max([e[2]['length'] for e in final_graph.edges(data=True)]))
            self._plot_current_graph(final_graph, added_points=None, title="final_graph")

        return final_graph
