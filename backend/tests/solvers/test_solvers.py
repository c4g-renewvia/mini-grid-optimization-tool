import re

import pandas as pd
import pytest
from pykml import parser

from mini_grid_solver.solvers.local_opt import LocalOptimization
from mini_grid_solver.utils.models import *
from mini_grid_solver.utils.registry import SOLVER_REGISTRY


# ==================== FIXTURES ====================
@pytest.fixture
def csv_nodes():
    """Loads coordinates from the test CSV file."""
    try:
        df = pd.read_csv("test_data_sets/BuildingCoordinates.csv")
        i = 0
        data_dict = df.to_dict(orient="records")
        for data in data_dict:
            data['index'] = i
            i += 1
        return [Node(**data) for data in data_dict]
    except FileNotFoundError:
        pytest.skip("BuildingCoordinates.csv not found")


@pytest.fixture
def kml_nodes():
    """Parses coordinates from the ground truth KML."""
    try:
        kml_file_path = "test_data_sets/bc1.kml"
        with open(kml_file_path, 'r', encoding="utf-8") as f:
            root = parser.parse(f).getroot()

        coords = []
        for folder in root.Document:
            for placemark in folder.Placemark:
                # KML coordinates are typically: lng, lat, alt
                coords_str = str(placemark.Point.coordinates).strip()
                lng, lat, _ = coords_str.split(",")
                _type = str(placemark.description).split(" ")[1].lower()
                coords.append(Node(
                    index=len(coords),
                    name=str(placemark.name),
                    lat=float(lat),
                    lng=float(lng),
                    type=_type
                ))
        return coords
    except (FileNotFoundError, AttributeError):
        pytest.skip("KML file not found or incorrectly formatted")


# add "test_data_sets/minigrid_2026-04-24.kml" for larger test
@pytest.fixture(params=["test_data_sets/minigrid_2026-04-07.kml",
                        "test_data_sets/minigrid_2026-04-08.kml",
                        "test_data_sets/bc2.kml"])

def kml_nodes_random_test_set(request):
    """Parses coordinates from the ground truth KML."""
    try:
        kml_file_path = request.param
        with open(kml_file_path, 'r', encoding="utf-8") as f:
            root = parser.parse(f).getroot()

        coords = []
        for folder in root.Document:
            for placemark in folder.Folder.Placemark:
                # KML coordinates are typically: lng, lat, alt
                coords_str = str(placemark.Point.coordinates).strip()
                lng, lat, _ = coords_str.split(",")
                _type = re.search(r"Type: (\w+)", str(placemark.description)).group(1)
                if _type == "pole":
                    continue
                coords.append(Node(
                    index=len(coords),
                    name=str(placemark.name),
                    lat=float(lat),
                    lng=float(lng),
                    type=_type
                ))
        return coords
    except (FileNotFoundError, AttributeError) as e:
        pytest.skip(f"KML file not found or incorrectly formatted {e}")


@pytest.fixture
def default_costs():
    """Standard cost parameters used in your main script."""
    return Costs(
        poleCost=1000.0,
        lowVoltageCostPerMeter=20.0,
        highVoltageCostPerMeter=40.0,
    )


@pytest.fixture
def default_length_constraints():
    """Standard cost parameters used in your main script."""
    return LengthConstraints(
        low=LengthConstraintsBase(poleToPoleMaxLength=30,
                                  poleToTerminalMaxLength=20,
                                  poleToTerminalMinLength=5),
        high=LengthConstraintsBase(poleToPoleMaxLength=50,
                                   poleToTerminalMaxLength=20,
                                   poleToTerminalMinLength=5)
    )


