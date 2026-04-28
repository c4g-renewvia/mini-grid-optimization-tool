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

    # ─── Core abstract method ───────────────────────────────────────────────

    @abstractmethod
    def _solve(self) -> Union[nx.DiGraph, nx.Graph]:
        """
        Abstract method to solve a problem and return a graph representation of its solution.

        The `_solve` method is intended to be implemented by subclasses with specific logic
        to process data or configurations and produce a directed or undirected graph based
        on the problem's requirements.

        Returns:
            Union[nx.DiGraph, nx.Graph]: A graph representing the solution to the problem.
        """
        raise NotImplementedError("Subclasses must implement this method")

    # ─── Class methods ───────────────────────────────────────────────

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

    def build_solver_result(self, graph: Union[nx.DiGraph, nx.Graph],
                            debug_info: Optional[Dict[str, Any]] = None) -> SolverResult:
        """
        Processes a graph to compute and build a result containing ordered nodes, remapped
        edges, and cost estimations related to poles and wires. The solution enforces
        a consistent node ordering and calculates cost summaries for reporting.

        Args:
            graph: A graph structure provided as either a `nx.DiGraph` or `nx.Graph`
                instance. The graph represents the infrastructure network to solve.
            debug_info: An optional dictionary containing information intended for
                debugging purposes. If provided, it is included in the solution result
                when debugging mode is enabled.

        Returns:
            SolverResult: An object containing the processed graph orderings, cost
            estimates for poles and wires, and optionally the debugging information.
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
            poleCostEstimate=round(num_poles * pole_cost, 2),
            lowWireCostEstimate=round(low_wire_cost, 2),
            highWireCostEstimate=round(high_wire_cost, 2),
            totalWireCostEstimate=round(total_wire_cost, 2),
            totalCostEstimate=round(total_cost, 2),
            debug=debug_info if self.request.debug else None,
        )


    def solve(self) -> SolverResult:
        """
        Method called by the server to solve the given request.
        Solves the given problem and return the result in a standardized format.

        This method integrates the flow of problem-solving by parsing and
        validating the input, solving the problem using the implemented solver,
        and constructing a solver result based on the computed solution.

        Returns:
            SolverResult: An object that encapsulates the result of the problem-solving
                          process. This includes details such as the solved data
                          representation.

        Raises:
            ValidationError: If the input provided does not meet required criteria
                             during the parsing and validation phase.

            SolverException: If an error occurs during the solving process, such as
                             an invalid state in the graph.
        """

        # Parse input and input into abstract solver method
        self.parse_and_validate_input()

        # Pass to implemented solver
        graph = self._solve()

        return self.build_solver_result(graph)
