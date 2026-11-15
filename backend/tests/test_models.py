import pytest
from pydantic import ValidationError

from mini_grid_solver.utils.models import Edge, Node


def test_legacy_node_has_unspecified_voltage():
    """Verify that legacy nodes retain unspecified voltage during serialization."""
    node = Node(index=0, lat=0.0, lng=0.0, type="terminal")

    assert node.voltageLevel is None
    assert Node.model_validate_json(node.model_dump_json()) == node


@pytest.mark.parametrize("voltage", ["low", "high"])
def test_node_voltage_round_trip(voltage):
    """Verify that voltage survives serialization and index changes.

    Args:
        voltage: Supported node voltage level to round-trip.
    """
    node = Node(
        index=1, lat=0.0, lng=0.001, type="terminal", voltageLevel=voltage
    )

    assert node.voltageLevel == voltage
    assert Node.model_validate_json(node.model_dump_json()) == node
    assert node.model_copy(update={"index": 2}).voltageLevel == voltage


@pytest.mark.parametrize("voltage", ["medium", "", 48, 380])
def test_node_rejects_invalid_voltage(voltage):
    """Verify that unsupported node voltage values are rejected.

    Args:
        voltage: Invalid voltage value to validate.
    """
    with pytest.raises(ValidationError, match="voltageLevel"):
        Node(index=1, lat=0.0, lng=0.001, type="terminal", voltageLevel=voltage)


def test_edge_preserves_terminal_voltage_separately_from_wire_voltage():
    """Verify that terminal voltage remains independent of wire voltage."""
    edge = Edge(
        start=Node(index=0, lat=0.0, lng=0.0, type="source"),
        end=Node(
            index=1, lat=0.0, lng=0.001, type="terminal", voltageLevel="high"
        ),
        lengthMeters=111.0,
        voltage="low",
    )

    restored = Edge.model_validate_json(edge.model_dump_json())

    assert restored.start.voltageLevel is None
    assert restored.end.voltageLevel == "high"
    assert restored.voltage == "low"


def test_node_with_voltage_remains_frozen():
    """Verify that voltage metadata does not allow mutation of frozen nodes."""
    node = Node(
        index=1, lat=0.0, lng=0.001, type="terminal", voltageLevel="low"
    )

    with pytest.raises(ValidationError, match="frozen_instance"):
        node.voltageLevel = "high"


@pytest.mark.parametrize("peak_load", [None, 0, 0.125, 2.5, 1000])
def test_peak_load_round_trip(peak_load):
    """Verify that peak-load values survive serialization.

    Args:
        peak_load: Optional nonnegative load in kilowatts.
    """
    node = Node(
        index=1, lat=0.0, lng=0.001, type="terminal", peakLoadKw=peak_load
    )

    assert node.peakLoadKw == peak_load
    assert Node.model_validate_json(node.model_dump_json()) == node


@pytest.mark.parametrize("peak_load", [-1, float("nan"), float("inf"), -float("inf"), "invalid"])
def test_invalid_peak_load_is_rejected(peak_load):
    """Verify that invalid peak-load values fail validation.

    Args:
        peak_load: Negative, nonfinite, or nonnumeric load value.
    """
    with pytest.raises(ValidationError, match="peakLoadKw"):
        Node(index=1, lat=0.0, lng=0.001, type="terminal", peakLoadKw=peak_load)


def test_legacy_node_has_unspecified_peak_load():
    """Verify that a legacy terminal has no implicit peak load."""
    assert Node(index=0, lat=0.0, lng=0.0, type="terminal").peakLoadKw is None


@pytest.mark.parametrize("field", ["maxPowerKw", "maxOutputCurrentA"])
@pytest.mark.parametrize("value", [None, 0, 0.125, 10.5, 1000])
def test_source_limit_round_trip(field, value):
    """Verify that source limits survive serialization.

    Args:
        field: Source-limit field name.
        value: Optional nonnegative limit to round-trip.
    """
    node = Node(index=0, lat=0.0, lng=0.0, type="source", **{field: value})

    assert getattr(node, field) == value
    assert Node.model_validate_json(node.model_dump_json()) == node


@pytest.mark.parametrize("field", ["maxPowerKw", "maxOutputCurrentA"])
@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), -float("inf"), "invalid"])
def test_invalid_source_limit_is_rejected(field, value):
    """Verify that invalid source limits fail validation.

    Args:
        field: Source-limit field name.
        value: Negative, nonfinite, or nonnumeric limit.
    """
    with pytest.raises(ValidationError, match=field):
        Node(index=0, lat=0.0, lng=0.0, type="source", **{field: value})


def test_legacy_source_limits_are_unspecified():
    """Verify that legacy sources have no implicit power or current limits."""
    node = Node(index=0, lat=0.0, lng=0.0, type="source")
    assert node.maxPowerKw is None
    assert node.maxOutputCurrentA is None
