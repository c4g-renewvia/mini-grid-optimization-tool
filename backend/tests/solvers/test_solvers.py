import re
from pathlib import Path
from unittest.mock import Mock

import networkx as nx
import pandas as pd
import pytest
from pykml import parser

from mini_grid_solver.solvers.local_opt import LocalOptimization
from mini_grid_solver.utils.models import *
from mini_grid_solver.utils.registry import SOLVER_REGISTRY

TEST_DATASET_DIR = "test_data_sets"


def _count_terminals(nodes) -> int:
    return sum(1 for node in nodes if node.type == "terminal")


# ==================== FIXTURES ====================
@pytest.fixture(params=[
    f"{TEST_DATASET_DIR}/bc1.kml",
    f"{TEST_DATASET_DIR}/bc2.kml",
])
def kml_nodes(request):
    """Parses coordinates from the bc1/bc2 ground-truth KML datasets."""
    try:
        kml_file_path = request.param
        with open(kml_file_path, 'r', encoding="utf-8") as f:
            root = parser.parse(f).getroot()

        coords = []
        placemarks = []

        # bc1 has Document-level placemarks; bc2 stores them inside Folder(s).
        if hasattr(root.Document, "Placemark"):
            placemarks.extend(list(root.Document.Placemark))
        if hasattr(root.Document, "Folder"):
            for folder in root.Document.Folder:
                if hasattr(folder, "Placemark"):
                    placemarks.extend(list(folder.Placemark))

        for placemark in placemarks:
            if not hasattr(placemark, "Point") or not hasattr(placemark.Point, "coordinates"):
                continue

            description_text = str(getattr(placemark, "description", ""))
            match = re.search(r"Type:\s*(\w+)", description_text)
            if not match:
                continue

            coords_str = str(placemark.Point.coordinates).strip()
            lng, lat, _ = coords_str.split(",")
            coords.append(Node(
                index=len(coords),
                name=str(placemark.name),
                lat=float(lat),
                lng=float(lng),
                type=match.group(1).lower()
            ))

        if not coords:
            pytest.skip(f"No valid node placemarks found in: {kml_file_path}")
        return coords
    except FileNotFoundError:
        pytest.skip(f"KML file not found: {kml_file_path}")
    except AttributeError:
        pytest.skip(f"KML file incorrectly formatted: {kml_file_path}")


# add f"{TEST_DATASET_DIR}/minigrid_2026-04-24.kml" for larger test
@pytest.fixture(params=[
    f"{TEST_DATASET_DIR}/minigrid_2026-04-07.kml",
    f"{TEST_DATASET_DIR}/minigrid_2026-04-08.kml",
])
def kml_nodes_random_test_set(request):
    """Parses random minigrid KML datasets and keeps only source/terminal points."""
    try:
        kml_file_path = request.param
        with open(kml_file_path, 'r', encoding="utf-8") as f:
            root = parser.parse(f).getroot()

        coords = []
        for folder in getattr(root.Document, "Folder", []):
            nested_folders = list(getattr(folder, "Folder", [])) or [folder]
            for nested_folder in nested_folders:
                for placemark in getattr(nested_folder, "Placemark", []):
                    if not hasattr(placemark, "Point") or not hasattr(placemark.Point, "coordinates"):
                        continue

                    match = re.search(r"Type:\s*(\w+)", str(getattr(placemark, "description", "")))
                    if not match:
                        continue

                    node_type = match.group(1).lower()
                    if node_type == "pole":
                        continue

                    coords_str = str(placemark.Point.coordinates).strip()
                    lng, lat, _ = coords_str.split(",")
                    coords.append(Node(
                        index=len(coords),
                        name=str(placemark.name),
                        lat=float(lat),
                        lng=float(lng),
                        type=node_type
                    ))

        if not coords:
            pytest.skip(f"No valid node placemarks found in: {kml_file_path}")
        return coords
    except (FileNotFoundError, AttributeError, IndexError):
        pytest.skip(f"KML file not found or incorrectly formatted: {kml_file_path}")


