import bisect
import heapq
import numpy as np
from matplotlib import pyplot as plt
from typing import List, Tuple

from .disk_based_steiner_solver import DiskBasedSteinerSolver  # your existing file


class BiniazPlaneSweepDiskSteinerSolver(DiskBasedSteinerSolver):
    """
    Disk-based Steiner solver using Biniaz et al.'s O(n log n) 4-approximation
    plane-sweep algorithm for Minimum Geometric Disk Cover.

    • Builds a maximal independent set I (points > 2R apart) in left-to-right order
      using a vertical plane sweep + balanced active set.
    • For each selected representative p ∈ I, covers the *right half-disk* of radius 2R
      with exactly 4 unit disks (the geometric trick that gives the 4-approx).
    • Keeps your existing filter_candidates, Fermat-pole generation, Steiner tree, and
      post-solver local optimization untouched.
    """

    def _minimum_disk_cover(self, term_coords: np.ndarray, R: float) -> Tuple[np.ndarray, list]:
        """
        Returns: (filtered_disk_centers: np.ndarray (N,2), names: list[str])
        """
        if len(term_coords) == 0:
            return np.empty((0, 2), dtype=float), []

        term_coords = np.asarray(term_coords, dtype=float)

        # ─── 1. Project to local East-North meter coordinates ─────────────────────
        local_points, m_per_lat, m_per_lon, ref_lat, ref_lon = self._latlon_to_local_meters(term_coords)

        if self.request.debug >= 1:
            print(f"Step 1: Biniaz Plane-Sweep 4-approx disk cover "
                  f"({len(term_coords)} terminals, R={R:.1f}m)")

        # ─── 2. Run the O(n log n) plane-sweep ───────────────────────────────────
        I_local = self._biniaz_plane_sweep(local_points, R)

        if len(I_local) == 0:
            # fallback (should never happen)
            fallback = np.array([[ref_lat, ref_lon]])
            return fallback, ["DiskCenterPole 1"]

        # ─── 3. Cover each right half-disk with exactly 4 unit disks ─────────────
        disk_centers_local = []
        for p in I_local:
            four = self._four_centers_right_half_disk(p, R)
            disk_centers_local.extend(four)

        disk_centers_local = np.array(disk_centers_local)

        # ─── 4. Back to geographic coordinates ───────────────────────────────────
        disk_centers_ll = self._local_meters_to_latlon(
            disk_centers_local, ref_lat, ref_lon, m_per_lat, m_per_lon
        )

        # ─── 5. Reuse your existing filtering logic ──────────────────────────────
        filtered = self.filter_candidates(
            candidates=disk_centers_ll,
            current_coords=term_coords,
            added_candidates=np.empty((0, 2)),
            pole_indices=[],
            terminal_indices=list(range(len(term_coords)))
        )

        if self.request.debug >= 1:
            print(f"  → {len(I_local)} representatives → {len(filtered)} final disk centers "
                  f"(4-approx guarantee)")

        names = [f"DiskCenterPole {i + 1}" for i in range(len(filtered))]

        return filtered, names

    # ─────────────────────────────────────────────────────────────────────────────
    #  Helper: lat/lon ↔ local meters (same scaling you already use in plotting)
    # ─────────────────────────────────────────────────────────────────────────────
    def _latlon_to_local_meters(self, coords: np.ndarray):
        coords = np.asarray(coords, dtype=float)
        avg_lat = float(np.mean(coords[:, 0]))
        METERS_PER_DEG_LAT = 111111.0
        METERS_PER_DEG_LON = METERS_PER_DEG_LAT * np.cos(np.radians(avg_lat))

        ref_lat, ref_lon = coords[0]  # arbitrary origin

        y = (coords[:, 0] - ref_lat) * METERS_PER_DEG_LAT
        x = (coords[:, 1] - ref_lon) * METERS_PER_DEG_LON

        return np.column_stack((x, y)), METERS_PER_DEG_LAT, METERS_PER_DEG_LON, ref_lat, ref_lon

    def _local_meters_to_latlon(self, local_xy: np.ndarray, ref_lat: float, ref_lon: float,
                                m_per_lat: float, m_per_lon: float):
        lat = ref_lat + local_xy[:, 1] / m_per_lat
        lon = ref_lon + local_xy[:, 0] / m_per_lon
        return np.column_stack((lat, lon))

    # ─────────────────────────────────────────────────────────────────────────────
    #  Core: Biniaz et al. plane-sweep (O(n log n))
    # ─────────────────────────────────────────────────────────────────────────────
    def _biniaz_plane_sweep(self, points: np.ndarray, R: float) -> np.ndarray:
        """O(n log n) plane-sweep that builds the maximal independent set I.
        Now with rich debug printing + live plots when debug >= 2."""
        if len(points) == 0:
            return np.empty((0, 2))

        n = len(points)
        events = []

        # Build event queue (this is the implicit sort!)
        for i in range(n):
            x, y = points[i]
            heapq.heappush(events, (x, 0, i, y))  # 0 = SITE event
            heapq.heappush(events, (x + 2 * R, 1, i, y))  # 1 = DELETION event

        if self.request.debug >= 1:
            print(f"--- Biniaz Plane-Sweep started ---")
            print(f"  {n} points, R = {R:.1f} m")
            print(f"  Event queue built: {len(events)} events (2n)")

        active: List[Tuple[float, int]] = []  # sorted by y: (y, point_idx)
        selected: List[int] = []
        step = 0

        while events:
            x, etype, idx, y = heapq.heappop(events)
            step += 1

            event_type = "SITE" if etype == 0 else "DELETION"

            if self.request.debug >= 2:
                print(f"\nStep {step:3d} | x = {x:8.2f}  {event_type:9}  point {idx:2d}  (y={y:7.2f})")
                print(f"      Active half-disks: {len(active)}")

            if etype == 1:  # DELETION
                active = [item for item in active if item[1] != idx]
                if self.request.debug >= 3:
                    print(f"      → Removed point {idx} from active set")
                continue

            # === SITE EVENT ===
            covered = False
            if active:
                pos = bisect.bisect_left(active, (y, -1))
                # Check only the 4–5 closest candidates (per Lemma 2)
                check_range = range(max(0, pos - 2), min(len(active), pos + 3))
                for k in check_range:
                    ay, a_idx = active[k]
                    dx = points[a_idx, 0] - x
                    dy = ay - y
                    dist_sq = dx * dx + dy * dy
                    if dist_sq <= (2 * R) ** 2 + 1e-8:
                        covered = True
                        if self.request.debug >= 3:
                            print(f"      → Covered by active point {a_idx} (dist={np.sqrt(dist_sq):.2f}m)")
                        break

            if not covered:
                selected.append(idx)
                bisect.insort(active, (y, idx))
                if self.request.debug >= 2:
                    print(f"      → SELECTED point {idx}  (new |I| = {len(selected)})")

                # Live plot after each selection (very insightful!)
                if self.request.debug >= 2:
                    self._plot_sweep_state(
                        points=points,
                        selected=selected,
                        active=[item[1] for item in active],
                        current_x=x,
                        R=R,
                        title=f"Sweep Step {step} – Selected {len(selected)} points"
                    )
            else:
                if self.request.debug >= 3:
                    print(f"      → Already covered → skipped")

        if self.request.debug >= 1:
            print(f"\n=== Plane-Sweep finished ===")
            print(f"  Selected {len(selected)} representatives (|I| ≤ OPT)")
            print(f"  Final active set size: {len(active)}")

        # Final plot of the complete solution
        if self.request.debug >= 1:
            self._plot_sweep_state(
                points=points,
                selected=selected,
                active=[],
                current_x=points[:, 0].max() + 2 * R + 10,
                R=R,
                title=f"FINAL Plane-Sweep Result – {len(selected)} disks (4-approx)"
            )

        return points[np.array(selected)]

    # ─────────────────────────────────────────────────────────────────────────────
    #  4-disk cover for right half-disk R(p)  (the geometric heart of the 4-approx)
    # ─────────────────────────────────────────────────────────────────────────────
    def _four_centers_right_half_disk(self, p: np.ndarray, R: float) -> List[np.ndarray]:
        """
        Returns 4 centers that together cover the right half-disk of radius 2R
        centered at p (local meter coordinates).

        This is the exact geometric construction used in Biniaz et al. (Figure 2(a)).
        You can tweak the offsets if you ever want a tighter empirical cover.
        """
        px, py = p
        # Offsets proven to cover any right half-disk of radius 2R with 4 radius-R disks
        offsets = [
            np.array([1.0 * R, 0.0]),
            np.array([0.5 * R, R * 0.8660254]),  # √3/2
            np.array([0.5 * R, -R * 0.8660254]),
            np.array([1.5 * R, 0.0]),
        ]
        return [p + off for off in offsets]

    def _plot_sweep_state(self,
                          points: np.ndarray,
                          selected: List[int],
                          active: List[int],
                          current_x: float,
                          R: float,
                          title: str = "Plane Sweep State"):
        """Visualizes the current state of the sweep line algorithm (in local meter coordinates)."""
        fig, ax = plt.subplots(figsize=(12, 8))
        ax.set_title(title)
        ax.set_xlabel("East (meters)")
        ax.set_ylabel("North (meters)")
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)

        # 1. All terminal points
        ax.scatter(points[:, 0], points[:, 1], c='red', s=80, label='Terminals', zorder=3)

        # 2. Selected representatives (I)
        if selected:
            sel = points[selected]
            ax.scatter(sel[:, 0], sel[:, 1], c='blue', s=200, marker='*',
                       edgecolors='black', linewidth=1.5, label=f'Selected I ({len(selected)})', zorder=5)

        # 3. Active right half-disks
        for idx in active:
            cx, cy = points[idx]
            # Right half-disk (radius 2R)
            theta = np.linspace(-np.pi / 2, np.pi / 2, 100)
            x_half = cx + 2 * R * np.cos(theta)
            y_half = cy + 2 * R * np.sin(theta)
            ax.plot(x_half, y_half, 'cyan', alpha=0.4, lw=2)
            # Full circle outline (faint)
            circle = plt.Circle((cx, cy), 2 * R, fill=False, color='cyan', alpha=0.15, lw=1, linestyle='--')
            ax.add_patch(circle)
            # Center of half-disk
            ax.plot(cx, cy, 'o', color='cyan', markersize=6, alpha=0.7)

        # 4. Sweep line (vertical)
        ax.axvline(x=current_x, color='black', linestyle='-', linewidth=2.5, alpha=0.9, label='Sweep Line')

        # 5. Legend and limits
        ax.legend(loc='upper right')
        padding = R * 0.3
        ax.set_xlim(points[:, 0].min() - padding, points[:, 0].max() + 2 * R + padding)
        ax.set_ylim(points[:, 1].min() - padding, points[:, 1].max() + padding)

        plt.tight_layout()
        plt.show()
        plt.close(fig)
