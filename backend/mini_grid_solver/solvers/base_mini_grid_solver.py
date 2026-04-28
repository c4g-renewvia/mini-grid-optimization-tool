# optimizers/base.py
import math
from abc import ABC, abstractmethod
from typing import Tuple, Union

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib import collections as mc
from scipy.optimize import minimize

from ..utils.models import *

MAX_EDGE_DIST_PENALTY = 10000


class BaseMiniGridSolver(ABC):
    """
    Abstract base class for MiniGrid power network optimizers.

    Subclasses implement different algorithms/heuristics while agreeing on:
      - Input  = SolverRequest
      - Output = SolverResult (edges, nodes, metrics, optional debug)

    No assumptions are made about:
      - Use of candidate poles
      - MST / Steiner tree / arborescence
      - Voltage assignment logic
      - Edge fragmentation / pole placement density
      - Cost model details
    """

    def __init__(self, request: SolverRequest):
        self.request = request
        self._nodes: Optional[List[Node]] = None
        self._edges: Optional[List[Edge]] = None
        self._graph: Optional[Union[nx.Graph, nx.DiGraph]] = None
        self._coords: Optional[np.ndarray] = None
        self._source_idx: Optional[int] = None
        self._terminal_indices: Optional[List[int]] = None
        self._pole_indices: Optional[List[int]] = None
        self._names: Optional[List[str]] = None
        self._costs: Optional[Costs] = None

        self._dist_matrix = None  # Will store the current (n x n) distance matrix
        self._cached_coords_hash = None  # Simple way to detect when points changed

    # ─── Static Helper methods ───────────────────────────────────────────────
    @staticmethod
    def get_input_params() -> List[SolverInputParams]:
        """
        Example:
            [
            SolverInputParams(
                name="n_points",
                type="int",
                default=10,
                min=2,
                max=100,
                description='Number of points'
            ),
            SolverInputParams(
                name="steinerize",
                type="bool",
                default=False,
                min=False,
                max=True,
                description='Steinerize the graph',
            ),
            SolverInputParams(
                name="algorithm",
                type="str",
                default="",
                options=['algo1', "algo2"],
                description='Which algorith to use',

            )
        ]
        """
        return []

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

    def get_min_pole_to_term(self) -> float:
        if self.request.voltageLevel == 'low':
            return self.request.lengthConstraints.low.poleToTerminalMinLength
        else:
            return self.request.lengthConstraints.high.poleToTerminalMinLength

    def get_max_pole_to_pole(self) -> float:
        if self.request.voltageLevel == 'low':
            return self.request.lengthConstraints.low.poleToPoleMaxLength
        else:
            return self.request.lengthConstraints.high.poleToPoleMaxLength

    def get_max_pole_to_term(self) -> float:
        if self.request.voltageLevel == 'low':
            return self.request.lengthConstraints.low.poleToTerminalMaxLength
        else:
            return self.request.lengthConstraints.high.poleToTerminalMaxLength

    def get_cost_per_meter(self) -> float:
        if self.request.voltageLevel == "low":
            return self.request.costs.lowVoltageCostPerMeter
        else:
            return self.request.costs.highVoltageCostPerMeter

    @staticmethod
    def _plot_current_graph(graph, added_points=None, title="Current tree after candidate addition", filename=None):
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.set_title(title)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_aspect('equal')

        # 1. Safely map indices to their true coordinates
        coord_dict = {}
        source_coords = []
        term_coords = []
        pole_coords = []
        for idx, node_data in graph.nodes(data=True):
            coord_dict[idx] = (node_data['lat'], node_data['lng'])
            if node_data['type'] == "source":
                source_coords.append(coord_dict[idx])
            elif node_data['type'] == "terminal":
                term_coords.append(coord_dict[idx])
            elif node_data['type'] == "pole":
                pole_coords.append(coord_dict[idx])

        # Plot Source
        if source_coords:
            sc = np.array(source_coords)
            ax.scatter(sc[:, 1], sc[:, 0], c='blue', s=120, marker='s', label='Source')

        # Plot Terminals
        if term_coords:
            tc = np.array(term_coords)
            ax.scatter(tc[:, 1], tc[:, 0], c='red', s=80, marker='o', label='Terminals')

        # Plot Existing poles
        if pole_coords:
            pc = np.array(pole_coords)
            ax.scatter(pc[:, 1], pc[:, 0], c='black', s=60, marker='^', label='Poles')

        # Highlight newly added candidate
        if added_points is not None:
            added_points = np.array(added_points)
            if len(added_points) > 0:
                ax.scatter(added_points[:, 1], added_points[:, 0], c='orange', s=200, marker='*', edgecolor='black',
                           linewidth=1.5,
                           label='Newly added pole')

        # Plot edges
        edge_lines = []
        for u, v in graph.edges():
            if u in coord_dict and v in coord_dict:
                pt_u = [coord_dict[u][1], coord_dict[u][0]]  # [lng, lat]
                pt_v = [coord_dict[v][1], coord_dict[v][0]]
                edge_lines.append([pt_u, pt_v])

        if edge_lines:
            lc = mc.LineCollection(edge_lines, colors='green', linewidths=1.5, alpha=0.7)
            ax.add_collection(lc)

        # ─── NEW: Display node indices on the graph ─────────────────────────
        for idx, (lat, lon) in coord_dict.items():
            node_type = graph.nodes[idx].get('type', 'unknown')
            if node_type == 'source':
                color = 'blue'
                offset = (0.00003, 0.00003)
                fontsize = 9
            elif node_type == 'terminal':
                color = 'darkred'
                offset = (0.00003, 0.00003)
                fontsize = 8
            else:  # pole
                color = 'black'
                offset = (0.00003, 0.00003)
                fontsize = 8

            ax.text(
                lon + offset[0],
                lat + offset[1],
                str(idx),
                fontsize=fontsize,
                color=color,
                ha='left',
                va='bottom',
                bbox=dict(boxstyle="round,pad=0.1", facecolor="white", alpha=0.75, edgecolor='none'),
                zorder=10
            )

        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        if filename:
            plt.savefig(filename, dpi=150, bbox_inches='tight')
            plt.close(fig)
            print(f"Saved plot: {filename}")
        else:
            plt.show()
            plt.close(fig)

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

    # ─── Core abstract methods ───────────────────────────────────────────────

    @abstractmethod
    def _solve(self) -> Union[nx.DiGraph, nx.Graph]:
        """
        Abstract method to be implemented by subclasses.
        Solves the given input data and returns the resulting graph, list of nodes, and an array of results.

        :param input_tuple: The input data containing necessary information to process the solution. The
            structure and data type of the input must align with the expected requirements of the solution.
        :return: A directed or undirected graph representing the computed solution:
            - A ``nx.(Di)Graph`` object representing the computed graph.
        """
        pass

    def solve(self) -> SolverResult:
        """
        Main entry point: take the request → produce full SolverResult.

        This is the only method most users / tests should call directly.

        """

        # Parse input and input into abstract solver method
        self.parse_and_validate_input()

        # Pass to implemented solver
        graph = self._solve()

        return self.build_solver_result(graph)

    # ─── Helpful common utilities (can be used or overridden) ────────────────
    def reindex_nodes(self, nodes):
        new_nodes = []
        for i, node in enumerate(nodes):
            new_nodes.append(Node(
                index=i,
                lat=node.lat,
                lng=node.lng,
                name=node.name,
                type=node.type,
            ))

        return new_nodes

    def _build_nodes(self, coords, candidates, names):
        """
        Builds a list of Node objects based on the input coordinates, node names,
        and candidate poles.

        Args:
            coords: numpy.ndarray
                A 2D array containing latitude and longitude coordinates of original
                nodes. Each row corresponds to a node, where the first column is the
                latitude and the second is the longitude.
            candidates: list[tuple[float, float]]
                A list of tuples, where each tuple contains the latitude and longitude
                of candidate pole nodes.
            names: list[str]
                A list of names corresponding to the original nodes.

        Returns:
            list[Node]:
                A list of Node objects created based on the provided input, where each
                node has its index, coordinates, type, and name assigned.
        """
        nodes = []
        n_orig = len(coords)

        for i in range(n_orig):
            if i == self._source_idx:
                t: Literal['source', 'pole', 'terminal'] = "source"
            else:
                if "pole" in names[i].lower():
                    t = "pole"
                else:
                    t = "terminal"
            nodes.append(Node(
                index=i,
                lat=float(coords[i, 0]),
                lng=float(coords[i, 1]),
                type=t,
                name=names[i],
            ))

        offset = n_orig
        for j, (lat, lon) in enumerate(candidates, start=offset):
            nodes.append(Node(
                index=j,
                lat=float(lat),
                lng=float(lon),
                type="pole",
            ))

        return nodes

    def _normalize_node_order(self):
        """Force consistent ordering: Source (0) → Terminals → Poles.
        Re-assigns dense contiguous indices 0,1,2,...
        This eliminates the 'index X out of bounds for axis 1 with size Y' errors
        when re-uploading solved KMLs."""
        if not self._nodes:
            return

        # Group nodes by type (preserving original relative order within groups)
        source_nodes = [n for n in self._nodes if n.type == "source"]
        terminal_nodes = [n for n in self._nodes if n.type == "terminal"]
        pole_nodes = [n for n in self._nodes if n.type == "pole"]

        # Rebuild in the desired order
        ordered_nodes = source_nodes + terminal_nodes + pole_nodes

        # Re-index everything densely
        self._nodes = []
        self._terminal_indices = []
        self._pole_indices = []
        self._source_idx = 0

        for i, node in enumerate(ordered_nodes):
            new_node = Node(
                index=i,
                lat=node.lat,
                lng=node.lng,
                name=node.name or f"{node.type} {i}",
                type=node.type,
            )
            self._nodes.append(new_node)

            if node.type == "terminal":
                self._terminal_indices.append(i)
            elif node.type == "pole":
                self._pole_indices.append(i)

        # Rebuild derived arrays
        self._coords = np.array([get_node_coord_tuple(n) for n in self._nodes], dtype=np.float64)
        self._names = [n.name for n in self._nodes]

        if self.request.debug >= 1:
            print(f"✅ Normalized node order → {len(source_nodes)} source + "
                  f"{len(terminal_nodes)} terminals + {len(pole_nodes)} poles")

    def parse_and_validate_input(self):
        """
        Parses and validates the input data required for the operation. Ensures that
        the input nodes, costs, and related data meet the necessary requirements and
        formats them for subsequent processing steps.

        Raises:
            ValueError: If the number of nodes is less than 2.
            ValueError: If more than one source node is found in the input.
            ValueError: If no source node is found in the input.
            ValueError: If there are fewer than two coordinates after normalization.
        """
        nodes = self.request.nodes
        costs: Costs = self.request.costs.model_copy()

        if len(nodes) < 2:
            raise ValueError("At least 2 nodes required")

        coords = np.array([get_node_coord_tuple(n) for n in nodes], dtype=np.float64)
        names = [n.name for n in nodes]

        source_idx = None
        for i, n in enumerate(nodes):
            if n.type == "source":
                if source_idx is not None:
                    raise ValueError("Only one source allowed")
                source_idx = i

        if source_idx is None:
            raise ValueError("No source found")
        else:
            source_idx = int(source_idx)

        terminal_indices = [n.index for n in nodes if n.type == "terminal"]
        pole_indices = [n.index for n in nodes if n.type == "pole"]

        self._nodes = nodes
        self._edges = self.request.edges
        self._coords = coords
        self._names = names
        self._costs = costs

        self._source_idx = source_idx
        self._terminal_indices = terminal_indices
        self._pole_indices = pole_indices

        # ────── Normalize ordering and indices ──────
        self._normalize_node_order()

        # Build a graph of given nodes or edges
        self._graph = self.build_graph_from_nodes(self._nodes)

        if len(self._coords) < 2:
            raise ValueError("Need at least source + 1 terminal")

        return

    def calc_edge_weight(self, length, to_terminal=False):
        """
        Cost of wire and pole
        Args:
            length: length of edge
            voltage: cost to use for edge. key in self.request.solver dict,
                e.g. "lowVoltageCostPerMeter" or "highVoltageCostPerMeter"
            to_terminal: if destination is terminal, then subtract the length of pole to house constraint from extra pole calculation

        Returns:

        """
        voltage_cost = self.get_cost_per_meter()

        pole_cost = self.request.costs.poleCost

        # Cost of the wire
        weight = length * voltage_cost

        # Cost of intermediate support poles for long spans
        pole_to_pole_constraint = self.get_max_pole_to_pole()

        if to_terminal:
            pole_to_terminal_constraint = self.get_max_pole_to_term()
            length -= pole_to_terminal_constraint

        extra_poles = max(0, math.ceil(length / pole_to_pole_constraint) - 1)
        weight += extra_poles * pole_cost

        return weight

    def _compute_total_cost(self, graph):
        """
        Compute total cost (wire + poles) + HUGE penalties for BOTH:
          - edges that are TOO LONG
          - terminal edges that are TOO SHORT (poleToTerminalMinLength)
        """
        # 1. Wire + intermediate support-pole costs
        wire_cost = sum(d['weight'] for u, v, d in graph.edges(data=True))

        # 2. Pole costs
        num_poles = sum(1 for idx, data in graph.nodes(data=True) if data['type'] == "pole")
        pole_cost = self._costs.poleCost

        total = wire_cost + (num_poles * pole_cost)

        # 3. Constraint violation penalty (NOW COVERS MIN + MAX)
        violation_penalty = 0.0
        for u, v, data in graph.edges(data=True):
            length = data.get("length", 0.0)
            voltage = data.get("voltage", "low")

            u_type = graph.nodes[u]['type']
            v_type = graph.nodes[v]['type']
            is_terminal_edge = (u_type == "terminal" or v_type == "terminal")

            if is_terminal_edge:
                max_len = self.get_max_pole_to_term()
                min_len = self.get_min_pole_to_term()
            else:
                max_len = self.get_max_pole_to_pole()
                min_len = 0.5  # pole-pole has no meaningful minimum

            # Too long → massive linear penalty (same as before)
            if length > max_len + 0.1:
                excess = length - max_len
                violation_penalty += MAX_EDGE_DIST_PENALTY * excess

            # Too short on terminal edges → also massive penalty
            if is_terminal_edge and length < min_len:
                shortfall = (min_len - length) * 1000
                violation_penalty += MAX_EDGE_DIST_PENALTY * shortfall * 50

        return total + violation_penalty

    def _compute_total_cost_poles_only(self, graph):
        """
        Compute total cost (wire + poles) + HUGE penalties for BOTH:
          - edges that are TOO LONG
          - terminal edges that are TOO SHORT (poleToTerminalMinLength)
          - No violation penalty
        """
        # 1. Wire + intermediate support-pole costs
        wire_cost = sum(d['weight'] for u, v, d in graph.edges(data=True))

        # 2. Pole costs
        num_poles = sum(1 for idx, data in graph.nodes(data=True) if data['type'] == "pole")
        pole_cost = self._costs.poleCost

        total = wire_cost + (num_poles * pole_cost)

        return total

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

    def build_graph_from_nodes(self, nodes, edges=None, include_terminals=False, directed=False) -> Union[
        nx.DiGraph, nx.Graph]:
        """
        Builds a graph representation from a given set of nodes and edges or calculates
        edges dynamically based on coordinates and a distance matrix if edges are not
        provided.

        This method creates a NetworkX graph object. Nodes in the graph are initialized
        with metadata such as name, type, latitude, and longitude, while edges are
        either provided explicitly or computed dynamically. When edges are computed,
        their weights and other attributes are derived from distances and specific
        cost calculations.

        Args:
            nodes (list[Node]): List of Node objects representing the graph's nodes.
                Node objects must have attributes such as `index`, `name`, `type`,
                `lat`, and `lng`.
        """
        G = nx.DiGraph() if directed else nx.Graph()
        nodes = self.reindex_nodes(nodes)
        for node in nodes:
            G.add_node(node.index)
            G.nodes[node.index]["name"] = node.name
            G.nodes[node.index]["type"] = node.type
            G.nodes[node.index]["lat"] = node.lat
            G.nodes[node.index]["lng"] = node.lng

        coords = np.array([get_node_coord_tuple(n) for n in nodes])

        dist_matrix = self.compute_distance_matrix(coords)
        if edges is None:
            for i in G.nodes:
                i_type = G.nodes[i]["type"]
                for j in G.nodes:
                    if i == j:
                        continue
                    j_type = G.nodes[j]["type"]

                    if ((i_type == "source" and j_type == "pole") or
                            (i_type == "pole" and j_type == "pole") or
                            (i_type == "pole" and j_type == "terminal") or
                            include_terminals):
                        G.add_edge(i, j)
                        d = dist_matrix[i, j]
                        weight = self.calc_edge_weight(d, to_terminal=(j in self._terminal_indices))
                        G.edges[i, j]["weight"] = weight
                        G.edges[i, j]["length"] = d
                        G.edges[i, j]["voltage"] = self.request.voltageLevel

        else:
            for edge in edges:
                start, end = edge.start, edge.end
                i, j = start.index, end.index
                G.add_edge(i, j)
                G.edges[i, j]["weight"] = self.calc_edge_weight(edge.lengthMeters,
                                                                to_terminal=(j in self._terminal_indices))
                G.edges[i, j]["length"] = edge.lengthMeters
                G.edges[i, j]["voltage"] = self.request.voltageLevel

        return G

    def build_directed_graph_for_arborescence(self, nodes) -> nx.DiGraph:
        """
        Constructs a directed graph representing an arborescence structure. The graph is built
        based on nodes representing poles and terminals, with specific rules governing connections
        between the source node, poles, and terminals. The graph edges are weighted based on
        distance and voltage level.

        Args:
            nodes (list): A list of node objects representing poles and terminals. Each node object
                should have attributes such as `index`, `type`, `name`, `lat`, `lng`, and
                `coord_tuple`.

        Returns:
            nx.DiGraph: A directed graph (DiGraph) representing the arborescence structure, where
            nodes represent the input nodes and edges represent connections between them.
        """

        DG = nx.DiGraph()

        pole_indices = [n.index for n in nodes if n.type == "pole"]
        terminal_indices = [n.index for n in nodes if n.type == "terminal"]
        source_idx = nodes[self._source_idx].index

        all_points = np.array([get_node_coord_tuple(n) for n in nodes])

        if hasattr(self, '_get_distance_matrix'):
            dist_matrix = self._get_distance_matrix(all_points)
        else:
            dist_matrix = self.compute_distance_matrix(all_points)

        for n in nodes:
            DG.add_node(n.index, name=n.name, type=n.type, lat=n.lat, lng=n.lng)

        # 1: source → poles (main trunk)
        for p in pole_indices:
            d = dist_matrix[source_idx, p]
            if 0.1 < d:
                w = self.calc_edge_weight(d)
                DG.add_edge(source_idx, p, weight=w, length=d, voltage=self.request.voltageLevel)

        # 2: Bidirectional pole ↔ pole (undirected spans)
        for i in range(len(pole_indices)):
            for j in range(i + 1, len(pole_indices)):
                p1, p2 = pole_indices[i], pole_indices[j]
                d = dist_matrix[p1, p2]
                w = self.calc_edge_weight(d)
                if 0.1 < d:
                    DG.add_edge(p1, p2, weight=w, length=d, voltage=self.request.voltageLevel)
                    DG.add_edge(p2, p1, weight=w, length=d, voltage=self.request.voltageLevel)

        # 3: poles → terminals (service drops)
        for p in pole_indices:
            for h in terminal_indices:
                d = dist_matrix[p, h]
                if 0.1 < d:
                    w = self.calc_edge_weight(d, to_terminal=True)
                    DG.add_edge(p, h, weight=w, length=d, voltage=self.request.voltageLevel)

        # 4. Source to Terminals
        for h in terminal_indices:
            d = dist_matrix[source_idx, h]
            if 0.1 < d:
                w = self.calc_edge_weight(d, to_terminal=True)
                DG.add_edge(source_idx, h, weight=w, length=d, voltage=self.request.voltageLevel)

        return DG

    @staticmethod
    def _minimum_spanning_arborescence_w_attrs(DG, attr="weight", default=1e18, preserve_attrs=True):
        """
        Constructs a minimum spanning arborescence (directed tree) from a directed graph
        while optionally preserving node attributes.

        Args:
            DG (networkx.DiGraph): The directed graph to compute the minimum spanning
                arborescence from.
            attr (str): Name of the edge attribute to use as the weight for computing
                the arborescence. Default is "weight".
            default (float): Default weight assigned to edges if the specified attribute
                does not exist. Default is 1e18.
            preserve_attrs (bool): If True, preserves the attributes of nodes from the
                input graph in the resulting arborescence. Default is True.

        Returns:
            networkx.DiGraph: A directed graph representing the minimum spanning
            arborescence, optionally with preserved node attributes.
        """

        arbo_graph = nx.minimum_spanning_arborescence(DG, attr=attr, default=default, preserve_attrs=preserve_attrs)

        if preserve_attrs:
            for n, d in DG.nodes(data=True):
                if n in arbo_graph:
                    arbo_graph.nodes[n].update(d)  # or arbo_graph.nodes[n] = d.copy()

        return arbo_graph

    def rename_poles(self, graph: Union[nx.DiGraph, nx.Graph]) -> Union[nx.DiGraph, nx.Graph]:
        """
        Rename poles using DEPTH-FIRST SEARCH (DFS preorder) order from the source.
        Poles are numbered in the exact order they are first discovered when doing
        a DFS traversal starting from the source node.
        """
        if self._source_idx is None or not graph:
            return graph

        graph = graph.copy()

        try:
            # DFS preorder traversal from source (depth-first discovery order)
            dfs_order = list(nx.dfs_preorder_nodes(graph, self._source_idx))
        except (nx.NetworkXError, KeyError):
            # Fallback if graph is malformed
            dfs_order = list(graph.nodes())

        # Collect poles in the exact DFS discovery order
        poles = []
        for idx in dfs_order:
            data = graph.nodes[idx]
            if data.get('type') == 'pole':
                poles.append((idx, data))

        # Rename poles sequentially
        for i, (idx, data) in enumerate(poles, 1):
            graph.nodes[idx]['name'] = f"Pole {i:03d}"
            graph.nodes[idx]['used'] = True

        if self.request.debug >= 1:
            print(f"✅ Renamed {len(poles)} poles using DFS (depth-first) order from source")

        return graph

    def prune_dead_end_pole_branches(self, graph: Union[nx.Graph, nx.DiGraph]) -> Union[nx.Graph, nx.DiGraph]:
        """
        Prunes dead-end pole branches in a Directed Graph (DiGraph).

        This function removes leaf nodes in the provided graph that represent poles and do not serve
        any terminal nodes in their subtree. The pruning process continues iteratively until no such
        dead-end poles remain in the graph. It modifies a copy of the input graph without affecting
        the original.

        Args:
            graph: A directed graph representing the network structure.

        Returns:
            A new graph with dead-end pole branches removed.
        """
        graph = graph.copy()

        removed = True
        while removed:
            removed = False
            leaves = [n for n in graph.nodes(data=True) if graph.out_degree(n[0]) == 0]
            for leaf in leaves:
                if leaf[1]['type'] == "pole":
                    # Check if this leaf (or its subtree) serves any terminal
                    descendants = nx.descendants(graph, leaf[0]) | {leaf[0]}
                    if not any(graph.nodes(data=True)[d]['type'] == 'terminal' for d in descendants):
                        # No terminal served → safe to remove
                        predecessors = list(graph.predecessors(leaf[0]))
                        for pred in predecessors:
                            graph.remove_edge(pred, leaf[0])
                        graph.remove_node(leaf[0])
                        removed = True

        graph = self.rename_poles(graph)

        return graph

    def _recompute_edges_for_node(self, graph: Union[nx.DiGraph, nx.Graph], node_idx: int):
        """
        Recomputes the edge attributes for all edges connected to a specific node in
        the graph. The method updates the 'length' and 'weight' attributes of each
        edge based on the Haversine distance between the nodes and the edge's
        associated voltage level.

        Args:
            graph (Union[nx.DiGraph, nx.Graph]): The graph object representing the
                network. It can be either a directed or undirected graph and must
                contain 'lat' and 'lng' attributes for its nodes.
            node_idx (int): The index of the node for which the edges need to be
                recomputed.
        """
        # Get ALL edges touching this node (incoming + outgoing)
        if isinstance(graph, nx.DiGraph):
            incident_edges = list(graph.in_edges(node_idx, data=True)) + \
                             list(graph.out_edges(node_idx, data=True))
        else:
            incident_edges = list(graph.edges(node_idx, data=True))

        for u, v, data in incident_edges:
            lat1, lng1 = graph.nodes[u]['lat'], graph.nodes[u]['lng']
            lat2, lng2 = graph.nodes[v]['lat'], graph.nodes[v]['lng']

            length = self.haversine_meters(lat1, lng1, lat2, lng2)

            # Update both the edge data and the stored attributes
            graph[u][v]['length'] = length
            graph[u][v]['weight'] = self.calc_edge_weight(
                length,
                graph[u][v].get('voltage', 'low')
            )

    def _all_edges_valid(self, graph, node_idx: int) -> bool:
        """
        Validates edges of a graph based on length constraints and node type requirements.

        This method checks whether all the edges incident to a specific node in a graph meet the specified
        criteria for length and other node-dependent conditions. It accommodates both directed and undirected
        graphs and differentiates between terminal-to-pole and pole-to-pole node types to enforce appropriate
        constraints.

        Args:
            graph (nx.Graph or nx.DiGraph): Input graph, which can either be a directed or undirected networkx graph.
            node_idx (int): Index of the node to validate within the graph.

        Returns:
            bool: True if all edges incident to the specified node satisfy the constraints, False otherwise.
        """
        if isinstance(graph, nx.DiGraph):
            incident_edges = list(graph.in_edges(node_idx, data=True)) + \
                             list(graph.out_edges(node_idx, data=True))
        else:
            incident_edges = list(graph.edges(node_idx, data=True))

        for u, v, data in incident_edges:
            length = data.get('length', 0.0)
            voltage = data.get('voltage', 'low')

            # Determine max allowed length
            u_type = graph.nodes[u].get('type')
            v_type = graph.nodes[v].get('type')

            if u_type == 'terminal' or v_type == 'terminal':
                max_len = self.get_max_pole_to_term()
            else:
                max_len = self.get_max_pole_to_pole()

            min_len = self.get_min_pole_to_term()

            if (length < min_len + 0.01) or (length > max_len + 0.01):
                return False
        return True

    def _enforce_min_pole_terminal_distances(self, graph: Union[nx.DiGraph, nx.Graph]) -> Union[nx.DiGraph, nx.Graph]:
        """
        Enforces minimum distance constraints between poles and terminals in a graph.

        This method ensures that the physical constraints regarding the minimum distance
        between poles and terminals are upheld within the provided graph. If any poles
        and terminals are found to be closer than the prescribed minimum distance, the
        positions of the poles are adjusted accordingly to meet the constraint. The
        operation is performed on a modified copy of the graph, leaving the original
        graph unaltered.

        Parameters:
            graph (Union[nx.DiGraph, nx.Graph]): The directed or undirected graph
                containing nodes and edges representing poles, terminals, and their
                connections.

        Returns:
            Union[nx.DiGraph, nx.Graph]: A modified graph that satisfies the minimum
            distance constraints between poles and terminals.

        Raises:
            ValueError: If distance calculations fail or graph node attributes are
            missing necessary geographic properties (`lat` and `lng`).
        """
        graph = graph.copy()
        min_dist = self.get_min_pole_to_term()

        if self.request.debug >= 1:
            print(f"\n--- Enforcing min pole-to-terminal distance ({min_dist:.1f}m) ---")

        fixed = 0
        for u, v, data in list(graph.edges(data=True)):
            u_type = graph.nodes[u].get('type')
            v_type = graph.nodes[v].get('type')

            if (u_type == 'terminal' or v_type == 'terminal') and (u_type == 'pole' or v_type == 'pole'):
                pole_idx = u if u_type == 'pole' else v
                term_idx = v if v_type == 'terminal' else u

                lat_p, lon_p = graph.nodes[pole_idx]['lat'], graph.nodes[pole_idx]['lng']
                lat_t, lon_t = graph.nodes[term_idx]['lat'], graph.nodes[term_idx]['lng']

                dist = self.haversine_meters(lat_p, lon_p, lat_t, lon_t)

                if dist < min_dist - 0.01:  # small tolerance
                    # Move pole away from terminal along the line
                    scale = min_dist / dist
                    new_lat = lat_t - scale * (lat_t - lat_p)
                    new_lon = lon_t - scale * (lon_t - lon_p)

                    graph.nodes[pole_idx]['lat'] = float(new_lat)
                    graph.nodes[pole_idx]['lng'] = float(new_lon)
                    fixed += 1

                    if self.request.debug >= 2:
                        print(f"    Fixed pole {pole_idx} → terminal {term_idx} ({dist:.2f}m → {min_dist:.2f}m)")

        if fixed > 0:
            self._recompute_all_edges(graph)
            if self.request.debug >= 1:
                print(f"    → Fixed {fixed} violating edges")
                self._plot_current_graph(graph, title="After min-distance enforcement")

        return graph

    def _post_solver_local_opt(self, graph: Union[nx.DiGraph, nx.Graph]) -> Union[nx.DiGraph, nx.Graph]:
        """
        Performs a local optimization on the given graph to reduce the total cost by
        iteratively applying optimization techniques. This process includes splitting
        long edges, renaming poles, and optimizing pole positions. The function
        terminates when no significant improvement is observed or when a predefined
        maximum number of iterations is reached.

        Args:
            graph (Union[nx.DiGraph, nx.Graph]): The input graph representing the
                structure to be optimized. The graph may be directed or undirected
                and should conform to the assumptions made by the optimization
                algorithms.

        Returns:
            Union[nx.DiGraph, nx.Graph]: The optimized graph after local adjustments
            to minimize the total cost.
        """
        # Initial cleanup
        graph = self.rename_poles(graph)

        previous_cost = self._compute_total_cost(graph)
        best_cost = previous_cost
        best_graph = graph  # optional: for reversion

        iteration = 0
        max_iterations = 12
        convergence_tol = 1e-3
        stagnant_count = 0
        max_stagnant = 1

        if self.request.debug >= 1:
            print(f"\n=== Starting Post-Solver Local Optimization ===")
            print(f"Initial cost: {previous_cost:.2f} | Nodes: {graph.number_of_nodes()}")

        while iteration < max_iterations:
            iteration += 1
            if self.request.debug >= 1:
                print(f"\n--- Iteration {iteration} ---")

            graph = self._pole_gradient_optimizer(graph)
            graph = self._merge_collinear_pole_chains(graph)
            graph = self._drop_redundant_poles(graph)
            graph = self.split_long_edges_w_poles(graph)

            # rebuild graph to refresh attributes and ensure consistency and shortest path
            nodes = [ Node(index=x[0], **x[1]) for x in graph.nodes(data=True)]
            graph = self.build_graph_from_nodes(nodes, directed=True)
            graph = self._minimum_spanning_arborescence_w_attrs(graph)
            graph = self.prune_dead_end_pole_branches(graph)

            graph = self.split_long_edges_w_poles(graph)

            if self.request.debug >= 2:
                print(f"Nodes: {graph.number_of_nodes()}")
                self._plot_current_graph(graph, title=f"After iteration {iteration}")

            current_cost = self._compute_total_cost(graph)
            delta = current_cost - previous_cost
            is_close = math.isclose(current_cost, previous_cost, abs_tol=convergence_tol)

            if self.request.debug >= 1:
                print(f"   Cost: {previous_cost:.2f} → {current_cost:.2f} (Δ = {delta:+.2f})")

            # Stopping conditions
            if current_cost > previous_cost + convergence_tol:
                if self.request.debug >= 1:
                    print("   Cost increased significantly → stopping")
                graph = best_graph  # revert
                break

            if is_close:
                stagnant_count += 1
                if stagnant_count >= max_stagnant:
                    if self.request.debug >= 1:
                        print(f"   No meaningful improvement for {max_stagnant} iterations → stopping")
                    break
            else:
                stagnant_count = 0

            previous_cost = current_cost
            if current_cost < best_cost:
                best_cost = current_cost
                best_graph = graph.copy()

        graph = self._enforce_min_pole_terminal_distances(graph)

        final_cost = self._compute_total_cost(graph)

        if self.request.debug >= 1:
            print(f"\n=== Post-opt finished after {iteration} iteration(s). "
                  f"Final cost: {final_cost:.2f} ===\n")

        return graph

    def _fast_total_cost_for_coords(self, coords: np.ndarray) -> float:
        """
        Calculates the total cost for a given set of coordinates considering wire costs, pole
        costs, trunk and terminal drops, and ensures compliance with maximum allowable distances.

        The method determines the cost of setting up a network infrastructure given a set of
        geographic coordinates. It handles different components of the cost, including trunk
        and terminal wire costs, pole costs, penalties for exceeding maximum distances, and
        pruning of unnecessary poles using a minimum spanning tree.

        Args:
            coords (np.ndarray): A 2D array of coordinates, where each row represents a point
                in geographic space. The length of coords must be at least 2.

        Returns:
            float: The total calculated cost, including the wire cost and the cost of active
            poles after pruning.
        """
        if len(coords) < 2:
            return 1e9

        n = len(coords)
        source_idx = self._source_idx
        terminals = self._terminal_indices
        poles = [i for i in range(n) if i != source_idx and i not in terminals]

        dist = self.haversine_vec(coords, coords)

        low_cost = self.get_cost_per_meter()
        pole_cost = self.request.costs.poleCost
        max_pole_pole = self.get_max_pole_to_pole()
        max_pole_term = self.get_max_pole_to_term()
        MAX_PENALTY = 10000.0

        wire_cost = dist * low_cost

        # Trunk cost
        extra_poles_trunk = np.maximum(0, np.ceil(dist / max_pole_pole) - 1)
        excess_trunk = np.maximum(0, dist - max_pole_pole)
        trunk_cost = wire_cost + (extra_poles_trunk * pole_cost) + (excess_trunk * MAX_PENALTY)

        # Terminal drop cost
        dist_adj = np.maximum(0, dist - max_pole_term)
        extra_poles_term = np.maximum(0, np.ceil(dist_adj / max_pole_pole) - 1)
        excess_term = np.maximum(0, dist - max_pole_term)
        term_cost = wire_cost + (extra_poles_term * pole_cost) + (excess_term * MAX_PENALTY)

        adj = np.zeros((n, n), dtype=float)

        if poles:
            adj[source_idx, poles] = trunk_cost[source_idx, poles]
            adj[poles, source_idx] = trunk_cost[poles, source_idx]

        if len(poles) > 1:
            p_grid = np.ix_(poles, poles)
            adj[p_grid] = trunk_cost[p_grid]

        valid_sources = [source_idx] + poles
        if valid_sources and terminals:
            st_grid = np.ix_(valid_sources, terminals)
            ts_grid = np.ix_(terminals, valid_sources)
            adj[st_grid] = term_cost[st_grid]
            adj[ts_grid] = term_cost[ts_grid]

        adj[dist < 0.1] = 0.0
        np.fill_diagonal(adj, 0.0)

        from scipy.sparse import csr_matrix
        from scipy.sparse.csgraph import minimum_spanning_tree

        csr_adj = csr_matrix(adj)
        mst = minimum_spanning_tree(csr_adj)

        # Fast pruning
        mst_dense = mst.toarray()
        undirected_mst = mst_dense + mst_dense.T
        degrees = np.count_nonzero(undirected_mst, axis=1)

        pruned_nodes = set()
        removed = True
        while removed:
            removed = False
            for p in poles:
                if p not in pruned_nodes and degrees[p] == 1:
                    pruned_nodes.add(p)
                    neighbors = np.nonzero(undirected_mst[p])[0]
                    if len(neighbors) > 0:
                        neighbor = neighbors[0]
                        undirected_mst[p, neighbor] = 0.0
                        undirected_mst[neighbor, p] = 0.0
                        degrees[p] = 0
                        degrees[neighbor] -= 1
                    removed = True

        total_wire_and_extra = np.sum(undirected_mst) / 2.0
        num_active_poles = len(poles) - len(pruned_nodes)
        return total_wire_and_extra + (num_active_poles * pole_cost)

    def _drop_redundant_poles(self, pruned_graph: Union[nx.Graph, nx.DiGraph]) -> Union[nx.Graph, nx.DiGraph]:
        """
        Removes redundant pole nodes from the graph that do not contribute to connecting
        terminals. A pole is considered redundant if its removal does not disconnect any
        terminal from the source, and doing so reduces the total cost.

        Args:
            pruned_graph (nx.DiGraph): The directed graph representing the current network
                structure, with nodes containing 'type' and positional attributes.

        Returns:
            nx.DiGraph: A new directed graph with redundant poles removed and poles renamed.

        """
        if self.request.debug >= 1:
            print("\n--- Starting Fast Drop Phase (with proper reconnection) ---")

        current_graph = pruned_graph.copy()
        cur_cost = self._compute_total_cost(current_graph)

        pole_indices = sorted(
            [idx for idx, data in current_graph.nodes(data=True)
             if data.get('type') == 'pole'],
            reverse=True
        )

        for pole_to_drop in pole_indices:
            if self.request.debug >= 2:
                print(f"  Trying to drop pole {pole_to_drop}...")

            # === Build reduced coordinates (without the pole) ===
            coords_list = []
            names_list = []
            for idx, data in sorted(current_graph.nodes(data=True)):
                if idx == pole_to_drop:
                    continue
                coords_list.append([data['lat'], data['lng']])
                names_list.append(data.get('name', f"Node {len(coords_list)}"))

            coords_array = np.array(coords_list, dtype=float) if coords_list else np.empty((0, 2))

            # Fast cost check
            trial_cost = self._fast_total_cost_for_coords(coords_array)

            if trial_cost <= cur_cost + 1e-3:
                # === ACCEPTED DROP → rebuild the correct graph ===
                if self.request.debug >= 1:
                    print(f"Drop Phase: Removed pole {pole_to_drop} (cost {cur_cost:.2f} → {trial_cost:.2f})")

                trial_nodes = self._build_nodes(coords_array, np.empty((0, 2)), names_list)

                DG = self.build_directed_graph_for_arborescence(trial_nodes)
                arbo_graph = self._minimum_spanning_arborescence_w_attrs(DG)
                new_graph = self.prune_dead_end_pole_branches(arbo_graph)

                current_graph = new_graph
                cur_cost = trial_cost
            else:
                if self.request.debug >= 2:
                    print(f"Drop Phase: Kept pole {pole_to_drop} (would increase cost to {trial_cost:.2f})")

        if self.request.debug >= 1:
            print("--- Fast Drop Phase Complete ---\n")
            self._plot_current_graph(current_graph, added_points=None, title="After Drop Phase")

        current_graph = self.rename_poles(current_graph)
        current_graph = self.rename_poles(current_graph)
        return current_graph

    def _recompute_all_edges(self, graph: Union[nx.Graph, nx.DiGraph]):
        """
        Recalculates and updates all edges in the given graph with computed lengths and weights.

        This method iterates through all edges in the provided graph, computes their lengths
        based on the Haversine distance formula, and updates the edge attributes accordingly.
        Additionally, it assigns a weight to each edge depending on its length and whether
        either endpoint of the edge is a terminal node.

        Parameters:
        graph: Union[nx.Graph, nx.DiGraph]
            The graph object containing nodes and edges. Nodes must include 'lat' and 'lng'
            attributes representing their geographic coordinates. Additionally, a node may
            optionally include a 'type' attribute to signify its role (e.g., 'terminal').

        Raises:
        None
        """
        for u, v, data in list(graph.edges(data=True)):
            lat1, lon1 = graph.nodes[u]['lat'], graph.nodes[u]['lng']
            lat2, lon2 = graph.nodes[v]['lat'], graph.nodes[v]['lng']
            length = self.haversine_meters(lat1, lon1, lat2, lon2)
            data['length'] = length

            # Same logic you already use elsewhere
            to_terminal = (graph.nodes[v].get('type') == 'terminal' or
                           graph.nodes[u].get('type') == 'terminal')
            data['weight'] = self.calc_edge_weight(length, to_terminal=to_terminal)

    def _get_pole_optimization_order(self, graph: Union[nx.DiGraph, nx.Graph], farthest_first: bool = True) -> List[
        int]:
        """
        Generates an optimized order of poles for processing based on their distance
        from a source node in the given graph. This function determines the order
        either from farthest to closest or closest to farthest, depending on the
        `farthest_first` parameter.

        Parameters:
        graph: nx.DiGraph or nx.Graph
            The graph representing the network structure. Nodes must have a 'type'
            attribute to identify poles, and edges may optionally have a 'length'
            attribute for weighted distance calculation.
        farthest_first: bool, default=True
            If True, sorts poles from farthest to closest; if False, sorts poles from
            closest to farthest.

        Returns:
        List[int]
            A list of node indices representing poles, sorted according to the
            specified order of distance from the source node.
        """
        source_idx = self._source_idx
        poles = [
            idx for idx, data in graph.nodes(data=True)
            if data.get('type') == 'pole'
        ]
        if not poles:
            return []

        # Compute shortest-path distance (using edge 'length' if present)
        try:
            dist_dict = nx.single_source_dijkstra_path_length(
                graph, source_idx, weight='length'
            )
        except (nx.NetworkXError, KeyError):
            # fallback for graphs without 'length' or disconnected nodes
            dist_dict = nx.single_source_shortest_path_length(graph, source_idx)

        # Sort poles
        sorted_poles = sorted(
            poles,
            key=lambda p: dist_dict.get(p, 999999.0),
            reverse=farthest_first
        )

        if self.request.debug >= 2:
            print(f"  Pole optimization order: {'farthest-first' if farthest_first else 'closest-first'} "
                  f"({len(sorted_poles)} poles)")

        return sorted_poles

    def _pole_gradient_optimizer(self, graph: Union[nx.DiGraph, nx.Graph]) -> Union[nx.DiGraph, nx.Graph]:
        """
        Optimizes the positions of poles in a graph with respect to a cost function. The optimization
        is performed iteratively over selected poles, ensuring that each pole's movement adheres to
        predefined constraints. The optimization process stops early if no meaningful improvement is
        achieved in a pass.

        Parameters:
            graph (Union[nx.Graph, nx.DiGraph]): The graph containing nodes and edges, where nodes
            represent points such as poles or terminals, and edges represent connections between these
            points.

        Returns:
            Union[nx.Graph, nx.DiGraph]: A copy of the input graph with adjusted pole positions
            optimized to minimize the total cost.

        Raises:
            None
        """
        pole_indices = [idx for idx, data in graph.nodes(data=True)
                        if data.get('type') == 'pole']
        if not pole_indices:
            return graph

        graph = graph.copy()
        n_passes = 3

        max_move_meters = 20.0
        one_meter_deg = 1.0 / 111111.0
        max_delta_deg = max_move_meters * one_meter_deg

        if self.request.debug >= 1:
            initial_cost = self._compute_total_cost(graph)
            print(f"\n=== Sequential Pole Optimization ({len(pole_indices)} poles, "
                  f"{n_passes} passes, max move {max_move_meters}m) ===")
            print(f"Initial cost: {initial_cost:.2f}")

        improved_anywhere = True
        total_improvement = 0.0

        for pass_num in range(n_passes):
            if not improved_anywhere and pass_num > 0:
                if self.request.debug >= 1:
                    print(f"   No improvement in pass {pass_num} → stopping early")
                break

            improved_anywhere = False
            pole_order = self._get_pole_optimization_order(
                graph,
                farthest_first=False
            )

            for node_idx in pole_order:
                if node_idx not in graph:
                    continue

                lat0 = graph.nodes[node_idx]['lat']
                lon0 = graph.nodes[node_idx]['lng']
                old_cost = self._compute_total_cost(graph)

                def objective(x):
                    lat, lon = x
                    # Temporarily move pole
                    graph.nodes[node_idx]['lat'] = float(lat)
                    graph.nodes[node_idx]['lng'] = float(lon)
                    self._recompute_all_edges(graph)

                    return self._compute_total_cost(graph)

                res = minimize(
                    objective,
                    [lat0, lon0],
                    method='BFGS',
                )

                new_cost = res.fun

                best_lat, best_lon = res.x
                graph.nodes[node_idx]['lat'] = float(best_lat)
                graph.nodes[node_idx]['lng'] = float(best_lon)
                self._recompute_all_edges(graph)

                if new_cost < old_cost - 0.5:  # only accept meaningful real savings
                    improved_anywhere = True
                    total_improvement += (new_cost - old_cost)
                    edge_lengths = [e[2]['length'] for e in graph.edges(data=True)]
                    if self.request.debug >= 1:
                        print("Max edge length after move:", max(edge_lengths) if edge_lengths else 0.0)
                    if self.request.debug >= 1:
                        move_m = math.hypot(
                            (res.x[0] - lat0) / one_meter_deg,
                            (res.x[1] - lon0) / one_meter_deg
                        )
                        print(f"   Pole {node_idx:3d} improved by {new_cost - old_cost:+.2f} $ "
                              f"(moved {move_m:.3f}m)")
                    if self.request.debug >= 3:
                        self._plot_current_graph(graph, added_points=[(res.x[0], res.x[1])], )
                else:
                    # Revert to original position
                    graph.nodes[node_idx]['lat'] = lat0
                    graph.nodes[node_idx]['lng'] = lon0
                    self._recompute_all_edges(graph)

        final_cost = self._compute_total_cost(graph)
        if self.request.debug >= 1:
            print(f"Optimization finished → cost {initial_cost:.2f} → {final_cost:.2f} "
                  f"(total improvement {total_improvement:.2f})")

        if self.request.debug >= 1:
            self._plot_current_graph(graph,
                                     title=f"After Sequential Pole Optimization(${self._compute_total_cost(graph):.2f}) + {self.get_min_max_edge_len(graph)}")

        return graph

    def get_min_max_edge_len(self, graph):

        edge_lengths = [e[2]['length'] for e in graph.edges(data=True)]
        max_len = max(edge_lengths) if edge_lengths else 0.0
        min_len = min(edge_lengths) if edge_lengths else 0.0

        return f"Max edge length: {max_len}m | Min edge length: {min_len}m"

    @staticmethod
    def _get_num_poles_and_wire_length(graph: Union[nx.Graph, nx.DiGraph]):
        """
        Calculates the number of poles in the graph and the total wire length for
        different voltage types.

        This function iterates over the edges and nodes of the graph to compute
        the total wire length categorized by voltage type ("low" and "high") and
        count the total number of poles. It assumes that the edges in the graph
        have an attribute `length` for wire length and `voltage` for the type of
        voltage. Nodes in the graph are expected to have a `type` attribute to
        identify poles.

        Args:
            graph (Union[nx.Graph, nx.DiGraph]): A NetworkX graph representing the
                network of wires and poles. The graph's edges should contain the
                attributes `length` (float) and `voltage` (str), and its nodes
                should have a `type` attribute.

        Returns:
            Tuple[int, float, float]: A tuple containing:
                - The number of poles (int) in the graph.
                - The total wire length (float) for "low" voltage.
                - The total wire length (float) for "high" voltage.
        """
        low_m = high_m = 0.0

        for u, v, d in graph.edges(data=True):
            length = d.get("length", 0.0)
            voltage = d.get("voltage", "unknown")

            if voltage == "low":
                low_m += length
            elif voltage == "high":
                high_m += length

        n_poles = sum(1 for idx, data in graph.nodes(data=True) if data['type'] == "pole")

        return n_poles, low_m, high_m

    def _distance_from_source(self, graph: Union[nx.Graph, nx.DiGraph], node_idx: int) -> float:
        """
        Returns the (approximate) distance from the source to a given node.
        Uses edge 'length' when available (preferred), otherwise falls back to hop count.
        """
        try:
            dists = nx.single_source_dijkstra_path_length(graph, self._source_idx, weight='length')
            return float(dists.get(node_idx, 999999.0))
        except (nx.NetworkXError, KeyError):
            # fallback for graphs without length attributes
            try:
                return float(nx.shortest_path_length(graph, self._source_idx, node_idx))
            except:
                return 999999.0

    def _merge_collinear_pole_chains(self, graph: Union[nx.Graph, nx.DiGraph]) -> nx.DiGraph:
        """
        NEW BEHAVIOR (as requested):
        - Start at every TERMINAL
        - Walk UPSTREAM (via predecessors) collecting the chain
        - Stop when we reach a node that has MORE THAN 1 SUCCESSOR
          (i.e. a branching point in the tree)
        - Treat that branching node as the START of the merged edge
        - The terminal is the END of the merged edge
        - If the entire chain is collinear, collapse all intermediate poles
          into ONE long straight edge (branch_point → terminal)

        This is repeated across the whole graph until all straight chains
        leading to terminals are reduced to single edges.

        After this pass, split_long_edges_w_poles will see the full long
        straight segments and apply maximal spacing + terminal stretch.
        """
        graph = graph.copy()
        merged_count = 0

        # Ensure we have a proper directed arborescence (edges point away from source)
        if not isinstance(graph, nx.DiGraph):
            graph = self.build_directed_graph_for_arborescence(
                [Node(index=i, lat=n['lat'], lng=n['lng'], type=n['type'], name=n.get('name'))
                 for i, n in graph.nodes(data=True)]
            )

        terminal_nodes = [
            n for n, data in graph.nodes(data=True)
            if data.get('type') == 'terminal'
        ]

        visited = set()  # prevent re-processing overlapping chains

        for term_idx in terminal_nodes:
            if term_idx in visited:
                continue

            # Build chain UPSTREAM from terminal
            chain = [term_idx]
            current = term_idx

            while True:
                preds = list(graph.predecessors(current))
                if len(preds) != 1:          # not a straight path
                    break
                pred = preds[0]

                # Stop when we hit a branching node (more than 1 successor)
                if graph.out_degree(pred) > 1:
                    chain.append(pred)
                    break

                # Also stop at source (it has no predecessor)
                if pred == self._source_idx:
                    chain.append(pred)
                    break

                chain.append(pred)
                current = pred

                if current in visited:
                    break

            # Reverse so chain[0] = upstream branching node / source
            #          chain[-1] = terminal
            chain = chain[::-1]

            # Need at least 2 edges (3 nodes) to be worth merging
            if len(chain) < 3:
                continue

            # Check collinearity
            is_straight = True
            for i in range(len(chain) - 2):
                p1 = np.array([graph.nodes[chain[i]]['lat'], graph.nodes[chain[i]]['lng']])
                p2 = np.array([graph.nodes[chain[i+1]]['lat'], graph.nodes[chain[i+1]]['lng']])
                p3 = np.array([graph.nodes[chain[i+2]]['lat'], graph.nodes[chain[i+2]]['lng']])

                v1 = p2 - p1
                v2 = p3 - p2
                cross = abs(v1[0] * v2[1] - v1[1] * v2[0])
                if cross > 1e-5:   # tight tolerance (~0.5–1°)
                    is_straight = False
                    break

            if not is_straight:
                continue

            # === MERGE the straight chain ===
            start_idx = chain[0]      # branching node or source
            end_idx   = chain[-1]     # terminal
            end_type  = graph.nodes[end_idx].get('type')

            # Compute true total length of the chain
            total_length = 0.0
            for i in range(len(chain) - 1):
                total_length += graph[chain[i]][chain[i+1]]['length']

            # Remove all intermediate poles
            for mid in chain[1:-1]:
                if graph.nodes[mid].get('type') == 'pole':
                    graph.remove_node(mid)
                    merged_count += 1

            # Add single long edge
            is_to_terminal = (end_type == 'terminal')
            graph.add_edge(
                start_idx, end_idx,
                length=total_length,
                voltage=graph.nodes[start_idx].get('voltage', self.request.voltageLevel),
                weight=self.calc_edge_weight(total_length, to_terminal=is_to_terminal)
            )

            # Mark all nodes in this chain as visited
            visited.update(chain)

        graph = self.rename_poles(graph)

        if self.request.debug >= 1 and merged_count > 0:
            print(f"  _merge_collinear_pole_chains: merged {merged_count} intermediate poles "
                  f"into long straight segments (terminal-first, stop at branch points)")
            self._plot_current_graph(graph, title="After Collinear Merge (terminal-first + branch stop)")

        return graph

    def split_long_edges_w_poles(self, graph: Union[nx.Graph, nx.DiGraph]) -> nx.DiGraph:
        """
        HARD-RESPECTING long-edge splitting.

        • Every created edge (pole-pole or pole-terminal) is guaranteed to be:
          - ≤ max_pole_to_pole (or max_pole_to_term for service drops)
          - ≥ a safe minimum (no near-overlapping poles)

        • Uses **uniform spacing** for the entire remaining segment.
          This completely eliminates tiny final segments that were causing
          almost-overlapping poles.

        • Terminal edges: first pole placed exactly at max_pole_to_term from the terminal,
          then the rest of the chain is split evenly.
        """
        MIN_SEGMENT_M = 5.0   # hard floor — you can tune this if you want even stricter

        new_graph = graph.copy()

        # node data cache
        node_data = {n: data.copy() for n, data in new_graph.nodes(data=True)}
        if not node_data:
            return new_graph

        next_index = max(new_graph.nodes) + 1

        # Pre-compute source distances for pole-pole heuristic
        source_dist = {}
        try:
            source_dist = nx.single_source_dijkstra_path_length(
                new_graph, self._source_idx, weight='length'
            )
        except (nx.NetworkXError, KeyError):
            pass

        for u, v, data in list(new_graph.edges(data=True)):
            if u not in new_graph or v not in new_graph:
                continue

            u_type = new_graph.nodes[u].get('type', '')
            v_type = new_graph.nodes[v].get('type', '')
            length_m = float(data.get("length", 0.0))
            voltage = data.get("voltage", self.request.voltageLevel)

            is_terminal_edge = (u_type == "terminal" or v_type == "terminal")

            if is_terminal_edge:
                max_allowed = self.get_max_pole_to_term()
            else:
                max_allowed = self.get_max_pole_to_pole()

            if length_m <= max_allowed + 1.0:
                continue

            # ── Determine starting end ──
            if is_terminal_edge:
                term_idx = u if u_type == "terminal" else v
                far_idx = v if u_type == "terminal" else u
                start_idx, end_idx = term_idx, far_idx
                to_terminal = True
            else:
                d_u = source_dist.get(u, self._distance_from_source(new_graph, u))
                d_v = source_dist.get(v, self._distance_from_source(new_graph, v))
                start_idx, end_idx = (u, v) if d_u <= d_v else (v, u)
                to_terminal = False

            start_pos = np.array([node_data[start_idx]['lat'], node_data[start_idx]['lng']], dtype=float)
            end_pos   = np.array([node_data[end_idx]['lat'],   node_data[end_idx]['lng']],   dtype=float)

            new_graph.remove_edge(u, v)

            prev_idx = start_idx
            remaining_m = length_m

            current_pos = start_pos

            # ── Terminal edge special case ──
            if is_terminal_edge:
                # Serving pole exactly at max_pole_to_term from terminal
                frac = max_allowed / length_m
                first_pole_pos = current_pos + frac * (end_pos - current_pos)

                new_graph.add_node(
                    next_index,
                    lat=float(first_pole_pos[0]),
                    lng=float(first_pole_pos[1]),
                    type="pole",
                    name=f"Pole {next_index}"
                )
                node_data[next_index] = {"lat": float(first_pole_pos[0]), "lng": float(first_pole_pos[1]), "type": "pole"}

                new_graph.add_edge(
                    start_idx, next_index,
                    length=max_allowed,
                    voltage=voltage,
                    weight=self.calc_edge_weight(max_allowed, to_terminal=True)
                )

                prev_idx = next_index
                next_index += 1
                remaining_m = length_m - max_allowed
                max_allowed = self.get_max_pole_to_pole()  # switch to pole-pole max for the rest
                current_pos = first_pole_pos


            # ── Uniform spacing for the remaining straight segment ──
            if remaining_m > max_allowed + 0.1:
                num_segments = math.ceil(remaining_m / max_allowed)
                segment_length = remaining_m / num_segments   # guaranteed <= max_allowed

                # Make sure we don't create a segment shorter than MIN_SEGMENT_M
                if segment_length < MIN_SEGMENT_M and num_segments > 1:
                    num_segments -= 1
                    segment_length = remaining_m / num_segments

                for i in range(1, num_segments):
                    frac = i / num_segments
                    current_pos = current_pos + frac * (end_pos - current_pos)

                    new_graph.add_node(
                        next_index,
                        lat=float(current_pos[0]),
                        lng=float(current_pos[1]),
                        type="pole",
                        name=f"Pole {next_index}"
                    )
                    node_data[next_index] = {"lat": float(current_pos[0]), "lng": float(current_pos[1]), "type": "pole"}

                    new_graph.add_edge(
                        prev_idx, next_index,
                        length=segment_length,
                        voltage=voltage,
                        weight=self.calc_edge_weight(segment_length)
                    )

                    prev_idx = next_index
                    next_index += 1

            # ── Final segment (now guaranteed to respect limits) ──
            final_length = remaining_m if not is_terminal_edge else (length_m - (length_m - remaining_m))
            final_to_terminal = to_terminal and (prev_idx != end_idx)
            new_graph.add_edge(
                prev_idx, end_idx,
                length=final_length,
                voltage=voltage,
                weight=self.calc_edge_weight(final_length, to_terminal=final_to_terminal)
            )

        new_graph = self.rename_poles(new_graph)

        if self.request.debug >= 1:
            added = next_index - (max(node_data.keys()) + 1 if node_data else 0)
            print(f"  split_long_edges_w_poles: added {added} poles (hard uniform spacing — limits strictly respected)")
            self._plot_current_graph(new_graph, title="After Hard-Respect Long Edge Splitting")

        return new_graph

    def _get_ordered_nodes_and_remap_edges(self, graph: Union[nx.DiGraph, nx.Graph]):
        """Return nodes in canonical order: Source → Terminals → Poles (sorted by distance from source)
        with dense contiguous indices 0,1,2,... and remap all edges accordingly."""
        source_nodes = []
        terminal_nodes = []
        pole_nodes = []

        for idx, data in graph.nodes(data=True):
            node = Node(
                index=idx,
                lat=data['lat'],
                lng=data['lng'],
                name=data.get('name') or f"{data['type']} {idx}",
                type=data['type'],
            )
            if data['type'] == "source":
                source_nodes.append(node)
            elif data['type'] == "terminal":
                terminal_nodes.append(node)
            elif data['type'] == "pole":
                pole_nodes.append(node)

        # Keep original relative order for terminals
        terminal_nodes.sort(key=lambda n: n.index)

        # Sort poles by their CURRENT name (which was set by rename_poles to "Pole 001", "Pole 002", ...)
        # This guarantees distance-based ordering
        pole_nodes.sort(key=lambda n: n.name)

        ordered_nodes = source_nodes + terminal_nodes + pole_nodes

        # Build old → new index mapping
        old_to_new = {node.index: new_idx for new_idx, node in enumerate(ordered_nodes)}

        # Create final nodes with dense indices
        final_nodes = []
        for new_idx, node in enumerate(ordered_nodes):
            final_nodes.append(Node(
                index=new_idx,
                lat=node.lat,
                lng=node.lng,
                name=node.name,
                type=node.type,
            ))

        # Remap edges
        final_edges = []
        for start_idx, end_idx, edge_data in graph.edges(data=True):
            new_start = old_to_new[start_idx]
            new_end = old_to_new[end_idx]

            start_data = graph.nodes[start_idx]
            end_data = graph.nodes[end_idx]

            final_edges.append(Edge(
                start=Node(
                    index=new_start,
                    lat=start_data['lat'],
                    lng=start_data['lng'],
                    name=start_data.get('name'),
                    type=start_data['type']
                ),
                end=Node(
                    index=new_end,
                    lat=end_data['lat'],
                    lng=end_data['lng'],
                    name=end_data.get('name'),
                    type=end_data['type']
                ),
                lengthMeters=round(edge_data.get('length', 0.0), 4),
                voltage=edge_data.get("voltage", "low"),
            ))

        return final_nodes, final_edges

    def build_solver_result(self, graph: Union[nx.DiGraph, nx.Graph],
                            debug_info: Optional[Dict[str, Any]] = None) -> SolverResult:
        """
        Builds and returns a SolverResult object that encapsulates details about the network optimization solution,
        including calculated costs, node and edge details, and optional debugging information.

        This method processes a graph input, ensuring a consistent ordering of nodes and remapping of edges.
        It performs cost calculations based on the number of poles and the lengths of low-voltage and high-voltage
        wiring required. The results are then encapsulated in the SolverResult class instance.

        Parameters:
            graph (Union[nx.DiGraph, nx.Graph]): The input graph representing the network to be optimized.
            debug_info (Optional[Dict[str, Any]]): Optional debugging information relevant to the optimization process.

        Returns:
            SolverResult: An object containing details of the optimized network, its associated costs, and debug information
            if provided and enabled.
        """
        # rename poles to have a name
        graph = self.rename_poles(graph)

        # ────── Force consistent ordering on output ──────
        nodes, edges = self._get_ordered_nodes_and_remap_edges(graph)

        # Cost calculations (unchanged)
        num_poles, total_low_m, total_high_m = self._get_num_poles_and_wire_length(graph)

        pole_cost = self._costs.poleCost
        low_cost_m = self._costs.lowVoltageCostPerMeter
        high_cost_m = self._costs.highVoltageCostPerMeter

        low_wire_cost = total_low_m * low_cost_m
        high_wire_cost = total_high_m * high_cost_m
        total_wire_cost = low_wire_cost + high_wire_cost
        total_cost = total_wire_cost + num_poles * pole_cost

        return SolverResult(
            edges=edges,  # ← now correctly remapped
            nodes=nodes,  # ← now guaranteed Source → Terminals → Poles
            totalLowVoltageMeters=round(total_low_m, 2),
            totalHighVoltageMeters=round(total_high_m, 2),
            numPolesUsed=num_poles,
            poleCostEstimate=round(num_poles * pole_cost, 2),
            lowWireCostEstimate=round(low_wire_cost, 2),
            highWireCostEstimate=round(high_wire_cost, 2),
            totalWireCostEstimate=round(total_wire_cost, 2),
            totalCostEstimate=round(total_cost, 2),
            debug=debug_info if self.request.debug else None,
        )

    def compute_distance_matrix(self, points: np.ndarray) -> np.ndarray:
        """Default haversine distance matrix — override if you want Euclidean, etc."""
        return self.haversine_vec(points, points)

    def get_all_points(self) -> np.ndarray:
        """Convenience: return (n_points, 2) array of all original lat/lon"""
        self.parse_and_validate_input()  # ensure parsed
        return self._coords

    def source_coord(self) -> np.ndarray:
        self.parse_and_validate_input()
        return self._coords[self._source_idx]

    def terminal_coords(self) -> np.ndarray:
        self.parse_and_validate_input()
        return self._coords[self._terminal_indices]
