import math
from typing import List, Optional

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.patches import Ellipse

from .base_mini_grid_solver import BaseMiniGridSolver
from .registry import register_solver


@register_solver
class DiskBasedSteinerSolver(BaseMiniGridSolver):
    """
    This algorithm attempts to solve the Steiner problem using a disk-based approach.

    Step 1: Identify the disk centers by covering the terminal nodes with the least number of disks possible
    Step 2: Run a standard Steiner solver on the remaining points
    Step 3: Post solve gradient decent optimization

    Args:
    """

    def __init__(self, request):
        super().__init__(request)

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

        This function generates a plot displaying terminals, selected disk centers, and optional candidate centers,
        alongside their respective coverage areas. It utilizes matplotlib for visualization and requires coordinates
        and other input data formatted as NumPy arrays. The function is intended for debug purposes and will not
        execute if the debug level of the request object is below the specified threshold.

        Parameters:
            term_coords (np.ndarray): A 2D array of terminal coordinates given as [latitude, longitude].
            disk_centers (np.ndarray): A 2D array of the coordinates of selected disk centers as [latitude, longitude].
            R (float): The radius of the disks in meters.
            candidates (Optional[np.ndarray]): Optional 2D array of candidate coordinates as [latitude, longitude].
            title (str): The title to display at the top of the plot. Default is "Minimum Disk Cover".

        Raises:
            None
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
        Filters a list of candidate coordinates based on specific constraints such as
        bounding box, minimum distances, and duplication checks.

        This method processes a list of candidate geographic coordinates and determines
        which candidates should be retained based on several filtering criteria, including
        proximity to terminals, poles, and previously added candidates. The filtering is
        performed step-by-step in the following order: bounding box constraints, minimum
        pole-to-terminal and pole-to-pole distances, removal of already-added candidates,
        and final deduplication.

        Parameters:
            candidates: np.ndarray
                A 2D array of candidate coordinates where each row represents a latitude-longitude
                pair (lat, lng).
            current_coords: np.ndarray
                A 2D array of current coordinates of existing elements, such as terminals and poles.
            added_candidates: np.ndarray
                A 2D array of already-added candidate coordinates to ensure no duplicate inclusion.
            pole_indices: List[int]
                A list of indices referencing poles within current_coords.
            terminal_indices: List[int]
                A list of indices referencing terminals within current_coords.

        Returns:
            np.ndarray
                A 2D array of filtered candidate coordinates (latitude-longitude pairs) that passed
                all filtering stages.
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

    def _generate_circumference_candidates(self,
                                           center: np.ndarray,
                                           R: float,
                                           n_points: int = 6) -> np.ndarray:
        """
        Generates candidate points on the circumference of a circle specified by a center and a radius.

        This method calculates a set of evenly distributed points on the circle's circumference based on a given
        center and radius. The circumference is approximated using the input number of points, with adjustments
        handled to ensure a minimum number of points. The calculation considers the geographic scaling of latitude
        and longitude in meters to determine offsets and converts them back to degree coordinates.

        Parameters:
        center : np.ndarray
            A 2-element array representing the center of the circle in latitude and longitude coordinates.
        R : float
            Radius of the circle in meters.
        n_points : int, optional
            Number of points to generate along the circle's circumference. Defaults to 6. Minimum value is clamped to 3.

        Returns:
        np.ndarray
            A 2D array where each row represents a point's latitude and longitude on the circle's
            circumference. The number of rows corresponds to `n_points`.
        """
        if n_points < 3:
            n_points = 6

        angles = np.linspace(0, 2 * np.pi, n_points, endpoint=False)

        # Local scaling at this latitude
        METERS_PER_DEG_LAT = 111111.0
        METERS_PER_DEG_LON = METERS_PER_DEG_LAT * np.cos(np.radians(center[0]))

        # Offsets in meters
        dx_m = R * np.cos(angles)  # longitude direction
        dy_m = R * np.sin(angles)  # latitude direction

        # Convert back to degrees
        dlat = dy_m / METERS_PER_DEG_LAT
        dlon = dx_m / METERS_PER_DEG_LON

        points = np.column_stack([center[0] + dlat, center[1] + dlon])
        return points

    def _two_circle_centers(self, p1: np.ndarray, p2: np.ndarray, R: float) -> List[np.ndarray]:
        """
        Determines the two possible centers of two intersecting circles based on their radii and positions.

        This function calculates the two possible centers of overlap for two circles
        on a spherical surface determined by the given radius and positions of their centers.
        The calculation is based on the haversine distance between the two points and resolves
        the geometric relations required to locate the intersection points. If the circles
        do not intersect or are too close to each other within a threshold, the function
        returns an empty list.

        Parameters:
            p1 (np.ndarray): The latitude and longitude coordinates of the first circle, given as a numpy array.
            p2 (np.ndarray): The latitude and longitude coordinates of the second circle, given as a numpy array.
            R (float): The radius of the circles in meters.

        Returns:
            List[np.ndarray]: A list containing two numpy arrays, each representing the latitude
                              and longitude coordinates of the two possible centers of the intersecting circles.
                              Returns an empty list if the circles do not intersect or are degenerate.
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
        Generates points on the circumference of a circle, biased towards the source.

        This function calculates points on the circumference of a circle centered at the
        terminal point, with a given radius, that are biased in the direction of the source
        point. The computation takes into account the curvature of the Earth by using
        latitude and longitude coordinates and converting these into meter-space for more
        precise calculations.

        Parameters:
        terminal (np.ndarray): The center of the circle in latitude and longitude
                                [lat, lon].
        bias_point (np.ndarray): The point in latitude and longitude [lat, lon] towards
                             which the circle is biased.
        R (float): The radius of the circle in meters.

        Returns:
        List[np.ndarray]: A list of points on the circle's circumference in the format
                          [lat, lon].
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

    def _minimum_disk_cover(self, term_coords: np.ndarray, R: float) -> np.ndarray:
        """
        Computes a minimum disk cover for a given set of terminal coordinates, based on a specified disk radius.

        This method identifies disk centers that collectively cover all given terminal points, iteratively selecting points
        to minimize the number of disks required. Tie-breaking logic is applied to favor disks closer to the source coordinate.

        Parameters:
            term_coords (np.ndarray): A 2D array of shape (n, 2), where each row represents the (latitude, longitude)
                                      coordinates of a terminal. Must not be empty.
            R (float): Radius of the disks in the same units as the coordinates.

        Returns:
            np.ndarray: A 2D array of coordinates representing the selected disk centers. Each row specifies the
                        (latitude, longitude) of a disk center.

        Raises:
            None
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
            coverage_counts = np.sum(covers[:, uncovered_mask], axis=1)
            max_count = np.max(coverage_counts)

            if max_count <= 0:
                break

            # Get all candidates that achieve the max count
            best_candidates_idx = np.where(coverage_counts == max_count)[0]

            if len(best_candidates_idx) == 1:
                chosen_idx = best_candidates_idx[0]
            else:
                # Tie-breaker: prefer the candidate closest to the source
                dists_to_source = self.haversine_vec(
                    candidates[best_candidates_idx],
                    np.array([source_coord])
                ).flatten()
                chosen_idx = best_candidates_idx[np.argmin(dists_to_source)]

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
                print(f"    Selected center {chosen_idx} → covers {max_count} new terminals "
                      f"({np.sum(uncovered_mask)} remaining)")

        selected_centers = np.array(selected_centers)

        # Debug plots (exactly as you had them)
        if self.request.debug >= 2:
            self._plot_disk_cover(
                term_coords=term_coords,
                disk_centers=selected_centers,
                R=R,
                candidates=candidates,
                title=f"Before filtered disk Cover – {n_term} terminals → {len(selected_centers)} disks (R={R:.1f}m)"
            )

        filtered_centers = self.filter_candidates(
            candidates=selected_centers,
            current_coords=term_coords,
            added_candidates=np.empty((0, 2)),
            pole_indices=[],
            terminal_indices=list(range(n_term))
        )

        if self.request.debug >= 2:
            self._plot_disk_cover(
                term_coords=term_coords,
                disk_centers=filtered_centers,
                R=R,
                candidates=candidates,
                title=f"Filtered disk Cover – {n_term} terminals → {len(filtered_centers)} disks (R={R:.1f}m)"
            )

        if self.request.debug >= 1:
            print(f"  Disk cover complete: {len(filtered_centers)} disks cover "
                  f"{n_term} terminals (R = {R:.1f} m)")

        if self.request.debug >= 2:
            self._plot_disk_cover(
                term_coords=term_coords,
                disk_centers=filtered_centers,
                R=R,
                candidates=candidates,
                title=f"FINAL Disk Cover (source-biased) – {n_term} terminals → {len(filtered_centers)} disks (R={R:.1f}m)"
            )

        return filtered_centers

    def _solve(self) -> nx.DiGraph:
        """
        Solves the Disk-Based Steiner problem by computing a directed graph that satisfies
        length constraints and connectivity requirements for the given set of input coordinates.

        The algorithm follows several steps:
        1. Finds a minimal disk cover for the terminal coordinates within the given constraints.
        2. Computes a Steiner tree considering the source and disk centers as candidates for poles.
        3. Performs post-solving optimizations such as pruning non-essential branches and applying
           local optimization to refine the final graph.

        Raises
        ------
        ValueError
            If no terminal coordinates are provided in the input dataset.

        Returns
        -------
        nx.DiGraph
            A directed graph representing the optimal solution, where nodes correspond to poles
            (including potential Steiner poles and disk center poles), and directed edges represent
            the connections under the specified constraints.
        """

        coords = self._coords
        term_indices = self._terminal_indices
        R = self.get_max_pole_to_pole()

        term_coords = coords[term_indices]

        if len(term_coords) == 0:
            raise ValueError("No terminals found in the input coordinates")

        # ── Step 1: Minimum disk cover ─────────────────────────────────────
        if self.request.debug >= 1:
            print(f"Step 1: Disk cover with R={R:.1f}m for {len(term_coords)} terminals")

        disk_centers = self._minimum_disk_cover(term_coords, R=R)  # returns (k, 2) array

        if self.request.debug >= 1:
            print(f"   → Selected {len(disk_centers)} disk-center poles")

        # ── Step 2: Standard Steiner on source + disk centers ──────────────
        # We add the disk centers as candidate poles to the original point set.
        # The base arborescence + prune will automatically:
        #   • connect terminals to the nearest disk center (service drops)
        #   • connect the disk centers to the source (with possible extra Steiner poles)
        if len(disk_centers) == 0:
            raise ValueError("No disk centers found.")

        candidate_poles = disk_centers.tolist()
        candidate_names = [f"DiskCenterPole {i + 1}" for i in range(len(candidate_poles))]

        full_nodes = self._build_nodes(
            coords,  # original source + terminals
            candidate_poles,  # new poles from disks
            self._names + candidate_names
        )

        DG = self.build_directed_graph_for_arborescence(full_nodes)
        if self.request.debug >= 1:
            self._plot_current_graph(DG, added_points=None, title="DG")
        arbo_graph = self._minimum_spanning_arborescence_w_attrs(DG)
        if self.request.debug >= 1:
            self._plot_current_graph(arbo_graph, added_points=None, title="arbo_graph")
        pruned_graph = self.prune_dead_end_pole_branches(arbo_graph)
        if self.request.debug >= 1:
            self._plot_current_graph(pruned_graph, added_points=None, title="pruned_graph")
        steinerized_graph = self.split_long_edges_with_coords(pruned_graph)
        if self.request.debug >= 1:
            self._plot_current_graph(steinerized_graph, added_points=None, title="steinerized_graph")

        # ── Step 3: Post-solve gradient descent + cleanup
        final_graph = self._post_solver_local_opt(steinerized_graph)

        if self.request.debug >= 1:
            n_poles = sum(1 for _, d in final_graph.nodes(data=True) if d['type'] == 'pole')
            print(f"DiskBasedSteinerSolver finished – final poles: {n_poles}")

            self._plot_current_graph(final_graph, added_points=None, title="final_graph")

        return final_graph
