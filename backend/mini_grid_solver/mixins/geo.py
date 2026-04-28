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
        """
        Compute axis-aligned bounding box from array of [lat, lon] points.

        Args:
            coords: np.ndarray of shape (n, 2) where each row is [latitude, longitude]
                    or list of [lat, lon] pairs

        Returns:
            dict: {'min_lat': float, 'max_lat': float, 'min_lon': float, 'max_lon': float}
                  or None if input is empty/invalid
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
        return any(np.allclose(c, np.array(p), atol=1e-6) for p in existing)

    @staticmethod
    def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate the great-circle distance between two points on Earth in meters.

        Uses the Haversine formula to compute distance between two latitude/lnggitude pairs.

        Args:
            lat1 (float): Latitude of the first point in degrees.
            lng1 (float): longitude of the first point in degrees.
            lat2 (float): Latitude of the second point in degrees.
            lng2 (float): longitude of the second point in degrees.

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
        """
        Computes the Haversine distance between two sets of points.
        Args:
            A: (n, 2) array of [lat, lon]
            B: (n, 2) array of [lat, lon]
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
        """
        Computes or retrieves a cached distance matrix for the given set of coordinates.

        This method calculates the pairwise distances between a given set of coordinates
        using a vectorized implementation for efficiency. If the coordinates have not
        changed and the cache is valid, the cached distance matrix is returned.

        Args:
            coords (np.ndarray): A 2D array of geographical coordinates where each row
                represents a point (latitude, longitude).

        Returns:
            np.ndarray: A 2D array representing the distance matrix, where the value
                at position (i, j) corresponds to the distance between the i-th and
                j-th points.

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
        """
        Computes a unique hash for a given set of coordinates. The coordinates
        are rounded to six decimal places to ensure precision at the meter level,
        and then serialized as bytes to generate a hash string.

        Args:
            coords: A NumPy array representing the coordinates to hash.

        Returns:
            str: A hash string generated from rounded coordinates.
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
        """
        Calculates intermediate points on the great-circle path between two geographical coordinates.

        This function computes a series of intermediate latitude and longitude points along the
        great-circle path between two given geographical coordinates, ensuring that the
        distance between consecutive points does not exceed a specified maximum length.

        Args:
            lat1: Latitude of the starting point in decimal degrees.
            lon1: Longitude of the starting point in decimal degrees.
            lat2: Latitude of the ending point in decimal degrees.
            lon2: Longitude of the ending point in decimal degrees.
            max_length: Maximum allowed distance between consecutive points in meters.

        Returns:
            List of tuples representing the latitude and longitude of each point along
            the path, including the starting and ending points.
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
