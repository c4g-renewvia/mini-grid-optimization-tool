from typing import List, Dict, Any, Optional, Literal, Tuple
from typing import Union

from pydantic import BaseModel, Field, ConfigDict

poleToTerminalMaxLength: float


class LengthConstraintsBase(BaseModel):
    """Pole spacing limits, in meters, for one voltage level."""

    poleToPoleMaxLength: float = 30.0
    poleToTerminalMaxLength: float = 20.0
    poleToTerminalMinLength: float = 5.0


class LengthConstraints(BaseModel):
    """Separate pole spacing limits for low- and high-voltage connections."""

    low: LengthConstraintsBase
    high: LengthConstraintsBase


class Costs(BaseModel):
    """Unit costs used when estimating poles and low- and high-voltage wire."""

    poleCost: float = 1000.0
    lowVoltageCostPerMeter: float = 30.0
    highVoltageCostPerMeter: float = 50.0


class SolverInputParams(BaseModel):
    """Describe one configurable solver parameter for the frontend."""

    name: str
    type: Literal["int", "float", "bool", "str", "list"]
    default: Union[str, float]
    description: str
    min: Optional[float] = None
    max: Optional[float] = None
    options: Optional[List[Any]] = None


class Solver(BaseModel):
    """Expose a registered solver and the parameters it accepts."""

    name: str
    params: List[SolverInputParams]


class Node(BaseModel):
    """
    Unified representation of any point in the network:
    source, terminal, intermediate pole, info, or pme.
    """
    index: int
    lat: float
    lng: float
    type: Literal["source", "terminal", "pole", "info", "pme"]
    name: Optional[str] = None

    model_config = ConfigDict(frozen=True)

def get_node_coord_tuple(node: Node) -> Tuple[float, float]:
    """Extract a node's geographic coordinates.

    Args:
        node: The node whose coordinates are requested.

    Returns:
        Tuple[float, float]: Latitude and longitude, in degrees.
    """
    return node.lat, node.lng

class Edge(BaseModel):
    """Represent a network connection and its measured length and voltage."""

    start: Node
    end: Node
    lengthMeters: float
    voltage: Literal["low", "high", "unknown"] = "unknown"


class SolverRequest(BaseModel):
    """Input payload describing a mini-grid layout and the solve configuration.

    Args:
        solver: Registered solver class name to run.
        params: Solver-specific options.
        nodes: Source, terminal, and any existing pole or informational nodes.
        edges: Existing connections to use when supported by the selected solver.
        voltageLevel: Voltage level used for edge constraints and wire costs.
        lengthConstraints: Per-voltage limits for pole-to-pole and
            pole-to-terminal spans.
        costs: Pole and voltage-specific wire costs.
        usePoles: Whether the requested solution may use poles.
        debug: Debug verbosity level; zero disables debug output.
    """
    solver: str = "SimpleMSTSolver"
    params: Dict[str, Any] = {}
    nodes: List[Node]
    edges: List[Edge] = []
    voltageLevel: Literal["low", "high"] = "low"
    lengthConstraints: LengthConstraints
    costs: Costs
    usePoles: bool = True
    debug: int = 0


class SolverResult(BaseModel):
    """Return the solved network together with length and cost summaries."""

    edges: List[Edge]
    nodes: List[Node]
    totalLowVoltageMeters: float = 0.0
    totalHighVoltageMeters: float = 0.0
    numPolesUsed: int = 0
    totalEdgeLengthMeters: float = 0.0
    poleCostEstimate: float = 0.0
    lowWireCostEstimate: float = 0.0
    highWireCostEstimate: float = 0.0
    totalWireCostEstimate: float = 0.0
    totalCostEstimate: float = 0.0

    debug: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        extra="forbid",
    )