@pytest.fixture
def renewvia_ground_truth_terminals_only_nodes():
    """Parses renewvia terminals-only KML with one source and many terminals."""
    try:
        kml_file_path = f"{TEST_DATASET_DIR}/renewvia_ground_truth_terminals_only.kml"
        with open(kml_file_path, "r", encoding="utf-8") as f:
            root = parser.parse(f).getroot()

        coords = []
        for folder in root.Document.Folder:
            for placemark in folder.Placemark:
                coords_str = str(placemark.Point.coordinates).strip()
                lng, lat, _ = coords_str.split(",")
                match = re.search(r"Type:\s*(\w+)", str(placemark.description))
                node_type = match.group(1).lower() if match else "terminal"
                coords.append(Node(
                    index=len(coords),
                    name=str(placemark.name),
                    lat=float(lat),
                    lng=float(lng),
                    type=node_type,
                ))

        if not coords:
            pytest.skip("renewvia_ground_truth_terminals_only.kml parsed but had no nodes")

        return coords
    except FileNotFoundError:
        pytest.skip("renewvia_ground_truth_terminals_only.kml not found")
    except (AttributeError, IndexError):
        pytest.skip("renewvia_ground_truth_terminals_only.kml incorrectly formatted")


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
                                  poleToTerminalMinLength=2),
        high=LengthConstraintsBase(poleToPoleMaxLength=50,
                                   poleToTerminalMaxLength=20,
                                   poleToTerminalMinLength=2)
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
def local_opt_kml_nodes_with_edges():
    """Load the existing layout, including poles and directed power lines."""
    kml_path = Path(__file__).resolve().parents[1] / TEST_DATASET_DIR / "local_opt_test.kml"
    with kml_path.open(encoding="utf-8") as f:
        root = parser.parse(f).getroot()

    namespaces = {"kml": "http://www.opengis.net/kml/2.2"}
    placemarks = root.xpath(".//kml:Placemark", namespaces=namespaces)
    nodes = []
    for placemark in placemarks:
        if not hasattr(placemark, "Point"):
            continue
        description = str(placemark.description)
        node_type = re.search(r"Type:\s*(source|terminal|pole)\b", description)
        if node_type is None:
            continue  # The summary placemark is not a network node.
        node_index = re.search(r"Index:\s*(\d+)", description)
        assert node_index is not None, f"Missing node index: {placemark.name}"
        lng, lat, *_ = str(placemark.Point.coordinates).strip().split(",")
        nodes.append(Node(
            index=int(node_index.group(1)),
            name=str(placemark.name),
            lat=float(lat),
            lng=float(lng),
            type=node_type.group(1),
        ))

    nodes.sort(key=lambda node: node.index)
    nodes_by_coordinates = {(node.lng, node.lat): node for node in nodes}
    edges = []
    for placemark in placemarks:
        if not hasattr(placemark, "LineString"):
            continue
        coordinates = str(placemark.LineString.coordinates).split()
        assert len(coordinates) == 2, f"Expected a two-endpoint line: {placemark.name}"
        endpoints = [
            tuple(map(float, coordinate.split(",")[:2]))
            for coordinate in coordinates
        ]
        start, end = [nodes_by_coordinates[coordinate] for coordinate in endpoints]
        voltage = re.search(r"Voltage:\s*(low|high)\b", str(placemark.description))
        assert voltage is not None, f"Missing line voltage: {placemark.name}"
        edges.append(Edge(
            start=start,
            end=end,
            lengthMeters=LocalOptimization.haversine_meters(
                start.lat, start.lng, end.lat, end.lng,
            ),
            voltage=voltage.group(1),
        ))

    assert nodes and edges, "The local optimization KML must contain nodes and lines"
    return nodes, edges


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


@pytest.mark.parametrize("solver_name", list(SOLVER_REGISTRY.keys()))
def test_all_solvers_with_kml(kml_nodes_random_test_set, solver_name, default_costs,
                              default_length_constraints):
    """
    Parametrized test: Runs every solver in the registry using minigrid KML data.
    Validates that each solver returns a result with nodes and edges.
    """
    solver_class = SOLVER_REGISTRY[solver_name]

    # Create request with default params
    req = SolverRequest(
        nodes=kml_nodes_random_test_set,
        costs=default_costs,
        lengthConstraints=default_length_constraints,
        debug=2,
    )

    result = solver_class(req).solve()
    print("Solver Name: ", solver_name)
    print("Number of Terminals:", _count_terminals(kml_nodes_random_test_set))
    print("Total Cost", result.totalCostEstimate)
    print("Number of Poles Used", result.numPolesUsed)
    print("Total Edge Length:", result.totalEdgeLengthMeters)

    # Assertions for output quality
    assert result is not None, f"{solver_name} returned no result"
    assert len(result.nodes) >= len(kml_nodes_random_test_set), f"{solver_name} lost nodes during solve"
    assert len(result.edges) > 0, f"{solver_name} failed to create any connections"
    assert result.totalCostEstimate > 0, f"{solver_name} calculated zero or negative cost"


