import networkx as nx
import numpy as np
import pytest

from mini_grid_solver.solvers.theoretical_solver import TheoreticalBoundSteinerSolver
from mini_grid_solver.utils.models import (
    Costs,
    LengthConstraints,
    LengthConstraintsBase,
    Node,
    SolverRequest,
)


def make_solver(beta=1000.0):
    """Create a theoretical solver with a configurable star-length bound.

    Args:
        beta: Maximum minimum-star length in meters.

    Returns:
        TheoreticalBoundSteinerSolver: A solver with source and terminal inputs.
    """
    return TheoreticalBoundSteinerSolver(SolverRequest(
        nodes=[
            Node(index=0, name="Source", type="source", lat=0.0, lng=0.0),
            Node(index=1, name="Terminal", type="terminal", lat=0.001, lng=0.0),
        ],
        params={"poleCost": beta},
        costs=Costs(),
        lengthConstraints=LengthConstraints(
            low=LengthConstraintsBase(poleToTerminalMinLength=0),
            high=LengthConstraintsBase(poleToTerminalMinLength=0),
        ),
    ))


def cluster_positions(monkeypatch, positions, beta, radius):
    """Cluster one-dimensional positions using exact absolute distances.

    Args:
        monkeypatch: Pytest fixture for replacing the geographic distance helper.
        positions: Terminal positions along a line.
        beta: Maximum minimum-star length.
        radius: Maximum distance from the selected terminal.

    Returns:
        list: Pole coordinates and terminal indices for each cluster.
    """
    solver = make_solver(beta)
    coords = np.column_stack((positions, np.zeros(len(positions))))
    monkeypatch.setattr(
        solver, "haversine_vec",
        lambda a, b: np.abs(a[:, 0, None] - b[None, :, 0]),
    )
    return solver._generate_greedy_clusters(coords, list(range(len(coords))), radius)


def test_clusters_take_nearest_terminals_not_input_order(monkeypatch):
    """Verify that clusters grow by distance rather than input ordering.

    Args:
        monkeypatch: Pytest fixture for replacing geographic distances.
    """
    clusters = cluster_positions(monkeypatch, [0, 30, 10, 20], beta=100, radius=25)

    assert [members for _, members in clusters] == [[0, 2, 3], [1]]
    np.testing.assert_array_equal(clusters[0][0], [0, 0])


def test_beta_uses_smallest_star_not_anchor_star(monkeypatch):
    """Verify that a non-anchor star center can keep a cluster within beta.

    Args:
        monkeypatch: Pytest fixture for replacing geographic distances.
    """
    clusters = cluster_positions(monkeypatch, [0, 10, 20], beta=20, radius=30)

    # The star at 10 has length 20, while the star at the anchor has length 30.
    assert [members for _, members in clusters] == [[0, 1, 2]]
    np.testing.assert_array_equal(clusters[0][0], [0, 0])


def test_beta_stops_at_first_exceedance_and_retains_rejected_terminal(monkeypatch):
    """Verify that the first over-budget terminal starts a later cluster.

    Args:
        monkeypatch: Pytest fixture for replacing geographic distances.
    """
    clusters = cluster_positions(monkeypatch, [0, 10, 20, 30], beta=19, radius=100)

    assert [members for _, members in clusters] == [[0, 1], [2, 3]]


@pytest.mark.parametrize("radius, expected", [
    (10, [[0, 1], [2]]),
    (9, [[0], [1], [2]]),
])
def test_radius_is_measured_from_anchor_and_includes_boundary(monkeypatch, radius, expected):
    """Verify that the anchor-radius bound includes its exact boundary.

    Args:
        monkeypatch: Pytest fixture for replacing geographic distances.
        radius: Maximum permitted distance from the anchor.
        expected: Expected terminal-index clusters.
    """
    clusters = cluster_positions(monkeypatch, [0, 10, 20], beta=100, radius=radius)

    assert [members for _, members in clusters] == expected


def test_empty_and_coincident_terminals(monkeypatch):
    """Verify clustering of empty inputs and coincident terminals.

    Args:
        monkeypatch: Pytest fixture for replacing geographic distances.
    """
    assert make_solver()._generate_greedy_clusters(np.empty((0, 2)), [], 10) == []
    clusters = cluster_positions(monkeypatch, [0, 0, 0], beta=0, radius=0)
    assert [members for _, members in clusters] == [[0, 1, 2]]


def test_solution_preserves_anchor_edges_and_splits_backbone():
    """Verify anchor placement, zero-length edges, connectivity, and span limits."""
    solver = TheoreticalBoundSteinerSolver(SolverRequest(
        nodes=[
            Node(index=0, name="Source", type="source", lat=-0.002, lng=0.0),
            Node(index=1, name="Anchor", type="terminal", lat=0.0, lng=0.0),
            Node(index=2, name="Near", type="terminal", lat=0.0001, lng=0.0),
            Node(index=3, name="Far", type="terminal", lat=0.001, lng=0.0),
        ],
        costs=Costs(),
        lengthConstraints=LengthConstraints(
            low=LengthConstraintsBase(
                poleToTerminalMinLength=0,
                poleToTerminalMaxLength=30,
                poleToPoleMaxLength=40,
            ),
            high=LengthConstraintsBase(),
        ),
    ))
    solver.parse_and_validate_input()
    graph = solver._solve()

    assert nx.is_arborescence(graph)
    for terminal in solver._terminal_indices:
        assert nx.has_path(graph, solver._source_idx, terminal)
        assert graph.out_degree(terminal) == 0
    anchor = next(n for n, data in graph.nodes(data=True) if data["name"] == "Anchor")
    pole = next(graph.predecessors(anchor))
    assert graph.nodes[pole]["lat"] == graph.nodes[anchor]["lat"]
    assert graph.nodes[pole]["lng"] == graph.nodes[anchor]["lng"]
    assert graph[pole][anchor]["length"] == 0
    for _, target, edge in graph.edges(data=True):
        limit = 30 if graph.nodes[target]["type"] == "terminal" else 40
        assert edge["length"] <= limit + 0.1

    result = solver.build_solver_result(graph)
    assert len(result.edges) == len(result.nodes) - 1
    assert any(edge.lengthMeters == 0 for edge in result.edges)
