# optimizers/base.py
from abc import ABC, abstractmethod
from typing import Union

import networkx as nx
import numpy as np

from ..mixins.costs import CostMixin
from ..mixins.geo import GeoMixin
from ..mixins.graph import GraphMixin
from ..mixins.post_processor import PostProcessingMixin
from ..utils.models import *

MAX_EDGE_DIST_PENALTY = 10000


class BaseMiniGridSolver(
    GeoMixin,
    CostMixin,
    GraphMixin,
    PostProcessingMixin,
    ABC):
    """
    Base class for solving Minigrid problems with integrated features for
    geometric, cost-based, graph-based, and post-processing solutions.

    The BaseMiniGridSolver class serves as a foundational framework for solving
    problems involving nodes, edges, and connectivity analysis using graph-based
    methods. It provides mechanisms to parse and validate input, normalize node
    ordering, construct graphs from input data, and generate solver results
    including detailed cost estimates and debug information. This class is designed
    to be extended with specific implementations of `_solve` tailored to unique
    problem requirements.

    Attributes:
        request (SolverRequest): Contains the input data and configuration necessary
            for solving a Minigrid problem.
    """

    def __init__(self, request: SolverRequest):
        """Initialize the solver with a request and empty working state.

        Args:
            request: Input data and configuration for the solve operation.
        """
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
        """Return the input parameters supported by this solver.

        Returns:
            An empty list because this base solver exposes no additional parameters.
        """
        return []

    # ─── Core abstract method ───────────────────────────────────────────────

    @abstractmethod
    def _solve(self) -> Union[nx.DiGraph, nx.Graph]:
        """Solve the problem and return its graph representation.

        Subclasses implement this method with the algorithm-specific solution logic.

        Returns:
            A directed or undirected graph representing the solution.
        """
        raise NotImplementedError("Subclasses must implement this method")

    # ─── Class methods ───────────────────────────────────────────────

    def parse_and_validate_input(self):
        """Validate the request and initialize normalized solver state.

        Raises:
            ValueError: If fewer than two nodes or coordinates are provided, or if
                the request has zero or multiple source nodes.
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

    def build_solver_result(self, graph: Union[nx.DiGraph, nx.Graph],
                            debug_info: Optional[Dict[str, Any]] = None) -> SolverResult:
        """Build a normalized solver result and calculate its cost estimates.

        Args:
            graph: The graph representing the infrastructure solution.
            debug_info: Optional debugging information to include when debug mode is
                enabled.

        Returns:
            The normalized result, including graph data, cost estimates, and optional
            debugging information.
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
            edges=edges,
            nodes=nodes,
            totalLowVoltageMeters=round(total_low_m, 2),
            totalHighVoltageMeters=round(total_high_m, 2),
            numPolesUsed=num_poles,
            totalEdgeLengthMeters=round(total_low_m + total_high_m, 2),
            poleCostEstimate=round(num_poles * pole_cost, 2),
            lowWireCostEstimate=round(low_wire_cost, 2),
            highWireCostEstimate=round(high_wire_cost, 2),
            totalWireCostEstimate=round(total_wire_cost, 2),
            totalCostEstimate=round(total_cost, 2),
            debug=debug_info if self.request.debug else None,
        )


    def solve(self) -> SolverResult:
        """Validate the request, run the solver, and build its result.

        Returns:
            The standardized result for the solved request.

        Raises:
            ValueError: If the request has invalid node or source data.
        """

        # Parse input and input into abstract solver method
        self.parse_and_validate_input()

        # Pass to implemented solver
        graph = self._solve()

        return self.build_solver_result(graph)
