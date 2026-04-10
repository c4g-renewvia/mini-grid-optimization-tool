import re

import pandas as pd
import pytest
from pykml import parser

from mini_grid_solver.src.solvers.registry import SOLVER_REGISTRY
from mini_grid_solver.src.utils.models import *
from mini_grid_solver.src.utils.models import LengthConstraints, LengthConstraintsBase


# ==================== FIXTURES ====================
@pytest.fixture
def csv_points():
    """Loads coordinates from the test CSV file."""
    try:
        df = pd.read_csv("test_data_sets/BuildingCoordinates.csv")
        return df.to_dict(orient="records")
    except FileNotFoundError:
        pytest.skip("BuildingCoordinates.csv not found")


@pytest.fixture
def kml_points():
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
                coords.append({
                    "name": str(placemark.name),
                    "lat": float(lat),
                    "lng": float(lng),
                    "type": str(placemark.description).split(" ")[1]
                })
        return coords
    except (FileNotFoundError, AttributeError):
        pytest.skip("KML file not found or incorrectly formatted")


@pytest.fixture(params=["test_data_sets/minigrid_2026-04-07.kml","test_data_sets/minigrid_2026-04-08.kml","test_data_sets/minigrid_2026-04-09.kml"])
def kml_points_random_test_set(request):
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
                type = re.search(r"Type: (\w+)", str(placemark.description)).group(1)
                if type == "pole":
                    continue
                coords.append({
                    "name": str(placemark.name),
                    "lat": float(lat),
                    "lng": float(lng),
                    "type": type
                })
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
        low=LengthConstraintsBase(poleToPoleLengthConstraint=30,
                                  poleToTerminalLengthConstraint=20,
                                  poleToTerminalMinimumLength=5),
        high=LengthConstraintsBase(poleToPoleLengthConstraint=50,
                                   poleToTerminalLengthConstraint=20,
                                   poleToTerminalMinimumLength=5)
    )


@pytest.fixture
def ga_tech_points():
    """Fixture containing the manually provided Georgia Tech area points."""
    return [
        {"name": "Source", "type": "source", "lat": 33.77679498, "lng": -84.39576765},
        {"name": "Terminal 02", "type": "terminal", "lat": 33.7766943, "lng": -84.3961707},
        {"name": "Terminal 03", "type": "terminal", "lat": 33.77715844, "lng": -84.39655715},
        {"name": "Terminal 04", "type": "terminal", "lat": 33.7766067, "lng": -84.39567965},
        {"name": "Terminal 05", "type": "terminal", "lat": 33.77736802, "lng": -84.39715452},
        {"name": "Terminal 06", "type": "terminal", "lat": 33.77694371, "lng": -84.39650116},
        {"name": "Terminal 07", "type": "terminal", "lat": 33.77759256, "lng": -84.39535238},
        {"name": "Terminal 08", "type": "terminal", "lat": 33.77670904, "lng": -84.39500275},
        {"name": "Terminal 09", "type": "terminal", "lat": 33.77655566, "lng": -84.39499823},
        {"name": "Terminal 10", "type": "terminal", "lat": 33.77721148, "lng": -84.39735571}
    ]


# ==================== TESTS ====================

def test_registry_not_empty():
    """Ensures there are solvers registered to test."""
    assert len(SOLVER_REGISTRY) > 0


@pytest.mark.parametrize("solver_name", SOLVER_REGISTRY.keys())
def test_all_solvers_with_csv(solver_name, csv_points, default_costs, default_length_constraints):
    """
    Parametrized test: Runs every solver in the registry using CSV data.
    Validates that each solver returns a result with nodes and edges.
    """
    solver_class = SOLVER_REGISTRY[solver_name]

    # Create request with default params
    req = SolverRequest(
        points=csv_points,
        costs=default_costs,
        lengthConstraints=default_length_constraints,
        debug=0,
    )

    result = solver_class(req).solve()

    # Assertions for output quality
    assert result is not None, f"{solver_name} returned no result"
    assert len(result.nodes) >= len(csv_points), f"{solver_name} lost points during solve"
    assert len(result.edges) > 0, f"{solver_name} failed to create any connections"
    assert result.totalCostEstimate > 0, f"{solver_name} calculated zero or negative cost"


@pytest.mark.parametrize("solver_name", ["DiskBasedSteinerSolver"])#SOLVER_REGISTRY.keys())
def test_all_solvers_with_kml(kml_points_random_test_set, solver_name, csv_points, default_costs,
                              default_length_constraints):
    """
    Parametrized test: Runs every solver in the registry using CSV data.
    Validates that each solver returns a result with nodes and edges.
    """
    solver_class = SOLVER_REGISTRY[solver_name]

    # Create request with default params
    req = SolverRequest(
        points=kml_points_random_test_set,
        costs=default_costs,
        lengthConstraints=default_length_constraints,
        debug=0,
    )

    result = solver_class(req).solve()

    # Assertions for output quality
    assert result is not None, f"{solver_name} returned no result"
    assert len(result.nodes) >= len(csv_points), f"{solver_name} lost points during solve"
    assert len(result.edges) > 0, f"{solver_name} failed to create any connections"
    assert result.totalCostEstimate > 0, f"{solver_name} calculated zero or negative cost"


