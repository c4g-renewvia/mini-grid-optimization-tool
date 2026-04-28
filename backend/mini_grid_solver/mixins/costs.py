import math
import numpy as np

MAX_EDGE_DIST_PENALTY = 10000


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
        if self.request.voltageLevel == 'low':
            return self.request.lengthConstraints.low.poleToTerminalMinLength
        else:
            return self.request.lengthConstraints.high.poleToTerminalMinLength

    def get_max_pole_to_pole(self) -> float:
        if self.request.voltageLevel == 'low':
            return self.request.lengthConstraints.low.poleToPoleMaxLength
        else:
            return self.request.lengthConstraints.high.poleToPoleMaxLength

    def get_max_pole_to_term(self) -> float:
        if self.request.voltageLevel == 'low':
            return self.request.lengthConstraints.low.poleToTerminalMaxLength
        else:
            return self.request.lengthConstraints.high.poleToTerminalMaxLength

    def get_cost_per_meter(self) -> float:
        if self.request.voltageLevel == "low":
            return self.request.costs.lowVoltageCostPerMeter
        else:
            return self.request.costs.highVoltageCostPerMeter
        """..."""

    def calc_edge_weight(self, length, to_terminal=False):
        """
        Calculates the weight (cost) of establishing an electrical connection over a specified length,
        including the cost of wires and supplementary poles required for intermediate support.

        Args:
            length: The length of the connection to be established, in meters.
            to_terminal: A boolean indicating whether the connection is reaching a terminal point.

        Returns:
            float: The calculated weight (cost) of establishing the electrical connection.
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

        extra_poles = max(0, math.ceil(length / pole_to_pole_constraint) - 1)
        weight += extra_poles * pole_cost

        return weight

    def _compute_total_cost(self, graph):
        """
        Calculates the total cost associated with a given graph based on wire costs, pole costs,
        and constraint violation penalties.

        The method calculates the total cost by summing up the wire costs, the costs of the
        intermediate support poles, and penalties associated with violation of distance constraints
        (length and type-based constraints) between nodes in the graph.

        Args:
            graph: A graph object where nodes and edges contain relevant attributes, such as 'type'
                for nodes and 'weight', 'length', and 'voltage' for edges. The graph is expected to
                use a data structure that complies with node and edge attribute lookups.

        Returns:
            float: The total cost associated with the given graph, including wire costs, pole costs,
            and any applicable violation penalties.
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
            if length > max_len + 0.1:
                excess = length - max_len
                violation_penalty += MAX_EDGE_DIST_PENALTY * excess

            # Too short on terminal edges → also massive penalty
            if is_terminal_edge and length < min_len:
                shortfall = (min_len - length) * 1000
                violation_penalty += MAX_EDGE_DIST_PENALTY * shortfall * 50

        return total + violation_penalty

    def _compute_total_cost_poles_only(self, graph):
        """
        Computes the total cost of constructing a network considering only wire
        costs and the cost of intermediate support poles.

        The calculation involves summing the weights of the edges in the given
        graph as wire costs and adding the cost of intermediate poles based on
        the specified type of nodes.

        Args:
            graph: A graph where edges contain a 'weight' attribute representing
                the cost of wire between two nodes, and nodes may have a 'type'
                attribute to indicate whether they are poles. The graph is
                expected to represent network connections.

        Returns:
            float: The total cost calculated as the sum of wire costs and pole
                costs.
        """
        # 1. Wire + intermediate support-pole costs
        wire_cost = sum(d['weight'] for u, v, d in graph.edges(data=True))

        # 2. Pole costs
        num_poles = sum(1 for idx, data in graph.nodes(data=True) if data['type'] == "pole")
        pole_cost = self._costs.poleCost

        total = wire_cost + (num_poles * pole_cost)

        return total

    def _fast_total_cost_for_coords(self, coords: np.ndarray) -> float:
        """
        Calculates the total cost for a given set of coordinates considering wire costs, pole
        costs, trunk and terminal drops, and ensures compliance with maximum allowable distances.

        The method determines the cost of setting up a network infrastructure given a set of
        geographic coordinates. It handles different components of the cost, including trunk
        and terminal wire costs, pole costs, penalties for exceeding maximum distances, and
        pruning of unnecessary poles using a minimum spanning tree.

        Args:
            coords (np.ndarray): A 2D array of coordinates, where each row represents a point
                in geographic space. The length of coords must be at least 2.

        Returns:
            float: The total calculated cost, including the wire cost and the cost of active
            poles after pruning.
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