@pytest.mark.parametrize("solver_name", list(SOLVER_REGISTRY.keys()))
def test_all_solvers_with_bc_ground_truth_kml(solver_name, kml_nodes, default_costs, default_length_constraints):
    """Run every registered solver against bc1/bc2 ground-truth KML datasets."""
    solver_class = SOLVER_REGISTRY[solver_name]
    req = SolverRequest(
        nodes=kml_nodes,
        costs=default_costs,
        lengthConstraints=default_length_constraints,
        debug=2,
    )

    result = solver_class(req).solve()
    print("Solver Name: ", solver_name)
    print("Number of Terminals:", _count_terminals(kml_nodes))
    print("Total Cost", result.totalCostEstimate)
    print("Number of Poles Used", result.numPolesUsed)
    print("Total Edge Length:", result.totalEdgeLengthMeters)

    assert result is not None, f"{solver_name} returned no result"
    assert len(result.nodes) >= len(kml_nodes), f"{solver_name} lost nodes during solve"
    assert len(result.edges) > 0, f"{solver_name} failed to create any connections"
    assert result.totalCostEstimate > 0


@pytest.mark.parametrize("solver_name", list(SOLVER_REGISTRY.keys()))
def test_all_solvers_with_renewvia_ground_truth_terminals_only_kml(
        solver_name,
        renewvia_ground_truth_terminals_only_nodes,
        default_costs,
        default_length_constraints,
):
    """Run all solvers on renewvia_ground_truth_terminals_only.kml."""
    solver_class = SOLVER_REGISTRY[solver_name]
    req = SolverRequest(
        nodes=renewvia_ground_truth_terminals_only_nodes,
        costs=default_costs,
        lengthConstraints=default_length_constraints,
        debug=0,
    )

    result = solver_class(req).solve()

    print("Solver Name: ", solver_name)
    print("Number of Terminals:", _count_terminals(renewvia_ground_truth_terminals_only_nodes))
    print("Total Cost", result.totalCostEstimate)
    print("Number of Poles Used", result.numPolesUsed)
    print("Total Edge Length:", result.totalEdgeLengthMeters)

    assert result is not None, f"{solver_name} returned no result"
    assert len(result.nodes) >= len(renewvia_ground_truth_terminals_only_nodes), (
        f"{solver_name} lost nodes during solve"
    )
    assert len(result.edges) > 0, f"{solver_name} failed to create any connections"
    assert result.totalCostEstimate > 0, f"{solver_name} calculated zero or negative cost"


def test_solver_param_metadata():
    """Checks that get_input_params returns valid data for the UI."""
    for name, solver_class in SOLVER_REGISTRY.items():
        params = solver_class.get_input_params()
        assert isinstance(params, list), f"{name} must return a list of parameters"