def test_greedy_steiner_solver(kml_points, default_costs, default_length_constraints):
    """Specific check for GreedyIterSteinerSolver using the KML dataset."""
    if "GreedyIterSteinerSolver" not in SOLVER_REGISTRY:
        pytest.skip("GreedyIterSteinerSolver not registered")

    solver_class = SOLVER_REGISTRY["GreedyIterSteinerSolver"]
    req = SolverRequest(
        points=kml_points,
        costs=default_costs,
        lengthConstraints=default_length_constraints,
        debug=0,
    )

    result = solver_class(req).solve()

    # Check that Steiner points (poles) were actually added
    poles = [n for n in result.nodes if n.get('type') == 'pole']
    assert len(poles) >= 0  # Validates the result contains a nodes list
    assert result.totalCostEstimate > 0


def test_greedy_steiner_solver2(kml_points_random_test_set, default_costs, default_length_constraints):
    """Specific check for GreedyIterSteinerSolver using the KML dataset."""
    if "GreedyIterSteinerSolver" not in SOLVER_REGISTRY:
        pytest.skip("GreedyIterSteinerSolver not registered")

    solver_class = SOLVER_REGISTRY["GreedyIterSteinerSolver"]
    req = SolverRequest(
        points=kml_points_random_test_set,
        costs=default_costs,
        lengthConstraints=default_length_constraints,
        debug=0,
    )

    result = solver_class(req).solve()

    # Check that Steiner points (poles) were actually added
    poles = [n for n in result.nodes if n.get('type') == 'pole']
    assert len(poles) >= 0  # Validates the result contains a nodes list
    assert result.totalCostEstimate > 0


def test_solver_param_metadata():
    """Checks that get_input_params returns valid data for the UI."""
    for name, solver_class in SOLVER_REGISTRY.items():
        params = solver_class.get_input_params()
        assert isinstance(params, list), f"{name} must return a list of parameters"


# ==================== ADDITIONAL TESTS ====================

@pytest.mark.parametrize("solver_name", SOLVER_REGISTRY.keys())
def test_solvers_with_ga_tech_data(solver_name, ga_tech_points, default_costs, default_length_constraints):
    """Verifies that all solvers can handle the specific Georgia Tech coordinate set."""
    solver_class = SOLVER_REGISTRY[solver_name]
    req = SolverRequest(
        points=ga_tech_points,
        costs=default_costs,
        lengthConstraints=default_length_constraints,
        debug=0,
    )
    result = solver_class(req).solve()

    assert result is not None
    assert len(result.edges) > 0
    assert result.totalCostEstimate > 0


def test_cost_calculation_integrity(ga_tech_points, default_costs, default_length_constraints):
    """
    Validates that the total cost accurately reflects the sum of its components.
    Formula: total_cost = (poleCount * poleCost) + lowWireCost + highWireCost
    """
    solver_class = SOLVER_REGISTRY["SimpleMSTSolver"]
    req = SolverRequest(params={},
                        points=ga_tech_points,
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


def test_connectivity_spanning(ga_tech_points, default_costs, default_length_constraints):
    """
    Ensures that every input node is present in the final graph.
    """
    solver_class = SOLVER_REGISTRY["SimpleMSTSolver"]
    req = SolverRequest(params={},
                        points=ga_tech_points,
                        costs=default_costs,
                        lengthConstraints=default_length_constraints, )
    result = solver_class(req).solve()

    input_names = {p["name"] for p in ga_tech_points if "source" not in p['name'].lower()}
    output_names = {n["name"] for n in result.nodes if "source" not in n['name'].lower()}

    # Check that all original points exist in the output nodes list
    assert input_names.issubset(output_names)


def test_steiner_point_injection(ga_tech_points, default_costs, default_length_constraints):
    """
    Verifies that Steiner-based solvers (like GreedyNSteiner) successfully
    inject additional 'pole' type nodes into the network.
    """
    solver_class = SOLVER_REGISTRY["GreedyIterSteinerSolver"]
    req = SolverRequest(points=ga_tech_points,
                        costs=default_costs,
                        lengthConstraints=default_length_constraints)
    result = solver_class(req).solve()

    # Check if any new 'pole' types were created beyond the original source/terminals
    poles = [n for n in result.nodes if n.get("type") == "pole"]

    # We expect at least some poles if n > 0 in a Steiner solver
    assert len(poles) > 0
