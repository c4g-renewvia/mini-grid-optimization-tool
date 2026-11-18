import pytest
from pydantic import ValidationError

from mini_grid_solver.utils.electrical_validation import validate_electrical_inputs
from mini_grid_solver.utils.models import (
    ElectricalInputRequest, ElectricalSettings, Node,
)


@pytest.fixture
def network():
    """Create a complete fixed-voltage network input.

    Returns:
        ElectricalInputRequest: Source, pole, terminal, and electrical settings.
    """
    source = Node(index=10, name="Source", type="source", lat=0, lng=0,
                  voltageLevel="low", maxPowerKw=10, maxOutputCurrentA=200)
    pole = Node(index=20, name="Pole", type="pole", lat=0, lng=0.001)
    terminal = Node(index=30, name="Terminal", type="terminal", lat=0, lng=0.002,
                    voltageLevel="low", peakLoadKw=2)
    return ElectricalInputRequest(
        nodes=[source, pole, terminal],
        settings=ElectricalSettings(
            conductorResistanceOhmPerKm=1.5, conductorCurrentRatingA=100,
            maxVoltageDropPercent=5,
        ),
    )


def test_ready_is_not_an_electrical_feasibility_check(network):
    """Verify that readiness does not imply sufficient source capacity.

    Args:
        network: Complete electrical-input fixture.
    """
    network.nodes[0] = network.nodes[0].model_copy(update={"maxPowerKw": 0})
    report = validate_electrical_inputs(network)
    assert report.status == "ready"
    assert report.errors == report.missingInputs == []


def test_missing_data_is_incomplete_and_zero_load_is_known(network):
    """Verify that zero load is known while omitted settings remain missing.

    Args:
        network: Complete electrical-input fixture.
    """
    network.settings = ElectricalSettings()
    network.nodes[2] = network.nodes[2].model_copy(update={"peakLoadKw": 0})
    report = validate_electrical_inputs(network)
    assert report.status == "incomplete"
    assert len(report.missingInputs) == 3


def test_unknown_node_voltage_and_load_are_not_defaulted(network):
    """Verify that unknown terminal voltage and load are reported as missing.

    Args:
        network: Complete electrical-input fixture.
    """
    network.nodes[2] = network.nodes[2].model_copy(update={"voltageLevel": None, "peakLoadKw": None})
    report = validate_electrical_inputs(network)
    assert report.status == "incomplete"
    assert "Terminal: voltage level" in report.missingInputs
    assert "Terminal: peak load (kW)" in report.missingInputs


@pytest.mark.parametrize("field,value", [
    ("conductorResistanceOhmPerKm", 0), ("conductorResistanceOhmPerKm", -1),
    ("conductorCurrentRatingA", 0), ("conductorCurrentRatingA", float("inf")),
    ("maxVoltageDropPercent", 0), ("maxVoltageDropPercent", 100),
    ("maxVoltageDropPercent", float("nan")),
])
def test_invalid_settings_rejected(field, value):
    """Verify that invalid electrical settings fail model validation.

    Args:
        field: Electrical-setting field name.
        value: Invalid value to validate.
    """
    with pytest.raises(ValidationError):
        ElectricalSettings(**{field: value})


@pytest.mark.parametrize("problem,expected", [
    ("indices", "indices must be unique"),
    ("two_sources", "Exactly one source"),
    ("no_source", "Exactly one source"),
    ("no_terminal", "At least one terminal"),
])
def test_invalid_networks(network, problem, expected):
    """Verify that malformed node collections produce explicit errors.

    Args:
        network: Complete electrical-input fixture.
        problem: Node-collection defect to introduce.
        expected: Expected error-message substring.
    """
    if problem == "indices":
        network.nodes.append(network.nodes[0])
    elif problem == "two_sources":
        network.nodes.append(network.nodes[0].model_copy(update={"index": 40}))
    elif problem == "no_source":
        network.nodes.pop(0)
    elif problem == "no_terminal":
        network.nodes.pop()
    report = validate_electrical_inputs(network)
    assert report.status == "invalid"
    assert any(expected in error for error in report.errors)


def test_unconnected_nodes_with_arbitrary_indices_are_ready(network):
    """Verify that readiness requires neither connections nor contiguous indices.

    Args:
        network: Complete electrical-input fixture.
    """
    assert validate_electrical_inputs(network).status == "ready"


def test_empty_network_returns_structured_errors():
    """Verify that an empty network returns errors and missing-setting details."""
    report = validate_electrical_inputs(ElectricalInputRequest(
        nodes=[], settings=ElectricalSettings(),
    ))
    assert report.status == "invalid"
    assert len(report.missingInputs) == 3


def test_terminal_voltage_mismatch(network):
    """Verify that terminal voltage must match the source voltage.

    Args:
        network: Complete electrical-input fixture.
    """
    network.nodes[2] = network.nodes[2].model_copy(update={"voltageLevel": "high"})
    report = validate_electrical_inputs(network)
    assert report.status == "invalid"
    assert any("Terminal: voltage must match" in error for error in report.errors)


def test_legacy_connection_data_is_not_inspected(network):
    """Verify that pre-solver validation ignores legacy connection data.

    Args:
        network: Complete electrical-input fixture.
    """
    request = ElectricalInputRequest.model_validate({
        **network.model_dump(),
        "edges": [{"start": {"index": -1}, "lengthMeters": -1, "voltage": "unknown"}],
    })
    report = validate_electrical_inputs(request)
    assert report.status == "ready"
    assert report.errors == report.missingInputs == []


def test_invalid_coordinates(network):
    """Verify that nonfinite coordinates produce an explicit error.

    Args:
        network: Complete electrical-input fixture.
    """
    network.nodes[1] = network.nodes[1].model_copy(update={"lat": float("nan")})
    report = validate_electrical_inputs(network)
    assert report.status == "invalid"
    assert any("coordinates" in error for error in report.errors)


def test_validation_endpoint_contract(network):
    """Verify endpoint registration and the electrical-readiness response.

    Args:
        network: Complete electrical-input fixture.
    """
    from server import app, check_electrical_inputs

    assert check_electrical_inputs(network).status == "ready"
    assert "/validate-electrical-inputs" in app.openapi()["paths"]


def test_uniform_high_voltage_network_is_supported(network):
    """Verify readiness for a uniformly high-voltage network.

    Args:
        network: Complete electrical-input fixture.
    """
    network.nodes = [
        node.model_copy(update={"voltageLevel": "high"})
        if node.type in ("source", "terminal") else node
        for node in network.nodes
    ]
    assert validate_electrical_inputs(network).status == "ready"


def test_missing_source_limits_are_reported(network):
    """Verify that omitted source power and current limits are listed.

    Args:
        network: Complete electrical-input fixture.
    """
    network.nodes[0] = network.nodes[0].model_copy(update={
        "maxPowerKw": None, "maxOutputCurrentA": None,
    })
    report = validate_electrical_inputs(network)
    assert report.status == "incomplete"
    assert report.missingInputs == [
        "Source: maximum power (kW)", "Source: output current limit (A)",
    ]
