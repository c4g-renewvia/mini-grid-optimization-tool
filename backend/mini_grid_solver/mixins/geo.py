import math
import numpy as np
from typing import List, Tuple

class GeoMixin:
    """
    GeoMixin provides a set of utilities for geographical computation.

    This class includes methods for commonly used geographical calculations such as computing
    bounding boxes for a set of coordinates, calculating distances using the Haversine formula,
    determining intermediate points along a great-circle path, and handling coordinate similarity
    detection. It leverages efficient vectorized implementation where applicable for performance
    and can process both individual coordinate pairs and arrays of coordinates.

    Attributes:
        None
    """

    @staticmethod
    def compute_bounding_box(coords):
        """Compute the axis-aligned bounds of latitude/longitude coordinates.

        Args:
            coords: Array or list of latitude/longitude pairs.

        Returns:
            dict or None: Bounds with ``min_lat``, ``max_lat``, ``min_lng``, and
                ``max_lng`` keys, or None when the input is empty.

        Raises:
            ValueError: If coordinates are not an ``(n, 2)`` array.
        """
        if len(coords) == 0:
            return None

        # Convert to numpy array if it's a list
        coords = np.asarray(coords)

        if coords.ndim != 2 or coords.shape[1] != 2:
            raise ValueError("coords must be (n, 2) array or list of [lat, lon] pairs")

        min_lat = np.min(coords[:, 0])
        max_lat = np.max(coords[:, 0])
        min_lon = np.min(coords[:, 1])
        max_lon = np.max(coords[:, 1])

        return {
            'min_lat': float(min_lat),
            'max_lat': float(max_lat),
            'min_lng': float(min_lon),
            'max_lng': float(max_lon)
        }

    @staticmethod
    def is_duplicate(c, existing):
        """Check whether a coordinate matches any existing point within tolerance.

        Args:
            c: Coordinate to check.
            existing: Coordinates against which to check.

        Returns:
            bool: Whether ``c`` is within the comparison tolerance of a point.
        """
        return any(np.allclose(c, np.array(p), atol=1e-6) for p in existing)

    @staticmethod
    def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate great-circle distance between two points in meters.

        Args:
            lat1 (float): Latitude of the first point in degrees.
            lng1 (float): Longitude of the first point in degrees.
            lat2 (float): Latitude of the second point in degrees.
            lng2 (float): Longitude of the second point in degrees.

        Returns:
            float: Distance in meters.
        """
        R = 6371000.0  # Earth mean radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lng2 - lng1)

        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    @staticmethod
    def haversine_vec(A, B):
        """Compute pairwise Haversine distances between two coordinate arrays.

        Args:
            A: Array of latitude/longitude coordinates.
            B: Array of latitude/longitude coordinates.

        Returns:
            np.ndarray: Matrix of pairwise distances in meters.
        """
        # A, B: (n, 2) arrays of [lat, lon]
        lat1, lon1 = np.radians(A[:, 0]), np.radians(A[:, 1])
        lat2, lon2 = np.radians(B[:, 0]), np.radians(B[:, 1])
        dlat = lat2 - lat1[:, None]
        dlon = lon2 - lon1[:, None]
        a = np.sin(dlat / 2) ** 2 + np.cos(lat1[:, None]) * np.cos(lat2) * np.sin(dlon / 2) ** 2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        return 6371000 * c  # shape (n_candidates, n_buildings)

    def _get_distance_matrix(self, coords: np.ndarray) -> np.ndarray:
        """Return the cached pairwise distance matrix or calculate it.

        Args:
            coords (np.ndarray): Array of latitude/longitude coordinates.

        Returns:
            np.ndarray: Pairwise distances in meters.
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

    def _compute_coords_hash(self, coords: np.ndarray) -> str:
        """Create a string hash from coordinates rounded to six decimals.

        Args:
            coords (np.ndarray): Coordinates to hash.

        Returns:
            str: String representation of the rounded coordinate bytes.
        """
        # Round to 6 decimals (meter-level precision) and hash
        rounded = np.round(coords, decimals=6)
        return str(rounded.tobytes())

    def _great_circle_intermediates(
            self,
            lat1: float, lon1: float,
            lat2: float, lon2: float,
            max_length: float
    ) -> List[Tuple[float, float]]:
        """Generate intermediate coordinates between two geographic endpoints.

        Args:
            lat1 (float): Starting latitude in degrees.
            lon1 (float): Starting longitude in degrees.
            lat2 (float): Ending latitude in degrees.
            lon2 (float): Ending longitude in degrees.
            max_length (float): Maximum segment distance in meters.

        Returns:
            List[Tuple[float, float]]: Coordinates along the path, including
                both endpoints.
        """
        d = self.haversine_meters(lat1, lon1, lat2, lon2)
        if d <= max_length:
            return [(lat1, lon1), (lat2, lon2)]

        n_segments = math.ceil(d / max_length)
        n_inter = n_segments - 1

        points = [(lat1, lon1)]

        # Very simple linear interpolation in lat/lon space (good enough for short distances < few km)
        # For higher accuracy over long distances → use proper great-circle intermediate formula
        for k in range(1, n_inter + 1):
            frac = k / n_segments
            lat = lat1 + frac * (lat2 - lat1)
            lon = lon1 + frac * (lon2 - lon1)
            points.append((lat, lon))

        points.append((lat2, lon2))
        return points