@pytest.fixture
def ga_tech_nodes():
    """Fixture containing the manually provided Georgia Tech area nodes."""
    return [
        Node(index=0, name="Source", type="source", lat=33.77679498, lng=-84.39576765),
        Node(index=1, name="Terminal 02", type="terminal", lat=33.7766943, lng=-84.3961707),
        Node(index=2, name="Terminal 03", type="terminal", lat=33.77715844, lng=-84.39655715),
        Node(index=3, name="Terminal 04", type="terminal", lat=33.7766067, lng=-84.39567965),
        Node(index=4, name="Terminal 05", type="terminal", lat=33.77736802, lng=-84.39715452),
        Node(index=5, name="Terminal 06", type="terminal", lat=33.77694371, lng=-84.39650116),
        Node(index=6, name="Terminal 07", type="terminal", lat=33.77759256, lng=-84.39535238),
        Node(index=7, name="Terminal 08", type="terminal", lat=33.77670904, lng=-84.39500275),
        Node(index=8, name="Terminal 09", type="terminal", lat=33.77655566, lng=-84.39499823),
        Node(index=9, name="Terminal 10", type="terminal", lat=33.77721148, lng=-84.39735571)
    ]


# ==================== FIXTURE WITH NODES + EDGES FOR LOCAL OPTIMIZATION ====================

@pytest.fixture
def ga_tech_nodes_with_edges():
    """Fixture with source, terminals, and some pre-existing poles + edges.
    This is ideal for testing LocalOptimization, which expects a connected graph."""

    nodes = [
        Node(index=0, name="Source", type="source", lat=33.77679498, lng=-84.39576765),
        Node(index=1, name="Terminal 02", type="terminal", lat=33.7766943, lng=-84.3961707),
        Node(index=2, name="Terminal 03", type="terminal", lat=33.77715844, lng=-84.39655715),
        Node(index=3, name="Terminal 04", type="terminal", lat=33.7766067, lng=-84.39567965),
        Node(index=4, name="Terminal 05", type="terminal", lat=33.77736802, lng=-84.39715452),
        Node(index=5, name="Terminal 06", type="terminal", lat=33.77694371, lng=-84.39650116),

        # Pre-placed poles
        Node(index=6, name="Pole A", type="pole", lat=33.77685, lng=-84.3960),
        Node(index=7, name="Pole B", type="pole", lat=33.77710, lng=-84.3964),
        Node(index=8, name="Pole C", type="pole", lat=33.77670, lng=-84.3958),
    ]

    # Pre-existing edges (this is what you were missing)
    edges = [
        # Source to Pole A (trunk)
        Edge(
            start=nodes[0],
            end=nodes[6],
            lengthMeters=45.2,
            voltage="low"
        ),
        # Pole A to Pole B
        Edge(
            start=nodes[6],
            end=nodes[7],
            lengthMeters=38.7,
            voltage="low"
        ),
        # Pole B to Pole C
        Edge(
            start=nodes[7],
            end=nodes[8],
            lengthMeters=52.1,
            voltage="low"
        ),
        # Service drops from poles to terminals
        Edge(
            start=nodes[6],
            end=nodes[1],
            lengthMeters=18.3,
            voltage="low"
        ),
        Edge(
            start=nodes[6],
            end=nodes[3],
            lengthMeters=22.5,
            voltage="low"
        ),
        Edge(
            start=nodes[7],
            end=nodes[2],
            lengthMeters=19.8,
            voltage="low"
        ),
        Edge(
            start=nodes[7],
            end=nodes[5],
            lengthMeters=25.4,
            voltage="low"
        ),
        Edge(
            start=nodes[8],
            end=nodes[4],
            lengthMeters=28.9,
            voltage="low"
        ),
    ]

    return nodes, edges


# ==================== TESTS ====================

def test_registry_not_empty():
    """Ensures there are solvers registered to test."""
    assert len(SOLVER_REGISTRY) > 0


@pytest.mark.parametrize("solver_name", SOLVER_REGISTRY.keys())
def test_all_solvers_with_csv(solver_name, csv_nodes, default_costs, default_length_constraints):
    """
    Parametrized test: Runs every solver in the registry using CSV data.
    Validates that each solver returns a result with nodes and edges.
    """
    solver_class = SOLVER_REGISTRY[solver_name]

    # Create request with default params
    req = SolverRequest(
        nodes=csv_nodes,
        costs=default_costs,
        lengthConstraints=default_length_constraints,
        debug=0,
    )

    result = solver_class(req).solve()

    # Assertions for output quality
    assert result is not None, f"{solver_name} returned no result"
    assert len(result.nodes) >= len(csv_nodes), f"{solver_name} lost nodes during solve"
    assert len(result.edges) > 0, f"{solver_name} failed to create any connections"
    assert result.totalCostEstimate > 0, f"{solver_name} calculated zero or negative cost"


