import math
import numpy as np

MAX_EDGE_DIST_PENALTY = 10000
EDGE_LENGTH_TOLERANCE_METERS = 0.1


class CostMixin:
    """
    Mixin class providing utility methods for calculating costs and constraints in
    electrical network design.

    The `CostMixin` class includes methods to calculate costs and enforce constraints
    related to poles, wires, and terminal connections in an electrical grid. These methods
    help compute costs for wire lengths, intermediate poles, and penalties for violating
    distance constraints. It is intended to be used as a part of a larger system for
    optimizing electrical distribution networks.

    Attributes:
        request (object): A context object containing voltage levels, length constraints, and
            cost details for calculation purposes.
    """

    def get_min_pole_to_term(self) -> float:
        """Return the minimum allowed pole-to-terminal distance in meters."""
        if self.request.voltageLevel == 'low':
            return self.request.lengthConstraints.low.poleToTerminalMinLength
        else:
            return self.request.lengthConstraints.high.poleToTerminalMinLength

    def get_max_pole_to_pole(self) -> float:
        """Return the maximum allowed pole-to-pole distance in meters."""
        if self.request.voltageLevel == 'low':
            return self.request.lengthConstraints.low.poleToPoleMaxLength
        else:
            return self.request.lengthConstraints.high.poleToPoleMaxLength

    def get_max_pole_to_term(self) -> float:
        """Return the maximum allowed pole-to-terminal distance in meters."""
        if self.request.voltageLevel == 'low':
            return self.request.lengthConstraints.low.poleToTerminalMaxLength
        else:
            return self.request.lengthConstraints.high.poleToTerminalMaxLength

    def get_cost_per_meter(self) -> float:
        """Return the wire cost per meter for the active voltage level."""
        if self.request.voltageLevel == "low":
            return self.request.costs.lowVoltageCostPerMeter
        else:
            return self.request.costs.highVoltageCostPerMeter
        """..."""

    def calc_edge_weight(self, length, to_terminal=False):
        """Calculate the cost of a connection, including intermediate support poles.

        Args:
            length: Connection length in meters.
            to_terminal: Whether the connection ends at a terminal.

        Returns:
            float: Total wire and intermediate-pole cost.
        """
        voltage_cost = self.get_cost_per_meter()

        pole_cost = self.request.costs.poleCost

        # Cost of the wire
        weight = length * voltage_cost

        # Cost of intermediate support poles for long spans
        pole_to_pole_constraint = self.get_max_pole_to_pole()

        if to_terminal:
            pole_to_terminal_constraint = self.get_max_pole_to_term()
            length -= pole_to_terminal_constraint

        extra_poles = max(
            0,
            math.ceil(length / (pole_to_pole_constraint + EDGE_LENGTH_TOLERANCE_METERS)) - 1,
        )
        weight += extra_poles * pole_cost

        return weight

    def _compute_total_cost(self, graph):
        """Calculate wire, pole, and distance-constraint costs for a graph.

        Args:
            graph: Graph whose nodes and edges contain network attributes.

        Returns:
            float: Total cost, including applicable constraint penalties.
        """
        # 1. Wire + intermediate support-pole costs
        wire_cost = sum(d['weight'] for u, v, d in graph.edges(data=True))

        # 2. Pole costs
        num_poles = sum(1 for idx, data in graph.nodes(data=True) if data['type'] == "pole")
        pole_cost = self._costs.poleCost

        total = wire_cost + (num_poles * pole_cost)

        # 3. Constraint violation penalty (NOW COVERS MIN + MAX)
        violation_penalty = 0.0
        for u, v, data in graph.edges(data=True):
            length = data.get("length", 0.0)
            voltage = data.get("voltage", "low")

            u_type = graph.nodes[u]['type']
            v_type = graph.nodes[v]['type']
            is_terminal_edge = (u_type == "terminal" or v_type == "terminal")

            if is_terminal_edge:
                max_len = self.get_max_pole_to_term()
                min_len = self.get_min_pole_to_term()
            else:
                max_len = self.get_max_pole_to_pole()
                min_len = 0.5  # pole-pole has no meaningful minimum

            # Too long → massive linear penalty (same as before)
            if length > max_len + EDGE_LENGTH_TOLERANCE_METERS:
                excess = length - max_len
                violation_penalty += MAX_EDGE_DIST_PENALTY * excess

            # Too short on terminal edges → also massive penalty
            if is_terminal_edge and length < min_len:
                shortfall = (min_len - length) * 1000
                violation_penalty += MAX_EDGE_DIST_PENALTY * shortfall * 50

        return total + violation_penalty

    def _compute_total_cost_poles_only(self, graph):
        """Calculate wire and pole costs for a graph without constraint penalties.

        Args:
            graph: Graph whose edges have weights and whose nodes have type attributes.

        Returns:
            float: Sum of edge weights and pole costs.
        """
        # 1. Wire + intermediate support-pole costs
        wire_cost = sum(d['weight'] for u, v, d in graph.edges(data=True))

        # 2. Pole costs
        num_poles = sum(1 for idx, data in graph.nodes(data=True) if data['type'] == "pole")
        pole_cost = self._costs.poleCost

        total = wire_cost + (num_poles * pole_cost)

        return total

    def _fast_total_cost_for_coords(self, coords: np.ndarray) -> float:
        """Estimate network cost for coordinates using an MST and pole pruning.

        Args:
            coords (np.ndarray): Geographic coordinates with one point per row.

        Returns:
            float: Estimated wire and active-pole cost, or a large sentinel when
                fewer than two coordinates are provided.
        """
        if len(coords) < 2:
            return 1e9

        n = len(coords)
        source_idx = self._source_idx
        terminals = self._terminal_indices
        poles = [i for i in range(n) if i != source_idx and i not in terminals]

        dist = self.haversine_vec(coords, coords)

        low_cost = self.get_cost_per_meter()
        pole_cost = self.request.costs.poleCost
        max_pole_pole = self.get_max_pole_to_pole()
        max_pole_term = self.get_max_pole_to_term()
        MAX_PENALTY = 10000.0

        wire_cost = dist * low_cost

        # Trunk cost
        extra_poles_trunk = np.maximum(0, np.ceil(dist / max_pole_pole) - 1)
        excess_trunk = np.maximum(0, dist - max_pole_pole)
        trunk_cost = wire_cost + (extra_poles_trunk * pole_cost) + (excess_trunk * MAX_PENALTY)

        # Terminal drop cost
        dist_adj = np.maximum(0, dist - max_pole_term)
        extra_poles_term = np.maximum(0, np.ceil(dist_adj / max_pole_pole) - 1)
        excess_term = np.maximum(0, dist - max_pole_term)
        term_cost = wire_cost + (extra_poles_term * pole_cost) + (excess_term * MAX_PENALTY)

        adj = np.zeros((n, n), dtype=float)

        if poles:
            adj[source_idx, poles] = trunk_cost[source_idx, poles]
            adj[poles, source_idx] = trunk_cost[poles, source_idx]

        if len(poles) > 1:
            p_grid = np.ix_(poles, poles)
            adj[p_grid] = trunk_cost[p_grid]

        valid_sources = [source_idx] + poles
        if valid_sources and terminals:
            st_grid = np.ix_(valid_sources, terminals)
            ts_grid = np.ix_(terminals, valid_sources)
            adj[st_grid] = term_cost[st_grid]
            adj[ts_grid] = term_cost[ts_grid]

        adj[dist < 0.1] = 0.0
        np.fill_diagonal(adj, 0.0)

        from scipy.sparse import csr_matrix
        from scipy.sparse.csgraph import minimum_spanning_tree

        csr_adj = csr_matrix(adj)
        mst = minimum_spanning_tree(csr_adj)

        # Fast pruning
        mst_dense = mst.toarray()
        undirected_mst = mst_dense + mst_dense.T
        degrees = np.count_nonzero(undirected_mst, axis=1)

        pruned_nodes = set()
        removed = True
        while removed:
            removed = False
            for p in poles:
                if p not in pruned_nodes and degrees[p] == 1:
                    pruned_nodes.add(p)
                    neighbors = np.nonzero(undirected_mst[p])[0]
                    if len(neighbors) > 0:
                        neighbor = neighbors[0]
                        undirected_mst[p, neighbor] = 0.0
                        undirected_mst[neighbor, p] = 0.0
                        degrees[p] = 0
                        degrees[neighbor] -= 1
                    removed = True

        total_wire_and_extra = np.sum(undirected_mst) / 2.0
        num_active_poles = len(poles) - len(pruned_nodes)
        return total_wire_and_extra + (num_active_poles * pole_cost)
