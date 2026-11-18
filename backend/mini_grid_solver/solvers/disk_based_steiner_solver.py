import math

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.patches import Ellipse

from .candidate_generation import CandidateGeneration
from ..utils.models import *
from ..utils.registry import register_solver

METERS_PER_DEG_LAT = 111111.0

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
        """Initialize the solver and its reusable geometry caches.

        Args:
            request: Input data and configuration for the solve operation.
        """
        super().__init__(request)
        # Caches from GreedyIterSteinerSolver for KDTree / Delaunay reuse
        self._delaunay_cache = None
        self._cached_coords = None
        self._kdtree_cache = None
        self._cached_kd_coords = None

    @staticmethod
    def get_input_params():
        """Return the parameters supported by the solver.

        Returns:
            An empty list because this solver exposes no additional parameters.
        """
        return []

    def _plot_disk_cover(self,
                         term_coords: np.ndarray,
                         disk_centers: np.ndarray,
                         R: float,
                         candidates: Optional[np.ndarray] = None,
                         title: str = "Minimum Disk Cover"):
        """Plot terminal coordinates, candidate centers, and selected coverage disks.

        Args:
            term_coords: Coordinates of the terminals.
            disk_centers: Coordinates of the selected disk centers.
            R: Disk radius in meters.
            candidates: Optional coordinates of all candidate centers.
            title: Plot title.
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

    def filter_disk_candidates(
            self,
            candidates: np.ndarray,
            terminal_coords: np.ndarray,
    ) -> np.ndarray:
        """Filter disk centers by terminal bounds, spacing, and duplication.

        Args:
            candidates: Candidate latitude-longitude coordinates.
            terminal_coords: Terminal latitude-longitude coordinates used for
                bounds and distance checks.

        Returns:
            Candidate coordinates that satisfy the filters.
        """
        if len(candidates) == 0:
            return np.empty((0, 2), dtype=float)

        original_count = len(candidates)

        # 1. Bounding-box filter (only terminals)
        bb = self.compute_bounding_box(terminal_coords)

        lat_mask = (bb['min_lat'] <= candidates[:, 0]) & (candidates[:, 0] <= bb['max_lat'])
        lng_mask = (bb['min_lng'] <= candidates[:, 1]) & (candidates[:, 1] <= bb['max_lng'])
        mask_bb = lat_mask & lng_mask

        candidates = candidates[mask_bb]
        if self.request.debug >= 2:
            print(f"    BB filter removed {original_count - len(candidates)} candidates outside terminal bbox")

        # 2. Minimum pole-to-terminal distance
        min_pole_to_term = self.get_min_pole_to_term()
        dists_to_terminals = self.haversine_vec(candidates, terminal_coords)
        mask_term = np.min(dists_to_terminals, axis=1) >= min_pole_to_term
        candidates = candidates[mask_term]

        # 5. Final deduplication
        if len(candidates) > 0:
            candidates = np.unique(np.round(candidates, decimals=6), axis=0)

        if self.request.debug >= 1:
            kept = len(candidates)
            removed = original_count - kept
            print(f"filter_candidates: kept {kept}/{original_count} disk centers "
                  f"(removed {removed} — BB + min-distance + duplicates)")

        return candidates

    @staticmethod
    def _latlon_to_meters(points: np.ndarray, ref_lat: float, ref_lon: float) -> np.ndarray:
        """Project latitude-longitude points into local east-north meters.

        Args:
            points: Latitude-longitude coordinates with shape ``(n, 2)``.
            ref_lat: Reference latitude in degrees.
            ref_lon: Reference longitude in degrees.

        Returns:
            Local east-north coordinates in meters.
        """
        METERS_PER_DEG_LON = METERS_PER_DEG_LAT * np.cos(np.radians(ref_lat))
        # points shape: (n, 2) → [lat, lon]
        north_m = (points[:, 0] - ref_lat) * METERS_PER_DEG_LAT
        east_m  = (points[:, 1] - ref_lon)  * METERS_PER_DEG_LON
        return np.column_stack((east_m, north_m))  # (n, 2) in meters

    @staticmethod
    def _meters_to_latlon(meter_points: np.ndarray, ref_lat: float, ref_lon: float) -> np.ndarray:
        """Convert local east-north coordinates back to latitude-longitude.

        Args:
            meter_points: Local east-north coordinates in meters with shape ``(n, 2)``.
            ref_lat: Reference latitude in degrees.
            ref_lon: Reference longitude in degrees.

        Returns:
            Latitude-longitude coordinates with shape ``(n, 2)``.
        """
        METERS_PER_DEG_LON = METERS_PER_DEG_LAT * np.cos(np.radians(ref_lat))
        dlat = meter_points[:, 1] / METERS_PER_DEG_LAT
        dlon = meter_points[:, 0] / METERS_PER_DEG_LON
        return np.column_stack((ref_lat + dlat, ref_lon + dlon))

    @staticmethod
    def circumcenter(p1, p2, p3):
        """Compute the circumcenter of three planar points.

        Args:
            p1: First point coordinate.
            p2: Second point coordinate.
            p3: Third point coordinate.

        Returns:
            The circumcenter coordinate, or ``None`` if the points are collinear.
        """
        d = 2 * (p1[0] * (p2[1] - p3[1]) +
                 p2[0] * (p3[1] - p1[1]) +
                 p3[0] * (p1[1] - p2[1]))
        if abs(d) < 1e-9:
            return None  # collinear / degenerate
        ux = ((p1[0] ** 2 + p1[1] ** 2) * (p2[1] - p3[1]) +
              (p2[0] ** 2 + p2[1] ** 2) * (p3[1] - p1[1]) +
              (p3[0] ** 2 + p3[1] ** 2) * (p1[1] - p2[1])) / d
        uy = ((p1[0] ** 2 + p1[1] ** 2) * (p3[0] - p2[0]) +
              (p2[0] ** 2 + p2[1] ** 2) * (p1[0] - p3[0]) +
              (p3[0] ** 2 + p3[1] ** 2) * (p2[0] - p1[0])) / d
        return np.array([ux, uy])

    @staticmethod
    def circumradius(p1, p2, p3):
        """Compute a triangle's circumradius using Heron's formula.

        Args:
            p1: First point coordinate.
            p2: Second point coordinate.
            p3: Third point coordinate.

        Returns:
            The circumradius, or infinity for a degenerate triangle.
        """
        a = np.linalg.norm(p2 - p1)
        b = np.linalg.norm(p3 - p2)
        c = np.linalg.norm(p1 - p3)
        s = (a + b + c) / 2.0
        area = np.sqrt(max(0.0, s * (s - a) * (s - b) * (s - c)))
        if area < 1e-9:
            return np.inf
        return (a * b * c) / (4 * area)

    @staticmethod
    def _circumcenter_and_radius_meters(pts_m: np.ndarray) -> Tuple[Optional[np.ndarray], float]:
        """Compute the circumcenter and radius for three meter-space points.

        Args:
            pts_m: Three planar point coordinates in meters.

        Returns:
            The center and radius, or ``(None, infinity)`` if the points are
            collinear.
        """
        p1, p2, p3 = pts_m
        d = 2 * (p1[0]*(p2[1] - p3[1]) + p2[0]*(p3[1] - p1[1]) + p3[0]*(p1[1] - p2[1]))
        if abs(d) < 1e-9:
            return None, np.inf  # collinear

        ux = ((p1[0]**2 + p1[1]**2) * (p2[1] - p3[1]) +
              (p2[0]**2 + p2[1]**2) * (p3[1] - p1[1]) +
              (p3[0]**2 + p3[1]**2) * (p1[1] - p2[1])) / d
        uy = ((p1[0]**2 + p1[1]**2) * (p3[0] - p2[0]) +
              (p2[0]**2 + p2[1]**2) * (p1[0] - p3[0]) +
              (p3[0]**2 + p3[1]**2) * (p2[0] - p1[0])) / d

        center_m = np.array([ux, uy])
        r_m = float(np.linalg.norm(center_m - p1))
        return center_m, r_m

    def generate_delaunay_circumcenter_candidates(self, term_coords: np.ndarray, R: float) -> List[np.ndarray]:
        """Generate Delaunay circumcenters whose meter-space radius is at most R.

        Args:
            term_coords: Terminal latitude-longitude coordinates.
            R: Maximum circumradius in meters.

        Returns:
            Circumcenter candidate coordinates in latitude-longitude.
        """
        if len(term_coords) < 3:
            return []

        term_coords = np.asarray(term_coords, dtype=float)

        # Use source or centroid as reference point for local projection (same style as your other methods)
        source_coord = self._coords[self._source_idx]
        ref_lat = float(source_coord[0])
        ref_lon = float(source_coord[1])

        # Project terminals to local meter coordinates
        term_m = self._latlon_to_meters(term_coords, ref_lat, ref_lon)

        # Reuse or compute Delaunay on the *meter* coordinates (correct geometry)
        if (self._delaunay_cache is None or
            self._cached_coords is None or
            not np.array_equal(self._cached_coords, term_coords)):  # still key on original coords for cache consistency
            from scipy.spatial import Delaunay
            self._delaunay_cache = Delaunay(term_m)          # ← note: Delaunay on meters
            self._cached_coords = term_coords.copy()

        cands_latlon = []
        for simplex in self._delaunay_cache.simplices:
            pts_m = term_m[simplex]                  # 3 points in meters
            pts_orig = term_coords[simplex]

            # Compute circumcenter + radius in meter space
            center_m, r_m = self._circumcenter_and_radius_meters(pts_m)

            if center_m is not None and r_m <= R + 1e-4:   # small tolerance
                # Project center back to lat/lon
                center_ll = self._meters_to_latlon(center_m.reshape(1, 2), ref_lat, ref_lon)[0]
                cands_latlon.append(center_ll)

        if self.request.debug >= 2:
            print(f"  Delaunay (metric): added {len(cands_latlon)} circumcenter candidates (r ≤ {R:.1f}m)")

        return cands_latlon

    def _minimum_disk_cover(self, term_coords: np.ndarray, R: float) -> Tuple[np.ndarray, list]:
        """Select a greedy disk cover with ties biased toward the growing source tree.

        The primary objective is to cover as many new terminals as possible per
        disk; ties favor centers closest to the source and previously selected
        centers. Debug mode can plot intermediate and final selections.

        Args:
            term_coords: Terminal coordinates to cover.
            R: Coverage radius in meters.

        Returns:
            The selected center coordinates and their generated names.

        Raises:
            ValueError: If no candidate centers are generated or pass filtering,
                or if no centers are selected.
        """
        if len(term_coords) == 0:
            return np.empty((0, 2), dtype=float)

        term_coords = np.asarray(term_coords, dtype=float)
        n_term = len(term_coords)
        source_coord = self._coords[self._source_idx]

        # ─── 1. Generate high-quality candidates ─────────────────────────────
        candidates_list = []

        # (a) Pairwise two-circle candidates
        for i in range(n_term):
            for j in range(i + 1, n_term):
                pair_centers = self._two_circle_centers(term_coords[i], term_coords[j], R)
                candidates_list.extend(pair_centers)

        # (b) Source-biased circumference points (more candidates for better tree options)
        for t in term_coords:
            circ_points = self._generate_biased_circumference_points(
                terminal=t,
                bias_point=source_coord,
                R=R,
                num_points=8,          # increased density
                angle_spread_deg=120   # wider spread
            )
            candidates_list.extend(circ_points)

        # (c) Optional geometrically perfect Delaunay circumcenters
        # delaunay_cands = self.generate_delaunay_circumcenter_candidates(term_coords, R)
        # candidates_list.extend(delaunay_cands)

        if not candidates_list:
            raise ValueError("No candidate centers found")

        candidates = self.filter_disk_candidates(np.array(candidates_list), term_coords)

        if len(candidates) == 0:
            raise ValueError("No valid disk candidates after filtering")

        if self.request.debug >= 1:
            print(f"  Tree-biased Disk Cover: generated {len(candidates)} candidates for {n_term} terminals")

        # ─── 2. Vectorized coverage matrix ─────────────────────────────────
        dist_matrix = self.haversine_vec(candidates, term_coords)
        covers = dist_matrix <= R + 0.1

        if self.request.debug >= 2:
            print(f"  Vectorized coverage matrix built: {covers.shape}")

        # ─── 3. Greedy Set-Cover with dynamic tree bias ────────────────────
        uncovered_mask = np.ones(n_term, dtype=bool)
        selected_centers = []
        current_tree_points = [source_coord.copy()]   # start with source only
        step = 0

        while np.any(uncovered_mask):
            step += 1
            # Primary score: number of NEW uncovered terminals covered
            new_coverage_counts = np.sum(covers[:, uncovered_mask], axis=1)
            max_new = int(np.max(new_coverage_counts))

            if max_new <= 0:
                break

            best_candidates_idx = np.where(new_coverage_counts == max_new)[0]

            if len(best_candidates_idx) == 1:
                chosen_idx = best_candidates_idx[0]
            else:
                # === STRONG TREE-LIKE TIE-BREAKER: closest to current partial tree ===
                dists_to_tree = self.haversine_vec(
                    candidates[best_candidates_idx],
                    np.array(current_tree_points)
                )
                min_dists_to_tree = np.min(dists_to_tree, axis=1)
                chosen_sub_idx = np.argmin(min_dists_to_tree)
                chosen_idx = best_candidates_idx[chosen_sub_idx]

                if self.request.debug >= 2:
                    print(f"    Tie-breaker (tree distance): chose candidate {chosen_idx} "
                          f"(dist to tree = {min_dists_to_tree[chosen_sub_idx]:.1f}m)")

            best_center = candidates[chosen_idx].copy()

            # Jiggle (your improved version with revert-if-no-gain)
            best_center = self._jiggle_disk_center(
                best_center,
                term_coords,
                R=R,
                uncovered_mask=uncovered_mask.copy()  # focus on still-uncovered terminals
            )

            # Re-compute coverage using the (possibly jiggled) position
            new_covers = self._compute_coverage_mask(best_center, term_coords, R)
            newly_covered = new_covers & uncovered_mask

            selected_centers.append(best_center)
            uncovered_mask[newly_covered] = False

            # Add this center to the growing tree for future bias
            current_tree_points.append(best_center.copy())

            if self.request.debug >= 2:
                print(f"    Selected + jiggled center {chosen_idx} → covers {np.sum(newly_covered)} new terminals "
                      f"({np.sum(uncovered_mask)} remaining)")

                # ─── STEP-BY-STEP DEBUG PLOT (so you can watch selection happen) ───
                self._plot_disk_cover(
                    term_coords=term_coords,
                    disk_centers=np.array(selected_centers),
                    R=R,
                    candidates=candidates,
                    title=f"Tree-Biased Disk Cover – Step {step} "
                          f"({n_term} terminals → {len(selected_centers)} disks, R={R:.1f}m)"
                )

        selected_centers = np.array(selected_centers)

        # ─── FINAL DEBUG PLOTS (exactly like original) ─────────────────────
        if self.request.debug >= 2:
            self._plot_disk_cover(
                term_coords=term_coords,
                disk_centers=selected_centers,
                R=R,
                candidates=candidates,
                title=f"Before filtered disk Cover – {n_term} terminals → {len(selected_centers)} disks (R={R:.1f}m)"
            )

            self._plot_disk_cover(
                term_coords=term_coords,
                disk_centers=selected_centers,
                R=R,
                candidates=candidates,
                title=f"Filtered disk Cover – {n_term} terminals → {len(selected_centers)} disks (R={R:.1f}m)"
            )

            self._plot_disk_cover(
                term_coords=term_coords,
                disk_centers=selected_centers,
                R=R,
                candidates=candidates,
                title=f"FINAL Tree-Biased Disk Cover – {n_term} terminals → {len(selected_centers)} disks (R={R:.1f}m)"
            )

        if self.request.debug >= 1:
            print(f"  Tree-biased disk cover complete: {len(selected_centers)} disks cover "
                  f"{n_term} terminals (R = {R:.1f} m)")
            print(f"   → Selected {len(selected_centers)} disk-center poles")

        if len(selected_centers) == 0:
            raise ValueError("No disk centers found.")

        disk_center_pole_coords = selected_centers.tolist()
        disk_center_names = [f"DiskCenterPole {i + 1}" for i in range(len(disk_center_pole_coords))]

        return disk_center_pole_coords, disk_center_names

    def _two_circle_centers(self, p1: np.ndarray, p2: np.ndarray, R: float) -> List[np.ndarray]:
        """Find radius-R circle centers passing through two geographic points.

        Args:
            p1: First latitude-longitude coordinate.
            p2: Second latitude-longitude coordinate.
            R: Circle radius in meters.

        Returns:
            The two possible center coordinates, or an empty list if no solution
            exists.
        """
        p1 = np.asarray(p1, dtype=float)
        p2 = np.asarray(p2, dtype=float)

        d_meters = self.haversine_meters(p1[0], p1[1], p2[0], p2[1])

        if d_meters > 2 * R or d_meters < 0.1:
            return []

        mid_lat = (p1[0] + p2[0]) / 2.0
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

    def _generate_biased_circumference_points(
            self,
            terminal: np.ndarray,
            bias_point: np.ndarray,
            R: float,
            num_points: int = 5,
            angle_spread_deg: float = 25.0
    ) -> List[np.ndarray]:
        """Generate radius-R points around a terminal biased toward a reference point.

        Args:
            terminal: Terminal latitude-longitude coordinate.
            bias_point: Coordinate toward which points are biased.
            R: Circumference radius in meters.
            num_points: Number of points to generate.
            angle_spread_deg: Total angular spread in degrees.

        Returns:
            Generated latitude-longitude coordinates.
        """
        points = []
        vec = bias_point - terminal
        dist = np.linalg.norm(vec)

        if dist < 1e-6:
            # fallback - two arbitrary points
            points.append(np.array([terminal[0] + R / METERS_PER_DEG_LAT, terminal[1]]))
            points.append(np.array([terminal[0] - R / METERS_PER_DEG_LAT, terminal[1]]))
            return points

        METERS_PER_DEG_LON = METERS_PER_DEG_LAT * np.cos(np.radians(terminal[0]))

        # unit vector toward source (in meter space)
        vec_m = np.array([vec[1] * METERS_PER_DEG_LON, vec[0] * METERS_PER_DEG_LAT])
        unit_m = vec_m / np.linalg.norm(vec_m)

        # main direction in radians
        main_angle = np.arctan2(unit_m[1], unit_m[0])

        for i in range(num_points):
            angle_offset = np.deg2rad((i - (num_points - 1) / 2) * (angle_spread_deg / (num_points - 1)))
            angle = main_angle + angle_offset

            offset_m = R * np.array([np.cos(angle), np.sin(angle)])
            dlat = offset_m[1] / METERS_PER_DEG_LAT
            dlon = offset_m[0] / METERS_PER_DEG_LON

            points.append(np.array([terminal[0] + dlat, terminal[1] + dlon]))

        return points

    def _compute_coverage_mask(self, center: np.ndarray, term_coords: np.ndarray, R: float) -> np.ndarray:
        """Return the mask of terminals covered by a disk center.

        Args:
            center: Disk-center latitude-longitude coordinate.
            term_coords: Terminal coordinates.
            R: Coverage radius in meters.

        Returns:
            A boolean array indicating which terminals are within the radius.
        """
        if len(term_coords) == 0:
            return np.array([], dtype=bool)
        dists = self.haversine_vec(center.reshape(1, 2), term_coords)
        return dists[0] <= R + 0.1

    def _jiggle_disk_center(
            self,
            initial_center_ll: np.ndarray,
            term_coords: np.ndarray,
            R: float,
            uncovered_mask: Optional[np.ndarray] = None,
            max_steps: int = 8,
            step_size_m: float = 25.0
    ) -> np.ndarray:
        """Adjust a selected center if doing so strictly improves its coverage.

        The adjustment respects the minimum pole-to-terminal spacing; otherwise,
        the original center is retained.

        Args:
            initial_center_ll: Initial center in latitude-longitude coordinates.
            term_coords: Terminal coordinates.
            R: Coverage radius in meters.
            uncovered_mask: Optional mask restricting coverage counts to uncovered
                terminals.
            max_steps: Maximum number of adjustment steps.
            step_size_m: Maximum movement per step in meters.

        Returns:
            The adjusted center if its coverage improves, otherwise the original.
        """
        if len(term_coords) == 0:
            return initial_center_ll.copy()

        # ─── INITIAL COVERAGE COUNT (before any jiggling) ─────────────────────
        initial_center_ll = np.asarray(initial_center_ll, dtype=float).copy()
        initial_covered_mask = self._compute_coverage_mask(initial_center_ll, term_coords, R)
        if uncovered_mask is not None:
            initial_count = np.sum(initial_covered_mask & uncovered_mask)
        else:
            initial_count = np.sum(initial_covered_mask)

        min_dist = self.get_min_pole_to_term()

        current_ll = initial_center_ll.copy()
        ref_lat = float(current_ll[0])
        ref_lon = float(current_ll[1])

        term_m = self._latlon_to_meters(term_coords, ref_lat, ref_lon)
        # FIXED: start from the actual initial center in meter space (original code started at [0,0]!)
        center_m = self._latlon_to_meters(current_ll.reshape(1, 2), ref_lat, ref_lon)[0].copy()

        for _ in range(max_steps):
            dists_m = np.linalg.norm(term_m - center_m[None, :], axis=1)
            covered_mask = dists_m <= R + 1.0

            active_mask = covered_mask
            if uncovered_mask is not None:
                active_mask = covered_mask & uncovered_mask

            n_active = np.sum(active_mask)
            if n_active <= 1:  # trivial case
                break

            covered_m = term_m[active_mask]
            centroid_m = np.mean(covered_m, axis=0)

            direction = centroid_m - center_m
            dist_to_centroid = np.linalg.norm(direction)
            if dist_to_centroid < 1.0:
                break

            move_dist = min(step_size_m, dist_to_centroid * 0.8)
            proposed_m = center_m + (direction / dist_to_centroid) * move_dist

            # ─── ENFORCE min_pole_to_term CONSTRAINT ───
            proposed_ll = self._meters_to_latlon(proposed_m.reshape(1, 2), ref_lat, ref_lon)[0]
            dists_to_terms = self.haversine_vec(proposed_ll.reshape(1, 2), term_coords).flatten()
            min_achieved = float(np.min(dists_to_terms))

            if min_achieved < min_dist:
                # Find closest terminal (in meter space for accuracy)
                closest_idx = int(np.argmin(np.linalg.norm(term_m - proposed_m[None, :], axis=1)))
                closest_term_m = term_m[closest_idx]

                vec_away = proposed_m - closest_term_m
                norm = np.linalg.norm(vec_away)
                if norm > 1e-6:
                    # Project exactly to the allowed boundary + small buffer
                    proposed_m = closest_term_m + (vec_away / norm) * (min_dist + 2.0)

            # Accept the (possibly corrected) position
            center_m = proposed_m

        # ─── FINAL CONVERSION + COVERAGE CHECK ─────────────────────────────
        new_center_ll = self._meters_to_latlon(center_m.reshape(1, 2), ref_lat, ref_lon)[0]

        final_covered_mask = self._compute_coverage_mask(new_center_ll, term_coords, R)
        if uncovered_mask is not None:
            final_count = np.sum(final_covered_mask & uncovered_mask)
        else:
            final_count = np.sum(final_covered_mask)

        if final_count > initial_count:
            if self.request.debug >= 2:
                print(f"    Jiggle improved coverage: {initial_count} → {final_count}")
            return new_center_ll
        else:
            if self.request.debug >= 2:
                print(f"    Jiggle did not increase coverage ({final_count} <= {initial_count}), reverting to original")
            return initial_center_ll

    def generate_candidates(self,
                            coords,
                            cur_edges,
                            fermat_candidates,
                            terminal_cluster_centers,
                            added_candidates,
                            num_per_edge=2):
        """Combine and filter candidate coordinates from supported generators.

        Args:
            coords: Coordinates of current graph nodes.
            cur_edges: Current graph edges.
            fermat_candidates: Fermat-point candidates.
            terminal_cluster_centers: Cluster-center candidates.
            added_candidates: Previously added candidate coordinates.
            num_per_edge: Number of intermediate candidates requested per edge.

        Returns:
            The filtered candidate coordinates.
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
        n_terminals = len(self._terminal_indices) + 1

        candidates = self.filter_candidates(
            candidates=candidates,
            terminal_coords=coords,
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
        """Calculate distances from a new coordinate to existing coordinates.

        Args:
            current_coords: Existing latitude-longitude coordinates.
            new_point: New latitude-longitude coordinate.

        Returns:
            A flattened array of haversine distances in meters.
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
        """Build the directed candidate graph with an additional point.

        Args:
            nodes: Node objects with index, name, type, latitude, and longitude.
            base_dist_matrix: Distances between existing nodes.
            cand_dists: Distances from the new point to existing nodes.
            new_point_idx: Index of the new point in ``nodes``.

        Returns:
            The graph with eligible source, pole, and terminal connections.
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

    def greedy_steiner_for_backbone(self, disk_center_pole_coords, disk_center_names):
        """Greedily improve the source-and-pole backbone with Steiner candidates.

        Args:
            disk_center_pole_coords: Coordinates of disk-center poles.
            disk_center_names: Names corresponding to the disk-center poles.

        Returns:
            A tuple of the backbone MST, its node coordinates, and their names.
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
            print(f"  Initial backbone MST cost: {current_cost:.2f} $")
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
                                             title=f"Trial candidate {idx} – cost {trial_cost:.2f} $")

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
                    print(f"    → BEST candidate accepted (index {best_idx}) – cost ↓ {current_cost:.2f} $")

                if self.request.debug >= 2:
                    self._plot_current_graph(current_mst, added_points=None,
                                             title=f"Backbone after iter {it + 1} – cost {current_cost:.2f} $")
            else:
                if self.request.debug >= 1:
                    print("  No improving candidate found – backbone converged")
                break

        # Restore original terminal indices for the caller
        self._terminal_indices = original_terminal_indices

        current_mst = self.rename_poles(current_mst)

        if self.request.debug >= 1:
            print(f"Greedy backbone converged – {len(current_coords) - 1} poles, final cost {current_cost:.2f} $")
            self._plot_current_graph(current_mst, title="Final Greedy Backbone MST")

        return current_mst, current_coords, current_names  # ← now returns coords + names too

    def attach_terminals(self, backbone_coords, backbone_names):
        """Attach each terminal to its closest node on the prepared backbone.

        Args:
            backbone_coords: Latitude-longitude coordinates of backbone nodes.
            backbone_names: Names corresponding to the backbone nodes.

        Returns:
            The directed graph with terminals attached, long edges split, and
            unnecessary pole branches pruned.
        """
        if self.request.debug >= 1:
            print(f"\nAttaching {len(self._terminal_indices)} terminals to closest backbone poles...")

        # Step 1: Build initial arborescence from backbone (source + disk/steiner poles)
        backbone_nodes = self._build_nodes(
            backbone_coords,
            np.empty((0, 2)),
            backbone_names
        )

        temp_DG = self.build_directed_graph_for_arborescence(backbone_nodes)
        best_graph = self._minimum_spanning_arborescence_w_attrs(temp_DG)

        if self.request.debug >= 1:
            print(f"   Initial backbone has {best_graph.number_of_nodes()} nodes "
                  f"({sum(1 for _, d in best_graph.nodes(data=True) if d['type'] == 'pole')} poles)")

        # ── CRITICAL FIX: Split long backbone edges FIRST ─────────────────────
        if self.request.debug >= 1:
            print("   Splitting long backbone edges (pole-to-pole and source-to-pole)...")

        best_graph = self.split_long_edges_w_poles(best_graph)

        # ── Extract UPDATED backbone coordinates after splitting ─────────────
        # (source + poles only — terminals not added yet)
        current_backbone_coords = []
        current_backbone_node_ids = []

        for node_id, data in list(best_graph.nodes(data=True)):
            if data.get('type') in ('source', 'pole'):
                current_backbone_coords.append([data['lat'], data['lng']])
                current_backbone_node_ids.append(node_id)

        current_backbone_coords = np.array(current_backbone_coords, dtype=float)

        if self.request.debug >= 1:
            added_poles = len(current_backbone_coords) - len(backbone_coords)
            print(f"   Backbone after splitting: {len(current_backbone_coords)} nodes "
                  f"(+{added_poles} new intermediate poles)")

        # ── Attach each terminal to the closest backbone node ───────────
        for term_idx in self._terminal_indices:
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

            # Find closest backbone node using the *updated* coordinates
            dists = self.haversine_vec(
                np.array([term_coord]),
                current_backbone_coords
            ).flatten()

            closest_local_idx = int(np.argmin(dists))
            closest_node_id = current_backbone_node_ids[closest_local_idx]
            dist = float(dists[closest_local_idx])

            weight = self.calc_edge_weight(dist, to_terminal=True)

            best_graph.add_edge(
                closest_node_id,
                term_node_id,
                weight=weight,
                length=dist,
                voltage=self.request.voltageLevel
            )

            if self.request.debug >= 2:
                print(f"  Terminal {term_name} attached to node {closest_node_id} "
                      f"(dist {dist:.1f}m)")

        # Final cleanup to keep the graph clean
        best_graph = self.prune_dead_end_pole_branches(best_graph)
        best_graph = self.rename_poles(best_graph)

        if self.request.debug >= 1:
            total_poles = sum(1 for _, d in best_graph.nodes(data=True) if d['type'] == 'pole')
            print(f"   → Attached {len(self._terminal_indices)} terminals. "
                  f"Final graph: {best_graph.number_of_nodes()} nodes, {total_poles} poles")
            self._plot_current_graph(
                best_graph,
                added_points=self._coords[self._terminal_indices],
                title=f"Backbone + Terminals Attached (${self._compute_total_cost(best_graph):.2f})"
            )

        return best_graph

    def _solve(self) -> Union[nx.Graph, nx.DiGraph]:
        """Build a disk-cover Steiner solution and optimize its directed tree.

        Raises:
            ValueError: If the input contains no terminals, or if disk cover
                generation cannot produce valid centers.

        Returns:
            The optimized directed Steiner tree.
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

        # ── Step 2: Attach terminals to closest poles (FIXED node indexing) ────────
        final_mst, backbone_coords, backbone_names = self.greedy_steiner_for_backbone(
            disk_center_pole_coords, disk_center_names
        )

        best_graph = self.attach_terminals(backbone_coords, backbone_names)

        # ── Step 3: Post-solve gradient descent optimization ────────────────
        # Extra Final Optimizations
        if self.request.debug >= 1:
            print("Step 3: Post-solve gradient descent optimization")
        final_graph = self._post_solver_opt(best_graph)

        nodes = [Node(index=x[0], **x[1]) for x in final_graph.nodes(data=True)]
        final_graph = self.build_graph_from_nodes(nodes, directed=True)
        final_graph = self._minimum_spanning_arborescence_w_attrs(final_graph)

        final_graph = self._post_solver_opt(final_graph)

        if self.request.debug >= 1:
            n_poles = sum(1 for _, d in final_graph.nodes(data=True) if d['type'] == 'pole')
            print(f"NewDiskBasedSteinerSolver finished – final poles: {n_poles}")
            edge_lengths = [e[2]['length'] for e in final_graph.edges(data=True)]
            print("Longest edge:", max(edge_lengths))
            print("Shortest edge:", min(edge_lengths))
            self._plot_current_graph(final_graph, added_points=None, title="final_graph")

        return final_graph
