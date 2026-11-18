import networkx as nx
import numpy as np
import pytest

from mini_grid_solver.solvers.disk_based_steiner_solver import DiskBasedSteinerSolver
from mini_grid_solver.solvers.local_opt import LocalOptimization
from mini_grid_solver.solvers.mst_solver import SimpleMSTSolver
from mini_grid_solver.solvers.theoretical_solver import TheoreticalBoundSteinerSolver
from mini_grid_solver.utils.models import (
    Costs,
    LengthConstraints,
    LengthConstraintsBase,
    Node,
    SolverRequest,
    SolverResult,
)


@pytest.fixture(params=["low", "high"])
def request_with_metadata(request):
    """Create a solver request containing mixed node electrical metadata.

    Args:
        request: Pytest request supplying the network voltage level.

    Returns:
        SolverRequest: Source and terminals with electrical metadata.
    """
    return SolverRequest(
        voltageLevel=request.param,
        nodes=[
            Node(index=4, name="High", type="terminal", lat=0.0001, lng=0.0001,
                 voltageLevel="high", peakLoadKw=2.5),
            Node(index=8, name="Source", type="source", lat=-0.0003, lng=0.0,
                 voltageLevel="high", maxPowerKw=10.5, maxOutputCurrentA=25.0),
            Node(index=2, name="Low", type="terminal", lat=0.0001, lng=-0.0001,
                 voltageLevel="low", peakLoadKw=0.0),
            Node(index=9, name="Legacy", type="terminal", lat=-0.0001, lng=0.0),
        ],
        costs=Costs(),
        lengthConstraints=LengthConstraints(
            low=LengthConstraintsBase(poleToTerminalMinLength=2),
            high=LengthConstraintsBase(poleToTerminalMinLength=2),
        ),
    )


def assert_metadata(result, input_nodes):
    """Assert that node and edge metadata survive result serialization.

    Args:
        result: Solver result to inspect.
        input_nodes: Nodes whose metadata must be preserved.
    """
    expected = {node.name: node.voltageLevel for node in input_nodes}
    actual = {node.name: node for node in result.nodes}
    for name, voltage in expected.items():
        assert actual[name].voltageLevel == voltage
    for node in input_nodes:
        assert actual[node.name].peakLoadKw == node.peakLoadKw
        assert actual[node.name].maxPowerKw == node.maxPowerKw
        assert actual[node.name].maxOutputCurrentA == node.maxOutputCurrentA
    for edge in result.edges:
        assert edge.start == actual[edge.start.name]
        assert edge.end == actual[edge.end.name]
    assert SolverResult.model_validate_json(result.model_dump_json()) == result


def test_normalization_and_reindexing_preserve_metadata(request_with_metadata):
    """Verify metadata preservation through normalization and reindexing.

    Args:
        request_with_metadata: Solver-request fixture with node metadata.
    """
    solver = SimpleMSTSolver(request_with_metadata)
    solver.parse_and_validate_input()

    assert [node.index for node in solver._nodes] == list(range(4))
    assert solver._nodes[0].type == "source"
    assert {node.name: node.voltageLevel for node in solver._nodes} == {
        node.name: node.voltageLevel for node in request_with_metadata.nodes
    }
    reindexed = solver.reindex_nodes(list(reversed(solver._nodes)))
    assert [node.index for node in reindexed] == list(range(4))
    assert {node.name: node.voltageLevel for node in reindexed} == {
        node.name: node.voltageLevel for node in request_with_metadata.nodes
    }
    assert request_with_metadata.nodes[0].index == 4


@pytest.mark.parametrize("directed", [False, True])
def test_graph_rebuilds_preserve_metadata(request_with_metadata, directed):
    """Verify metadata preservation when rebuilding network graphs.

    Args:
        request_with_metadata: Solver-request fixture with node metadata.
        directed: Whether to build a directed graph.
    """
    solver = SimpleMSTSolver(request_with_metadata)
    solver.parse_and_validate_input()
    nodes = solver._build_nodes(
        solver._coords, np.array([[0.0, 0.0002]]), solver._names
    )

    assert nodes[-1].voltageLevel is None
    assert nodes[-1].peakLoadKw is None
    graph = solver.build_graph_from_nodes(nodes, directed=directed)
    result = solver.build_solver_result(graph)
    assert_metadata(result, request_with_metadata.nodes)
    assert all(edge.voltage == request_with_metadata.voltageLevel for edge in result.edges)

    directed_graph = solver.build_directed_graph_for_arborescence(nodes)
    assert_metadata(solver.build_solver_result(directed_graph), request_with_metadata.nodes)


def test_disk_candidate_graph_preserves_metadata(request_with_metadata):
    """Verify that adding a disk candidate preserves terminal metadata.

    Args:
        request_with_metadata: Solver-request fixture with node metadata.
    """
    solver = DiskBasedSteinerSolver(request_with_metadata)
    solver.parse_and_validate_input()
    candidate = np.array([0.0, 0.0002])
    nodes = solver._build_nodes(solver._coords, [candidate], solver._names)
    graph = solver._build_directed_graph_with_new_point(
        nodes,
        solver.compute_distance_matrix(solver._coords),
        solver._distances_from_new_point(solver._coords, candidate),
        len(nodes) - 1,
    )

    assert_metadata(solver.build_solver_result(graph), request_with_metadata.nodes)


