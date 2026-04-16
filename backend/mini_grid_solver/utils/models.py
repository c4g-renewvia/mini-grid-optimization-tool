from typing import List, Dict, Any, Optional, Literal, Tuple
from typing import Union

from pydantic import BaseModel, Field, ConfigDict

poleToTerminalLengthConstraint: float


class LengthConstraintsBase(BaseModel):
    poleToPoleLengthConstraint: float = 30.0
    poleToTerminalLengthConstraint: float = 20.0
    poleToTerminalMinimumLength: float = 5.0


class LengthConstraints(BaseModel):
    low: LengthConstraintsBase
    high: LengthConstraintsBase


class Costs(BaseModel):
    poleCost: float = 1000.0
    lowVoltageCostPerMeter: float = 30.0
    highVoltageCostPerMeter: float = 50.0


class SolverInputParams(BaseModel):
    name: str
    type: Literal["int", "float", "bool", "str", "list"]
    default: Union[str, float]
    description: str
    min: Optional[float] = None
    max: Optional[float] = None
    options: Optional[List[Any]] = None


class Solver(BaseModel):
    name: str
    params: List[SolverInputParams]


class Node(BaseModel):
    """
    Unified representation of any point in the network:
    source, terminal, or intermediate pole.
    """
    index: int
    lat: float
    lng: float
    type: Literal["source", "terminal", "pole"]
    name: Optional[str] = None

    model_config = ConfigDict(frozen=True)

def get_node_coord_tuple(node: Node) -> Tuple[float, float]:
    return node.lat, node.lng

class Edge(BaseModel):
    start: Node
    end: Node
    lengthMeters: float
    voltage: Literal["low", "high", "unknown"] = "unknown"


class SolverRequest(BaseModel):
    """Pydantic model for incoming optimization request from frontend.

    Args:
        points: List of dicts with 'lat', 'lng', and optional 'name'.
        costs: Dict with poleCost, lowVoltageCostPerMeter, highVoltageCostPerMeter.
        lengthConstraints: {'low':
        debug: Optional flag to enable debug output.
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
    edges: List[Edge]
    nodes: List[Node]
    totalLowVoltageMeters: float = 0.0
    totalHighVoltageMeters: float = 0.0
    numPolesUsed: int = 0
    poleCostEstimate: float = 0.0
    lowWireCostEstimate: float = 0.0
    highWireCostEstimate: float = 0.0
    totalWireCostEstimate: float = 0.0
    totalCostEstimate: float = 0.0

    debug: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        extra="forbid",
    )
