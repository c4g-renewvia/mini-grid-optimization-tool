# optimizers/base.py
import math
from abc import ABC, abstractmethod
from typing import Tuple

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib import collections as mc

from ..utils.models import *

MIN_DIST_TO_TERMINAL = 10.0,
MAX_CIRCUMRADIUS = 300.0
MIN_CANDIDATE_SEPARATION = 10.0

MIN_POLE_TO_TERMINAL = 10.0
MAX_POLE_TO_TERMINAL_LV = 30.0
# MAX_POLE_TO_TERMINAL_HV = 50.0

MIN_POLE_TO_POLE = 10.0

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
        self._coords: Optional[np.ndarray] = None
        self._source_idx: Optional[int] = None
        self._terminal_indices: Optional[List[int]] = None
        self._names: Optional[List[str]] = None
        self._costs: Optional[Costs] = None

        self._dist_matrix = None  # Will store the current (n x n) distance matrix
        self._cached_coords_hash = None  # Simple way to detect when points changed

    # ─── Static Helper methods ───────────────────────────────────────────────
    @staticmethod
    def get_input_params():
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

    @staticmethod
    def parse_input(request: SolverRequest, poles: bool = True, debug: int = 0):
        """
        Parses input request containing information about geographical points, solver, and their attributes to generate structured
        data suitable for optimization tasks.

        This function processes the input `SolverRequest` to extract coordinates, their names, and classify one of the
        markers as the "Power Source". It ensures that the input contains at least two valid points, assigns a "Power Source"
        if not explicitly provided, and organizes the remaining points as terminals. The function also validates and cleans input
        data for consistency.

        Args:
            request: Input request containing points and their associated solver
            poles: If True, poles will be included in the parsed data.
            debug: Debug level.

        Returns:
            A tuple containing coords, terminal_indices, source_idx, original_names, solver
        """

        points = request.points
        costs: Costs = request.costs.model_copy()  # defensive copy

        if len(points) < 2:
            raise ValueError("At least 2 points required")

        coords_list = []
        names = []
        source_idx = None

        SOURCE_KEYWORDS = {
            "power source", "powersource", "source", "substation", "main source",
            "primary", "generator", "grid tie", "utility"
        }

        for i, p in enumerate(points):
            # Name handling
            raw_name = p.get("name")

            if not poles and "pole" in raw_name.lower():
                continue

            if raw_name is not None:
                try:
                    int(raw_name.split(" ")[-1])
                    name = raw_name
                except:
                    name = f"{str(raw_name).strip()} {i + 1}"
            else:
                name = f"Location {i + 1}"

            names.append(name)

            try:
                lat = float(p["lat"])
                lng = float(p["lng"])
            except (KeyError, TypeError, ValueError) as e:
                raise ValueError(f"Point {i + 1} missing/invalid lat/lng: {p}") from e

            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                raise ValueError(f"Point {i + 1} has invalid coordinates: ({lat}, {lng})")

            coords_list.append([lat, lng])

            # Source detection (case-insensitive, more flexible)
            name_lower = name.lower()
            if any(kw in name_lower for kw in SOURCE_KEYWORDS) or "source" in name_lower:
                if source_idx is not None:
                    print(f"Warning: Multiple potential sources detected; using first (index {source_idx})")
                else:
                    source_idx = i
                    names[i] = name  # canonical name

        coords = np.array(coords_list, dtype=np.float64)

        if source_idx is None:
            if debug:
                print("No explicit power source found → using first point (index 0)")
            source_idx = 0
            names[0] = "Power Source"

        terminal_indices = [i for i in range(len(coords)) if i != source_idx]

        return coords, terminal_indices, source_idx, names, costs

    @staticmethod
    def _plot_current_tree(graph, added_points=None, title="Current tree after candidate addition", filename=None):
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
            # Safely look up the exact coordinate using the node's unique index
            if u in coord_dict and v in coord_dict:
                pt_u = [coord_dict[u][1], coord_dict[u][0]]  # [lng, lat]
                pt_v = [coord_dict[v][1], coord_dict[v][0]]
                edge_lines.append([pt_u, pt_v])

        if edge_lines:
            lc = mc.LineCollection(edge_lines, colors='green', linewidths=1.5, alpha=0.7)
            ax.add_collection(lc)

        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

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
    def _solve(self, input_tuple) -> Union[nx.DiGraph, nx.Graph]:
        """
        Abstract method to be implemented by subclasses.
        Solves the given input data and returns the resulting graph, list of nodes, and an array of results.

        :param input_tuple: The input data containing necessary information to process the solution. The
            structure and data type of the input must align with the expected requirements of the solution.
        :return: A tuple containing three elements:
            - A ``nx.Graph`` object representing the computed graph.
        """
        pass

    def solve(self) -> SolverResult:
        """
        Main entry point: take the request → produce full SolverResult.

        This is the only method most users / tests should call directly.

        """

        # 1. Parse input and input into abstract solver method
        graph = self._solve(self.parse_and_validate_input(poles=True))

        # 2. Gradient Decent each pole placement to ensure not local optimization is left on the table
        final_graph = self._post_solver_local_opt(graph)

        return self.build_solver_result(final_graph)

    # ─── Helpful common utilities (can be used or overridden) ────────────────
    def _build_nodes(self, coords, candidates, names):
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
                is_candidate=False,
                used=True,  # originals always kept
            ))

        offset = n_orig
        for j, (lat, lon) in enumerate(candidates, start=offset):
            nodes.append(Node(
                index=j,
                lat=float(lat),
                lng=float(lon),
                type="pole",
                is_candidate=True,
                used=False,
            ))

        return nodes

    def parse_and_validate_input(self, poles: bool = True) -> Tuple[
        List[Node], np.ndarray, int, List[int], List[str], Dict[str, float]]:
        """
        Parses and validates the input data for constructing nodes. This includes parsing input data
        such as coordinates, source index, terminal indices, names, and solver, as well as ensuring
        basic operational validity through validation checks and setting default solver if not
        provided.

        Args:
            poles (bool): Determines whether poles should be included in the constructed nodes.

        Returns:
            Tuple[list[Node], np.ndarray, int, List[int], List[str], Dict[str, float]]:
            A tuple containing the constructed nodes, coordinates, source index,
            terminal indices, names, and cost mappings.

        Raises:
            ValueError: If the input does not contain at least one source and one terminal.
        """
        if self._coords is not None:
            return self._coords, self._source_idx, self._terminal_indices, self._names, self._costs

        self._coords, self._terminal_indices, self._source_idx, self._names, self._costs = self.parse_input(
            self.request, poles=poles, debug=self.request.debug)

        # You can add more validation / normalization here if desired
        if len(self._coords) < 2:
            raise ValueError("Need at least source + 1 terminal")

        self._nodes = self._build_nodes(self._coords, [], self._names)

        return self._nodes, self._coords, self._source_idx, self._terminal_indices, self._names, self._costs

    def calc_edge_weight(self, length, voltage="low", to_terminal=False):
        """
        Cost of wire and pole
        Args:
            length: length of edge
            voltage: cost to use for edge. key in self.request.solver dict,
                e.g. "lowVoltageCostPerMeter" or "highVoltageCostPerMeter"
            to_terminal: if destination is terminal, then subtract the length of pole to house constraint from extra pole calculation

        Returns:

        """
        voltage_cost = (self.request.costs.lowVoltageCostPerMeter
                        if voltage == "low"
                        else self.request.costs.highVoltageCostPerMeter)

        pole_cost = self.request.costs.poleCost

        # Cost of the wire
        weight = length * voltage_cost

        # Cost of intermediate support poles for long spans
        pole_to_pole_constraint = (self.request.lengthConstraints.low.poleToPoleLengthConstraint
                                   if voltage == "low"
                                   else self.request.lengthConstraints.high.poleToPoleLengthConstraint)

        if to_terminal:
            pole_to_terminal_constraint = (self.request.lengthConstraints.low.poleToTerminalLengthConstraint
                                           if voltage == "low"
                                           else self.request.lengthConstraints.high.poleToTerminalLengthConstraint)
            length -= pole_to_terminal_constraint

        extra_poles = max(0, math.ceil(length / pole_to_pole_constraint) - 1)
        weight += extra_poles * pole_cost

        return weight

    def _compute_total_cost(self, graph):
        """
        Compute total cost (wire + poles) + HUGE penalty if any edge violates
        the length constraints from self.request.lengthConstraints.

        This guarantees that local gradient descent (and any other optimizer)
        will NEVER accept a pole position that makes any edge too long.
        """
        # 1. Wire + intermediate support-pole costs (already computed in edge weights)
        wire_cost = sum(d['weight'] for u, v, d in graph.edges(data=True))

        # 2. Pole costs
        num_poles = sum(1 for idx, data in graph.nodes(data=True) if data['type'] == "pole")
        pole_cost = self._costs.poleCost

        total = wire_cost + (num_poles * pole_cost)

        # 3. Constraint violation penalty (prevents any illegal move)
        violation_penalty = 0.0
        for u, v, data in graph.edges(data=True):
            length = data.get("length", 0.0)
            voltage = data.get("voltage", "low")

            u_type = graph.nodes[u]['type']
            v_type = graph.nodes[v]['type']

            # Same logic as split_long_edges_with_coords + calc_edge_weight
            if u_type == "terminal" or v_type == "terminal":
                # service drop (pole ↔ terminal or source ↔ terminal)
                max_len = (self.request.lengthConstraints.low.poleToTerminalLengthConstraint
                           if voltage == "low"
                           else self.request.lengthConstraints.high.poleToTerminalLengthConstraint)
            else:
                # trunk / pole-pole / source-pole
                max_len = (self.request.lengthConstraints.low.poleToPoleLengthConstraint
                           if voltage == "low"
                           else self.request.lengthConstraints.high.poleToPoleLengthConstraint)

            if length > max_len + 1e-4:  # tiny floating-point tolerance
                excess = length - max_len
                violation_penalty += MAX_EDGE_DIST_PENALTY * excess  # 10000 × meters over

        return total + violation_penalty

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

        all_points = np.array([n.coord_tuple for n in nodes])

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
                voltage = "low"
                w = self.calc_edge_weight(d, voltage=voltage)
                DG.add_edge(source_idx, p, weight=w, length=d, voltage=voltage)

        # 2: Bidirectional pole ↔ pole (undirected spans)
        for i in range(len(pole_indices)):
            for j in range(i + 1, len(pole_indices)):
                p1, p2 = pole_indices[i], pole_indices[j]
                d = dist_matrix[p1, p2]
                voltage = "low"
                w = self.calc_edge_weight(d, voltage=voltage)
                if 0.1 < d:
                    DG.add_edge(p1, p2, weight=w, length=d, voltage=voltage)
                    DG.add_edge(p2, p1, weight=w, length=d, voltage=voltage)

        # 3: poles → terminals (service drops)
        for p in pole_indices:
            for h in terminal_indices:
                d = dist_matrix[p, h]
                if 0.1 < d:
                    voltage = "low"
                    w = self.calc_edge_weight(d, voltage=voltage, to_terminal=True)
                    DG.add_edge(p, h, weight=w, length=d, voltage=voltage)

        # 4. Source to Terminals
        for h in terminal_indices:
            d = dist_matrix[source_idx, h]
            if 0.1 < d:
                voltage = "low"
                w = self.calc_edge_weight(d, voltage=voltage, to_terminal=True)
                DG.add_edge(source_idx, h, weight=w, length=d, voltage=voltage)

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

    @staticmethod
    def rename_poles(graph: Union[nx.DiGraph, nx.Graph]) -> Union[nx.DiGraph, nx.Graph]:
        """
        Extracts and processes nodes that are used within the provided pruned minimum
        spanning tree (MST). Marks the nodes as used, assigns them a name if they are
        of type "pole" and lack a name, and returns the list of used nodes.

        Args:
            graph: The pruned minimum spanning tree used to determine which
                nodes to mark and process.

        Returns:
            list: A list of nodes that are used, with appropriate properties updated
            based on the given MST and node attributes.
        """
        pole_counter = 1
        for idx, node_data in graph.nodes(data=True):
            if node_data['type'] == "pole":
                graph.nodes[idx]['used'] = True
                graph.nodes[idx]['name'] = f"Pole {pole_counter}"
                pole_counter += 1
        return graph

    @staticmethod
    def prune_dead_end_pole_branches(DG: Union[nx.Graph, nx.DiGraph]) -> Union[nx.Graph, nx.DiGraph]:
        """
        Prunes dead-end pole branches in a Directed Graph (DiGraph).

        This function removes leaf nodes in the provided graph that represent poles and do not serve
        any terminal nodes in their subtree. The pruning process continues iteratively until no such
        dead-end poles remain in the graph. It modifies a copy of the input graph without affecting
        the original.

        Args:
            DG: A directed graph representing the network structure.

        Returns:
            A new graph with dead-end pole branches removed.
        """
        DG = DG.copy()

        removed = True
        while removed:
            removed = False
            leaves = [n for n in DG.nodes(data=True) if DG.out_degree(n[0]) == 0]
            for leaf in leaves:
                if leaf[1]['type'] == "pole":
                    # Check if this leaf (or its subtree) serves any terminal
                    descendants = nx.descendants(DG, leaf[0]) | {leaf[0]}
                    if not any(DG.nodes(data=True)[d]['type'] == 'terminal' for d in descendants):
                        # No terminal served → safe to remove
                        predecessors = list(DG.predecessors(leaf[0]))
                        for pred in predecessors:
                            DG.remove_edge(pred, leaf[0])
                        DG.remove_node(leaf[0])
                        removed = True
        return DG

    def _recompute_edges_for_node(self, graph, node_idx: int):
        """Recompute length and weight for ALL incident edges (in + out)
        after moving a pole. Required because the graph is a DiGraph."""
        # Get ALL edges touching this node (incoming + outgoing)
        incident_edges = list(graph.in_edges(node_idx, data=True)) + \
                         list(graph.out_edges(node_idx, data=True))

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
        """Check that ALL incident edges (in + out) respect lengthConstraints."""
        incident_edges = list(graph.in_edges(node_idx, data=True)) + \
                         list(graph.out_edges(node_idx, data=True))

        for u, v, data in incident_edges:
            length = data.get('length', 0.0)
            voltage = data.get('voltage', 'low')

            # Determine max allowed length
            u_type = graph.nodes[u].get('type')
            v_type = graph.nodes[v].get('type')

            if u_type == 'terminal' or v_type == 'terminal':
                max_len = (self.request.lengthConstraints.low.poleToTerminalLengthConstraint
                           if voltage == 'low' else
                           self.request.lengthConstraints.high.poleToTerminalLengthConstraint)
            else:
                max_len = (self.request.lengthConstraints.low.poleToPoleLengthConstraint
                           if voltage == 'low' else
                           self.request.lengthConstraints.high.poleToPoleLengthConstraint)

            min_len = (self.request.lengthConstraints.low.poleToTerminalMinimumLength
                       if voltage == 'low' else
                       self.request.lengthConstraints.high.poleToTerminalMinimumLength)

            if (length < min_len + 0.01) or (length > max_len + 0.01):
                return False
        return True

    def _post_solver_local_opt(self, graph):
        """
        Performs post-solver optimization on the given graph by refining node placement and reducing redundancy.

        The method applies a series of optimization steps to improve the placement of nodes in the graph, potentially
        reducing costs and redundancy. This involves splitting long edges, optimizing poles using gradient-based
        techniques, and removing unnecessary poles. It continues iterating until the cost stabilizes. The final graph
        is then updated with renamed poles for clarity.

        Parameters:
        graph: The input graph to be optimized.

        Returns:
        The optimized graph after node refinement and placement adjustments.
        """

        # Final Node Optimization Placement
        graph = self.split_long_edges_with_coords(graph=graph)

        graph = self.rename_poles(graph)

        current_cost = self._compute_total_cost(graph)

        while True:
            previous_cost = current_cost

            graph = self._pole_gradient_optimizer(graph)
            graph = self._drop_redundant_poles(graph)

            current_cost = self._compute_total_cost(graph)

            if current_cost >= previous_cost:
                break

        return graph

    def _drop_redundant_poles(self, pruned_graph: nx.DiGraph) -> nx.DiGraph:
        """
        Removes redundant poles from the provided pruned graph to reduce the overall cost
        of the network while maintaining acceptable performance. This procedure iteratively
        evaluates each pole, attempting to drop it and re-solving the network configuration
        without increasing the total cost.

        Parameters:
            pruned_graph (nx.DiGraph): A directed graph representing the current pruned network,
                                       where nodes contain attributes including their type,
                                       coordinates, and name.

        Returns:
            nx.DiGraph: The optimized graph with redundant poles removed, ensuring minimal
                        cost increase through a simplified reverse deletion method.

        Raises:
            None
        """
        if self.request.debug >= 1:
            print("\n--- Starting Drop Phase (Simplified Reverse Deletion) ---")

        current_graph = pruned_graph.copy()
        cur_cost = self._compute_total_cost(current_graph)

        # Get all pole indices, sorted in reverse order (last added first)
        pole_indices = sorted(
            [idx for idx, data in current_graph.nodes(data=True)
             if data.get('type') == 'pole'],
            reverse=True
        )

        for pole_to_drop in pole_indices:
            if self.request.debug >= 2:
                print(f"  Trying to drop pole {pole_to_drop}...")

            # === Build coords and names from CURRENT graph (excluding the pole we're testing) ===
            coords_list = []
            names_list = []
            node_mapping = {}  # old_index -> new_index (for _build_nodes)

            idx_counter = 0
            for idx, data in sorted(current_graph.nodes(data=True)):  # sort for stable order
                if idx == pole_to_drop:
                    continue  # skip the pole we're trying to drop

                coords_list.append([data['lat'], data['lng']])
                names_list.append(data.get('name', f"Node {idx_counter}"))

                node_mapping[idx] = idx_counter
                idx_counter += 1

            coords_array = np.array(coords_list, dtype=float) if coords_list else np.empty((0, 2))

            # Rebuild trial nodes using the extracted data
            trial_nodes = self._build_nodes(coords_array, np.empty((0, 2)), names_list)

            # Re-solve from scratch on the reduced set
            DG = self.build_directed_graph_for_arborescence(trial_nodes)
            arbo_graph = self._minimum_spanning_arborescence_w_attrs(DG)
            pruned = self.prune_dead_end_pole_branches(arbo_graph)

            new_cost = self._compute_total_cost(pruned)

            # Accept removal only if cost does not increase
            if new_cost <= cur_cost + 1e-3:
                if self.request.debug >= 1:
                    print(f"Drop Phase: Removed redundant pole {pole_to_drop}. "
                          f"New cost: {new_cost:.2f} m (was {cur_cost:.2f})")

                current_graph = pruned
                cur_cost = new_cost
            else:
                if self.request.debug >= 1:
                    print(f"Drop Phase: Kept pole {pole_to_drop} "
                          f"(removing would increase cost to {new_cost:.2f} m)")

        if self.request.debug >= 1:
            print("--- Drop Phase Complete ---\n")

            self._plot_current_tree(current_graph, added_points=None, title="After Drop Phase")

        return current_graph

    def _get_local_incident_cost(self, graph, node_idx: int) -> float:
        """Calculate the sum of weights for all edges directly connected to node_idx."""
        incident_edges = list(graph.in_edges(node_idx, data=True)) + \
                         list(graph.out_edges(node_idx, data=True))
        return sum(data.get('weight', 0.0) for u, v, data in incident_edges)

    def _pole_gradient_optimizer(self, graph: Union[nx.Graph, nx.DiGraph]):
        """
        Local gradient descent on each pole using ONLY local incident edge costs,
        while strictly respecting lengthConstraints.
        """
        if len([n for n, d in graph.nodes(data=True) if d.get('type') == 'pole']) == 0:
            return graph  # nothing to optimize

        graph = graph.copy()

        one_meter_deg = 1.0 / 111111.0
        max_step_meters = 5.0  # keep movements very local
        max_iterations = 25
        grad_eps_m = 0.5  # finite difference step
        eps_deg = grad_eps_m * one_meter_deg

        if self.request.debug > 1:
            print(f"Starting constrained local gradient descent. Initial cost: {self._compute_total_cost(graph):.2f}")

        improved = False

        for node_idx, node_data in list(graph.nodes(data=True)):
            if node_data.get('type') != "pole":
                continue

            if self.request.debug > 1:
                print(f"Optimizing pole {node_idx} ({node_data.get('name', 'Pole')})...")

            # === Baseline Local Cost ===
            # We only track the cost of edges touching this specific pole.
            current_local_cost = self._get_local_incident_cost(graph, node_idx)

            for iteration in range(max_iterations):
                lat, lng = graph.nodes[node_idx]['lat'], graph.nodes[node_idx]['lng']

                # Helper to quickly evaluate local cost at a new test position
                def eval_pos(test_lat, test_lng):
                    graph.nodes[node_idx]['lat'] = test_lat
                    graph.nodes[node_idx]['lng'] = test_lng
                    self._recompute_edges_for_node(graph, node_idx)

                    if not self._all_edges_valid(graph, node_idx):
                        return 1e9
                    return self._get_local_incident_cost(graph, node_idx)

                # === Compute numerical gradient (using local costs) ===
                cost_p_lat = eval_pos(lat + eps_deg, lng)
                cost_m_lat = eval_pos(lat - eps_deg, lng)
                cost_p_lng = eval_pos(lat, lng + eps_deg)
                cost_m_lng = eval_pos(lat, lng - eps_deg)

                # Restore exact baseline position before line search
                graph.nodes[node_idx]['lat'] = lat
                graph.nodes[node_idx]['lng'] = lng
                self._recompute_edges_for_node(graph, node_idx)

                # Calculate gradient vectors
                grad_lat = (cost_p_lat - cost_m_lat) / (2 * eps_deg)
                grad_lng = (cost_p_lng - cost_m_lng) / (2 * eps_deg)
                grad_norm = math.sqrt(grad_lat ** 2 + grad_lng ** 2)

                if grad_norm < 1e-3:  # practically flat
                    if self.request.debug > 1:
                        print(f"  Pole {node_idx}: gradient near zero")
                    break

                # Direction of descent
                step_lat = -grad_lat / grad_norm * max_step_meters * one_meter_deg
                step_lng = -grad_lng / grad_norm * max_step_meters * one_meter_deg

                # === Backtracking line search ===
                best_step_lat = 0.0
                best_step_lng = 0.0
                best_new_local_cost = current_local_cost

                for scale in [1.0, 0.5, 0.25, 0.125, 0.0625]:
                    test_cost = eval_pos(lat + scale * step_lat, lng + scale * step_lng)

                    if test_cost < best_new_local_cost:
                        best_new_local_cost = test_cost
                        best_step_lat = scale * step_lat
                        best_step_lng = scale * step_lng

                # === Apply best valid step ===
                if best_step_lat != 0.0 or best_step_lng != 0.0:
                    graph.nodes[node_idx]['lat'] = lat + best_step_lat
                    graph.nodes[node_idx]['lng'] = lng + best_step_lng
                    self._recompute_edges_for_node(graph, node_idx)

                    improvement = current_local_cost - best_new_local_cost
                    current_local_cost = best_new_local_cost
                    improved = True

                    move_m = math.hypot(best_step_lat / one_meter_deg, best_step_lng / one_meter_deg)
                    if self.request.debug > 1 and improvement > 0.05:
                        print(f"  Iter {iteration + 1:2d}: moved {move_m:.1f}m, Δcost = -{improvement:.2f}")
                else:
                    # Restore one last time to be safe if no step was taken
                    graph.nodes[node_idx]['lat'] = lat
                    graph.nodes[node_idx]['lng'] = lng
                    self._recompute_edges_for_node(graph, node_idx)

                    if self.request.debug > 1:
                        print(f"  Iter {iteration + 1:2d}: no valid improving step")
                    break

        if self.request.debug > 1:
            final_cost = self._compute_total_cost(graph)
            print(f"Local GD finished. Final global cost: {final_cost:.2f} "
                  f"({'improved' if improved else 'no significant change'})")

        if self.request.debug > 0:
            self._plot_current_tree(graph, [], title="After Local Optimization")

        return graph

    @staticmethod
    def _get_num_poles_and_wire_length(graph: Union[nx.Graph, nx.DiGraph]):
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

    def split_long_edges_with_coords(self, graph: Union[nx.Graph, nx.DiGraph]) -> nx.DiGraph:
        """
        Break long edges (> max_length_m meters) into multiple shorter segments by
        inserting new intermediate pole nodes directly into the graph.

        Args:
            graph: The current minimum spanning arborescence (directed graph)

        Returns:
            Updated graph with inserted intermediate nodes.
        """
        new_graph = graph.copy()

        # Build node data lookup
        node_data_by_index = {
            n: data.copy()
            for n, data in new_graph.nodes(data=True)
        }

        if not node_data_by_index:
            return new_graph

        next_index = max(node_data_by_index) + 1

        for u, v, data in list(new_graph.edges(data=True)):

            u_type = new_graph.nodes[u]['type']
            v_type = new_graph.nodes[v]['type']

            length_m = data.get("length", 0.0)
            voltage = data.get("voltage", "unknown")

            # Default max length
            max_length_m = 30.0

            if u_type == "terminal" or v_type == "terminal":
                if voltage == "low":
                    max_length_m = self.request.lengthConstraints.low.poleToTerminalLengthConstraint
                if voltage == "high":
                    max_length_m = self.request.lengthConstraints.high.poleToTerminalLengthConstraint
            else:
                if voltage == "low":
                    max_length_m = self.request.lengthConstraints.low.poleToPoleLengthConstraint
                if voltage == "high":
                    max_length_m = self.request.lengthConstraints.high.poleToPoleLengthConstraint

            # Skip short edges
            if length_m <= max_length_m + 0.01:  # small floating-point tolerance
                continue

            start_node = node_data_by_index[u]
            end_node = node_data_by_index[v]

            start_coord = np.array([start_node["lat"], start_node["lng"]], dtype=float)
            end_coord = np.array([end_node["lat"], end_node["lng"]], dtype=float)

            direction = end_coord - start_coord

            # CORRECT way: use ceil so every segment <= max_length_m
            num_segments = int(np.ceil(length_m / max_length_m))
            segment_length = length_m / num_segments

            # Remove the original long edge
            new_graph.remove_edge(u, v)

            prev_idx = u
            for i in range(1, num_segments):
                fraction = i / num_segments
                current = start_coord + fraction * direction

                # Add new intermediate pole
                new_graph.add_node(
                    next_index,
                    lat=float(current[0]),
                    lng=float(current[1]),
                    type="pole",
                    name="pole",
                    used=True,
                )

                node_data_by_index[next_index] = {
                    "lat": float(current[0]),
                    "lng": float(current[1]),
                    "type": "pole",
                    "name": "pole",
                    "used": True,
                }

                new_graph.add_edge(
                    prev_idx,
                    next_index,
                    length=segment_length,
                    voltage=voltage,
                    weight=self.calc_edge_weight(segment_length, voltage=voltage),
                )

                prev_idx = next_index
                next_index += 1

            # Final segment to original end node
            new_graph.add_edge(
                prev_idx,
                v,
                length=segment_length,
                voltage=voltage,
                weight=self.calc_edge_weight(segment_length, voltage=voltage),
            )

        # remove original edges
        new_graph.graph.update(graph.graph)
        return new_graph

    def build_solver_result(self, graph: Union[nx.DiGraph, nx.Graph],
                            debug_info: Optional[Dict[str, Any]] = None) -> SolverResult:
        """
        Builds a SolverResult object from the provided graph and debug information.

        The function computes the cost estimation, number of poles, and length of wires
        required based on graph attributes. It also creates a detailed representation
        of nodes and edges present in the graph.

        Args:
            graph (Union[nx.DiGraph, nx.Graph]): Input graph containing nodes and edges
                with associated metadata such as geographic coordinates, types, and lengths.
            debug_info (Optional[Dict[str, Any]]): Additional debug information to include
                in the SolverResult if the request has debugging enabled.

        Returns:
            SolverResult: Aggregated result containing detailed metrics, node and edge
            representation, and cost estimates.
        """
        # rename poles to have a name
        graph = self.rename_poles(graph)

        # 3. Build edges + lengths
        num_poles, total_low_m, total_high_m = self._get_num_poles_and_wire_length(graph)

        pole_cost = self._costs.poleCost
        low_cost_m = self._costs.lowVoltageCostPerMeter
        high_cost_m = self._costs.highVoltageCostPerMeter

        low_wire_cost = total_low_m * low_cost_m
        high_wire_cost = total_high_m * high_cost_m
        total_wire_cost = low_wire_cost + high_wire_cost
        total_cost = total_wire_cost + num_poles * pole_cost

        node_dicts = [
            {
                "index": idx,
                "lat": n['lat'],
                "lng": n['lng'],
                "name": n['name'] or f"{n['type']} {idx}",
                "type": n['type'],
            }
            for idx, n in graph.nodes(data=True)
        ]

        edges = []

        for start_idx, end_idx, edge_data in graph.edges(data=True):
            start = graph.nodes[start_idx]
            end = graph.nodes[end_idx]
            edges.append(OutputEdge(
                start={"lat": start['lat'], "lng": start['lng'], "name": start['name'], "type": start['type']},
                end={"lat": end['lat'], "lng": end['lng'], "name": end['name'], "type": end['type']},
                lengthMeters=round(edge_data['length'], 4),
                voltage=edge_data["voltage"],
            ))

        return SolverResult(
            edges=edges,
            nodes=node_dicts,
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
