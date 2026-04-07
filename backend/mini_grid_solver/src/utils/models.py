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
    points: List[Dict[str, Union[float, str, None]]]
    lengthConstraints: LengthConstraints
    costs: Costs
    debug: int = 0



class Solver(BaseModel):
    name: str
    params: List[Dict[str, Any]] = []


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
    is_candidate: bool = False
    used: bool = False

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,  # we will mutate 'used' and 'name' during processing
    )

    @property
    def coord_tuple(self) -> Tuple[float, float]:
        return self.lat, self.lng


class OutputEdge(BaseModel):
    start: Dict[str, Any]  # will contain lat, lng, name, type
    end: Dict[str, Any]
    lengthMeters: float = Field(..., ge=0)
    voltage: Literal["low", "high", "unknown"] = "unknown"


class SolverResult(BaseModel):
    edges: List[OutputEdge]
    nodes: List[Dict[str, Any]]  # minimal dicts for frontend (lat,lng,name,type,index,...)
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
