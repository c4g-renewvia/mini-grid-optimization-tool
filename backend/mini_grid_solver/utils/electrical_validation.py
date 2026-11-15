import math

from .models import ElectricalInputRequest, ElectricalInputReport


def validate_electrical_inputs(request: ElectricalInputRequest) -> ElectricalInputReport:
    """Check pre-solver electrical inputs without inspecting connections.

    Args:
        request: Nodes and electrical settings to validate.

    Returns:
        ElectricalInputReport: Readiness status, missing inputs, and errors.
    """
    errors = []
    missing = []
    nodes = {node.index: node for node in request.nodes}
    if len(nodes) != len(request.nodes):
        errors.append("Node indices must be unique.")
    sources = [node for node in request.nodes if node.type == "source"]
    terminals = [node for node in request.nodes if node.type == "terminal"]
    if len(sources) != 1:
        errors.append("Exactly one source is required.")
    if not terminals:
        errors.append("At least one terminal is required.")
    if any(node.type not in ("source", "terminal", "pole") for node in request.nodes):
        errors.append("Only sources, terminals, and poles are supported in electrical analysis.")
    for node in request.nodes:
        if (
            not math.isfinite(node.lat) or not math.isfinite(node.lng)
            or not -90 <= node.lat <= 90 or not -180 <= node.lng <= 180
        ):
            errors.append(f"{node.name or node.index}: coordinates must be finite and in range.")

    for field, label in (
        ("conductorResistanceOhmPerKm", "Conductor resistance (ohms/km per conductor)"),
        ("conductorCurrentRatingA", "Conductor current rating (A)"),
        ("maxVoltageDropPercent", "Maximum voltage drop (%)"),
    ):
        if getattr(request.settings, field) is None:
            missing.append(label)

    source_voltage = sources[0].voltageLevel if len(sources) == 1 else None
    for node in sources + terminals:
        label = node.name or f"Node {node.index}"
        if node.voltageLevel is None:
            missing.append(f"{label}: voltage level")
        elif source_voltage is not None and node.voltageLevel != source_voltage:
            errors.append(f"{label}: voltage must match the source for fixed-voltage analysis.")
        fields = (
            (("maxPowerKw", "maximum power (kW)"), ("maxOutputCurrentA", "output current limit (A)"))
            if node.type == "source" else (("peakLoadKw", "peak load (kW)"),)
        )
        for field, description in fields:
            if getattr(node, field) is None:
                missing.append(f"{label}: {description}")

    return ElectricalInputReport(
        status="invalid" if errors else "incomplete" if missing else "ready",
        missingInputs=missing,
        errors=errors,
    )
