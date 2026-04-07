# Mini-Grid Solver Documentation

This library provides a comprehensive framework for designing and optimizing rural power distribution networks. It focuses on minimizing total project solver by balancing wire lengths and pole placements while adhering to strict geographical and physical constraints.

---

## Project File Structure

Below is the directory structure for the Mini-Grid Optimizer library based on the provided source files:

```text
backend/
 └──mini_grid_solver/
    ├── server.py                           # Main entry point for the API
    ├── src/
        └── solvers/
            ├── __init__.py
            ├── base_mini_grid_solver.py       # Abstract base class for all solvers
            ├── greedy_iter_steiner_solver.py  # Greedy Iterative refinement solver
            ├── mst_solver.py                  # Simple MST baseline solver
            ├── registry.py                    # Solver registration utility
            ├── steinerized_mst.py             # MST with edge fragmentation
        │
        └── utils/
            ├── __init__.py
            ├── models.py                   # Pydantic data models
    └──test/                                # Tests for solver implementations
        ├── solvers/                        
            └──test_solvers.py              # Test suite for all solvers
        └──test_data_sets/                  # Data for testing
```

---

## Core Architecture

### 1. Data Models (`models.py`)

Built on Pydantic, these models ensure type safety and structured communication:

- **`SolverRequest`**: Captures input points (latitude/longitude), cost parameters, and solver-specific parameters.
- **`Node`**: A unified representation of every point in the network, categorized as a `source`, `terminal`, or `pole`.
- **`OutputEdge`**: Represents a connection between two nodes, including metadata for length and voltage levels.
- **`SolverResult`**: The final output containing the network topology, total solver, and optional debug metrics.
- **`Solvers`**: A registry of available optimization strategies made availiable to the front end.

### 2. Base Solver (`base_mini_grid_solver.py`)

The `BaseMiniGridSolver` is an abstract base class that provides essential utilities for all optimization algorithms:

- **Geographical Calculations**: Implements the Haversine formula to calculate great-circle distances in meters.
- **Input Canonicalization**: Automatically identifies power sources via keyword detection (e.g., "substation", "generator") and standardizes point names.
- **Vectorized Math**: Uses NumPy-based `haversine_vec` to compute distance matrices efficiently.
- **`_solve` method**: The abstract method that must be implemented by all child classes and does the main computation.

### 3. Registry Pattern (`registry.py`)

Solvers are decoupled from the main execution logic through a central `SOLVER_REGISTRY`. This allows developers to add new algorithms by simply applying the `@register_solver` decorator.

---

## Available Solvers

| Solver                        | Strategy                      | Key Features                                                                                                                |
| :---------------------------- | :---------------------------- | :-------------------------------------------------------------------------------------------------------------------------- |
| **`SimpleMSTSolver`**         | Baseline MST                  | Computes a standard Minimum Spanning Tree using only original points; useful as a lower-bound reference.                    |
| **`SteinerizedMSTSolver`**    | MST + Fragmentation           | Builds an MST and inserts intermediate poles along any edge exceeding a maximum span (e.g., 30m).                           |
| **`GreedyIterSteinerSolver`** | Greedy Iteration              | Iteratively adds candidate poles from Voronoi, Fermat, collinear, and projection sets to find the most cost-effective tree. |

---

---

# Future Development

## Voltage Support & Expansion

### Current Low Voltage (LV) Implementation

The library currently prioritizes low-voltage distribution for local micro-grids:

- **Default Classification**: All solvers currently default to assigning a `"low"` voltage type to every edge.
- **Costing**: Financial estimates primarily utilize the `lowVoltageCostPerMeter` parameter provided in the `SolverRequest`.
- **Physical Constraints**: Edge fragmentation and candidate generation are tuned to typical LV span limits, such as a 30-meter maximum length.
- **Metric Reporting**: The `totalHighVoltageMeters` field is initialized but generally returns `0.0` in the current iteration of the solvers.

### Expanding to High Voltage (HV) Support

The architecture is designed to be "HV-ready" and can be expanded using the following strategies:

- **Dual-Voltage Models**: The `OutputEdge` and `SolverResult` models already support a `"high"` voltage literal and separate cost tracking fields.
- **Trunk vs. Branch Logic**:
  - You can modify the `_build_edges_and_lengths` method to identify "trunk" lines.
  - Assign `"high"` voltage to edges directly connected to the source or to nodes serving more than a certain number of downstream terminals.
- **Distance-Based Upgrading**:
  - Update `build_directed_graph_for_arborescence` to evaluate both LV and HV weights for the same edge.
  - Higher voltage solver can be applied to long-distance spans where voltage drop across LV lines would be prohibitive.
- **Transformer Node Insertion**:
  - New node types can be added to the `Node` model to represent transformers where the network transitions from high to low voltage.
  -

### Expand Scope of Approximate Solvers:

Potential future improvements include:

- Genetic algorithms for global optimization.
- Local search techniques
- Zelikovsky-style relative greedy
- Concatenation heuristics (Zachariasen & Winter, 1999)
- Arora's PTAS
- Mitchell's guillotine subdivisions
- Ant Colony Optimization / Particle Swarms
- Neural-guided Steiner tree

---

## Getting started

- Create a new class that inherits from `BaseMiniGridSolver`
- Implement the abstract methods
- Register your solver using the `@register_solver` decorator