def test_local_optimization_kml_decreases_total_cost(
        local_opt_kml_nodes_with_edges, default_costs, default_length_constraints,
        monkeypatch,
):
    """Optimize only the existing KML layout and require a strict cost reduction."""
    nodes, edges = local_opt_kml_nodes_with_edges
    cost_before = round(
        sum(node.type == "pole" for node in nodes) * default_costs.poleCost
        + sum(
            edge.lengthMeters * (
                default_costs.lowVoltageCostPerMeter
                if edge.voltage == "low"
                else default_costs.highVoltageCostPerMeter
            )
            for edge in edges
        ),
        2,
    )
    request = SolverRequest(
        solver="LocalOptimization",
        nodes=nodes,
        edges=edges,
        voltageLevel="low",
        costs=default_costs,
        lengthConstraints=default_length_constraints,
        usePoles=True,
        debug=0,
    )

    plot = Mock(wraps=LocalOptimization._plot_current_graph)
    monkeypatch.setattr(LocalOptimization, "_plot_current_graph", plot)
    solver = LocalOptimization(request)
    result = solver.solve()

    final_plot = plot.call_args
    assert final_plot.kwargs["title"] == "Final accepted local optimization graph"
    plotted_result = solver.build_solver_result(final_plot.args[0])
    assert plotted_result == result
    assert any(
        call.kwargs.get("title", "").startswith("Candidate after iteration")
        for call in plot.call_args_list
    )
    geometric_cost = (
        result.numPolesUsed * default_costs.poleCost
        + sum(
            LocalOptimization.haversine_meters(
                edge.start.lat, edge.start.lng, edge.end.lat, edge.end.lng,
            ) * default_costs.lowVoltageCostPerMeter
            for edge in result.edges
        )
    )
    assert result.totalCostEstimate == pytest.approx(round(geometric_cost, 2), abs=0.01)

    graph = nx.DiGraph()
    graph.add_nodes_from(node.index for node in result.nodes)
    graph.add_edges_from((edge.start.index, edge.end.index) for edge in result.edges)
    source = next(node.index for node in result.nodes if node.type == "source")
    reachable = nx.descendants(graph, source)
    assert all(node.index in reachable for node in result.nodes if node.type == "terminal")
    assert _count_terminals(result.nodes) == _count_terminals(nodes)

    print(f"Total cost before: ${cost_before:,.2f}")
    print(f"Total cost after: ${result.totalCostEstimate:,.2f}")
    print(f"Cost reduction: ${cost_before - result.totalCostEstimate:,.2f}")
    assert 0 < result.totalCostEstimate < cost_before, (
        f"LocalOptimization did not decrease total cost: "
        f"${cost_before:,.2f} -> ${result.totalCostEstimate:,.2f}"
    )


@pytest.mark.parametrize("length, extra_poles", [
    (30.0, 0),
    (30.097955333016607, 0),
    (30.1, 0),
    (30.1001, 1),
    (60.2, 1),
    (60.2001, 2),
])
@pytest.mark.parametrize("voltage", ["low", "high"])
def test_edge_weight_respects_spacing_tolerance(
        ga_tech_nodes, default_costs, default_length_constraints,
        length, extra_poles, voltage,
):
    default_length_constraints.high.poleToPoleMaxLength = 30
    solver = LocalOptimization(SolverRequest(
        nodes=ga_tech_nodes,
        costs=default_costs,
        lengthConstraints=default_length_constraints,
        voltageLevel=voltage,
    ))
    expected = length * solver.get_cost_per_meter() + extra_poles * default_costs.poleCost
    assert solver.calc_edge_weight(length) == pytest.approx(expected)


def test_local_optimization_plots_restored_graph_after_rejected_candidate(
        local_opt_kml_nodes_with_edges, default_costs, default_length_constraints,
        monkeypatch,
):
    nodes, edges = local_opt_kml_nodes_with_edges
    solver = LocalOptimization(SolverRequest(
        nodes=nodes,
        edges=edges,
        costs=default_costs,
        lengthConstraints=default_length_constraints,
        debug=2,
    ))
    solver.parse_and_validate_input()
    graph = solver.build_graph_from_nodes(solver._nodes, solver._edges, directed=True)
    original = graph.copy()

    def worsen_candidate(candidate):
        candidate.nodes[10]["lat"] += 0.001
        candidate.edges[0, 10]["weight"] += 1000
        return candidate

    monkeypatch.setattr(solver, "_pole_gradient_optimizer", worsen_candidate)
    for method in (
        "_pole_block_coordinate_pass", "_merge_collinear_pole_chains",
        "split_long_edges_w_poles", "_drop_redundant_poles",
        "_enforce_min_pole_terminal_distances",
    ):
        monkeypatch.setattr(solver, method, lambda candidate: candidate)
    plot = Mock()
    monkeypatch.setattr(solver, "_plot_current_graph", plot)

    returned = solver._post_solver_opt(graph)

    assert nx.utils.graphs_equal(returned, original)
    assert not nx.utils.graphs_equal(plot.call_args_list[0].args[0], returned)
    assert plot.call_args.args[0] is returned
    assert plot.call_args.kwargs["title"] == "Final accepted local optimization graph"


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
    print("Number of Terminals:", _count_terminals(nodes))

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