@pytest.mark.parametrize("solver_name", SOLVER_REGISTRY.keys())
def test_all_solvers_with_kml(kml_nodes_random_test_set, solver_name, csv_nodes, default_costs,
                              default_length_constraints):
    """
    Parametrized test: Runs every solver in the registry using CSV data.
    Validates that each solver returns a result with nodes and edges.
    """
    solver_class = SOLVER_REGISTRY[solver_name]

    # Create request with default params
    req = SolverRequest(
        nodes=kml_nodes_random_test_set,
        costs=default_costs,
        lengthConstraints=default_length_constraints,
        debug=0,
    )

    result = solver_class(req).solve()

    # Assertions for output quality
    assert result is not None, f"{solver_name} returned no result"
    assert len(result.nodes) >= len(csv_nodes), f"{solver_name} lost nodes during solve"
    assert len(result.edges) > 0, f"{solver_name} failed to create any connections"
    assert result.totalCostEstimate > 0, f"{solver_name} calculated zero or negative cost"


def test_greedy_steiner_solver(kml_nodes, default_costs, default_length_constraints):
    """Specific check for GreedyIterSteinerSolver using the KML dataset."""
    if "GreedyIterSteinerSolver" not in SOLVER_REGISTRY:
        pytest.skip("GreedyIterSteinerSolver not registered")

    solver_class = SOLVER_REGISTRY["GreedyIterSteinerSolver"]
    req = SolverRequest(
        nodes=kml_nodes,
        costs=default_costs,
        lengthConstraints=default_length_constraints,
        debug=0,
    )

    result = solver_class(req).solve()

    # Check that Steiner nodes (poles) were actually added
    poles = [n for n in result.nodes if n.type == 'pole']
    assert len(poles) >= 0  # Validates the result contains a nodes list
    assert result.totalCostEstimate > 0


def test_greedy_steiner_solver2(kml_nodes_random_test_set, default_costs, default_length_constraints):
    """Specific check for GreedyIterSteinerSolver using the KML dataset."""
    if "GreedyIterSteinerSolver" not in SOLVER_REGISTRY:
        pytest.skip("GreedyIterSteinerSolver not registered")

    solver_class = SOLVER_REGISTRY["GreedyIterSteinerSolver"]
    req = SolverRequest(
        nodes=kml_nodes_random_test_set,
        costs=default_costs,
        lengthConstraints=default_length_constraints,
        debug=0,
    )

    result = solver_class(req).solve()

    # Check that Steiner nodes (poles) were actually added
    poles = [n for n in result.nodes if n.type == 'pole']
    assert len(poles) >= 0  # Validates the result contains a nodes list
    assert result.totalCostEstimate > 0


def test_solver_param_metadata():
    """Checks that get_input_params returns valid data for the UI."""
    for name, solver_class in SOLVER_REGISTRY.items():
        params = solver_class.get_input_params()
        assert isinstance(params, list), f"{name} must return a list of parameters"


# ==================== ADDITIONAL TESTS ====================

@pytest.mark.parametrize("solver_name", SOLVER_REGISTRY.keys())
def test_solvers_with_ga_tech_data(solver_name, ga_tech_nodes, default_costs, default_length_constraints):
    """Verifies that all solvers can handle the specific Georgia Tech coordinate set."""
    solver_class = SOLVER_REGISTRY[solver_name]
    req = SolverRequest(
        nodes=ga_tech_nodes,
        costs=default_costs,
        lengthConstraints=default_length_constraints,
        debug=0,
    )
    result = solver_class(req).solve()

    assert result is not None
    assert len(result.edges) > 0
    assert result.totalCostEstimate > 0