def test_disk_terminal_attachment_preserves_metadata(request_with_metadata):
    """Verify metadata preservation when attaching terminals to disk poles.

    Args:
        request_with_metadata: Solver-request fixture with node metadata.
    """
    solver = DiskBasedSteinerSolver(request_with_metadata)
    solver.parse_and_validate_input()
    graph = solver.attach_terminals(
        np.array([solver._coords[0], [0.0, 0.0]]),
        ["Source", "DiskCenterPole 1"],
    )

    assert_metadata(solver.build_solver_result(graph), request_with_metadata.nodes)


def test_undirected_post_processing_rebuild_preserves_metadata(request_with_metadata):
    """Verify metadata preservation during undirected graph post-processing.

    Args:
        request_with_metadata: Solver-request fixture with node metadata.
    """
    solver = SimpleMSTSolver(request_with_metadata)
    solver.parse_and_validate_input()
    graph = nx.minimum_spanning_tree(
        solver.build_graph_from_nodes(solver._nodes, include_terminals=True),
        weight="weight",
    )

    rebuilt = solver._merge_collinear_pole_chains(graph)

    assert_metadata(solver.build_solver_result(rebuilt), request_with_metadata.nodes)


@pytest.mark.parametrize("solver_class", [
    SimpleMSTSolver, DiskBasedSteinerSolver, TheoreticalBoundSteinerSolver,
])
def test_solving_preserves_metadata_without_changing_solution(
    request_with_metadata, solver_class
):
    """Verify that metadata survives solving without changing the layout.

    Args:
        request_with_metadata: Solver-request fixture with node metadata.
        solver_class: Solver implementation to exercise.
    """
    result = solver_class(request_with_metadata).solve()
    assert_metadata(result, request_with_metadata.nodes)

    legacy_request = request_with_metadata.model_copy(update={
        "nodes": [
            node.model_copy(update={
                "voltageLevel": None, "peakLoadKw": None,
                "maxPowerKw": None, "maxOutputCurrentA": None,
            })
            for node in request_with_metadata.nodes
        ],
    })
    legacy_result = solver_class(legacy_request).solve()
    result_without_metadata = result.model_dump()
    for node in result_without_metadata["nodes"]:
        node["voltageLevel"] = None
        node["peakLoadKw"] = None
        node["maxPowerKw"] = None
        node["maxOutputCurrentA"] = None
    for edge in result_without_metadata["edges"]:
        edge["start"]["voltageLevel"] = None
        edge["end"]["voltageLevel"] = None
        edge["start"]["peakLoadKw"] = None
        edge["end"]["peakLoadKw"] = None
        for endpoint in ("start", "end"):
            edge[endpoint]["maxPowerKw"] = None
            edge[endpoint]["maxOutputCurrentA"] = None
    assert result_without_metadata == legacy_result.model_dump()


def test_local_optimization_preserves_metadata(request_with_metadata):
    """Verify that local optimization preserves node electrical metadata.

    Args:
        request_with_metadata: Solver-request fixture with node metadata.
    """
    result = DiskBasedSteinerSolver(request_with_metadata).solve()
    request = request_with_metadata.model_copy(update={
        "nodes": result.nodes,
        "edges": result.edges,
    })

    optimized = LocalOptimization(request).solve()

    assert_metadata(optimized, request_with_metadata.nodes)
    assert all(edge.voltage == request.voltageLevel for edge in optimized.edges)


def test_result_remapping_preserves_metadata_on_both_edge_endpoints(request_with_metadata):
    """Verify metadata preservation on both remapped edge endpoints.

    Args:
        request_with_metadata: Solver-request fixture with node metadata.
    """
    solver = SimpleMSTSolver(request_with_metadata)
    solver.parse_and_validate_input()
    graph = nx.DiGraph()
    source = request_with_metadata.nodes[1]
    terminal = request_with_metadata.nodes[0]
    graph.add_node(10, **source.model_dump(exclude={"index"}))
    graph.add_node(20, **terminal.model_dump(exclude={"index"}))
    graph.add_edge(10, 20, length=45.0, voltage="low")

    result = solver.build_solver_result(graph)

    assert_metadata(result, [source, terminal])
    assert result.edges[0].start.index == 0
    assert result.edges[0].end.index == 1
    assert result.edges[0].start.voltageLevel == "high"
    assert result.edges[0].end.voltageLevel == "high"
    assert result.edges[0].voltage == "low"


def test_legacy_graph_without_voltage_metadata_serializes(request_with_metadata):
    """Verify serialization of graphs without voltage metadata.

    Args:
        request_with_metadata: Solver-request fixture used to initialize costs.
    """
    solver = SimpleMSTSolver(request_with_metadata)
    solver.parse_and_validate_input()
    graph = nx.DiGraph()
    graph.add_node(0, name="Source", type="source", lat=0.0, lng=0.0)
    graph.add_node(1, name="Terminal", type="terminal", lat=0.0, lng=0.001)
    graph.add_edge(0, 1, length=111.0, voltage="low")

    result = solver.build_solver_result(graph)

    assert all(node.voltageLevel is None for node in result.nodes)
    assert result.edges[0].start.voltageLevel is None
    assert result.edges[0].end.voltageLevel is None