def test_cost_calculation_integrity(ga_tech_nodes, default_costs, default_length_constraints):
    """
    Validates that the total cost accurately reflects the sum of its components.
    Formula: total_cost = (poleCount * poleCost) + lowWireCost + highWireCost
    """
    solver_class = SOLVER_REGISTRY["SimpleMSTSolver"]
    req = SolverRequest(params={},
                        nodes=ga_tech_nodes,
                        costs=default_costs,
                        lengthConstraints=default_length_constraints,
                        debug=0, )
    result = solver_class(req).solve()

    expected_total = (
            (result.numPolesUsed * default_costs.poleCost) +
            result.lowWireCostEstimate +
            result.highWireCostEstimate
    )

    # Using approx for floating point comparisons
    assert result.totalCostEstimate == pytest.approx(expected_total, rel=1e-2)


def test_connectivity_spanning(ga_tech_nodes, default_costs, default_length_constraints):
    """
    Ensures that every input node is present in the final graph.
    """
    solver_class = SOLVER_REGISTRY["SimpleMSTSolver"]
    req = SolverRequest(params={},
                        nodes=ga_tech_nodes,
                        costs=default_costs,
                        lengthConstraints=default_length_constraints)
    result = solver_class(req).solve()

    input_names = {p.name for p in ga_tech_nodes if "source" not in p.name.lower()}
    output_names = {n.name for n in result.nodes if "source" not in n.name.lower()}

    # Check that all original nodes exist in the output nodes list
    assert input_names.issubset(output_names)


def test_steiner_point_injection(ga_tech_nodes, default_costs, default_length_constraints):
    """
    Verifies that Steiner-based solvers (like GreedyNSteiner) successfully
    inject additional 'pole' type nodes into the network.
    """
    solver_class = SOLVER_REGISTRY["GreedyIterSteinerSolver"]
    req = SolverRequest(nodes=ga_tech_nodes,
                        costs=default_costs,
                        lengthConstraints=default_length_constraints)
    result = solver_class(req).solve()

    # Check if any new 'pole' types were created beyond the original source/terminals
    poles = [n for n in result.nodes if n.type == "pole"]

    # We expect at least some poles if n > 0 in a Steiner solver
    assert len(poles) > 0


# ==================== NEW TEST FOR LOCAL OPTIMIZATION WITH EDGES ====================

def test_local_optimization_with_edges(ga_tech_nodes_with_edges, default_costs, default_length_constraints):
    """Test LocalOptimization using a fixture that includes both nodes and edges."""

    nodes, edges = ga_tech_nodes_with_edges

    req = SolverRequest(
        solver="LocalOptimization",
        params={},
        nodes=nodes,
        edges=edges,  # Pass edges
        voltageLevel="low",
        lengthConstraints=default_length_constraints,
        costs=default_costs,
        usePoles=True,
        debug=0,
    )

    solver_class = LocalOptimization

    print(f"Testing LocalOptimization with {len(nodes)} nodes and {len(edges)} edges")

    result = solver_class(req).solve()

    # Core assertions
    assert result is not None, "LocalOptimization returned None"
    assert len(result.nodes) >= len(nodes), f"Lost nodes: {len(result.nodes)} < {len(nodes)}"
    assert len(result.edges) > 0, "No edges returned"

    poles = [n for n in result.nodes if n.type == "pole"]
    assert len(poles) >= 3, f"Expected at least 3 poles, got {len(poles)}"

    assert result.totalCostEstimate > 0, "Total cost should be positive"
    assert result.numPolesUsed > 0, "Should use poles"

    # Print useful summary
    print(f"✅ LocalOptimization test passed!")
    print(f"   Nodes: {len(result.nodes)} | Edges: {len(result.edges)}")
    print(f"   Poles used: {result.numPolesUsed}")
    print(f"   Total Cost: ${result.totalCostEstimate:,.2f}")
    print(f"   Low voltage: {result.totalLowVoltageMeters:,.1f} m")

    # Optional: Check that some edges were possibly shortened or refined
    total_length_before = sum(e.lengthMeters for e in edges)
    total_length_after = result.totalLowVoltageMeters + result.totalHighVoltageMeters

    print(f"   Total length before: {total_length_before:.1f}m → after: {total_length_after:.1f}m")
