import math
from typing import Union, List, Tuple

import networkx as nx
import numpy as np
from scipy.optimize import minimize

from ..utils.models import Node, Edge, get_node_coord_tuple


class PostProcessingMixin:
    """
    Provides methods for post-processing operations on nodes and edges in a network graph.

    This mixin includes methods for normalizing the order of nodes, renaming poles, pruning
    dead-end branches, recomputing edge attributes, and validating edges within a graph. The
    provided methods are useful for managing and refining the structure of graph-based network
    models, ensuring that nodes and edges comply with specific requirements. The class assumes
    NetworkX-compatible graphs and utilizes various graph-theoretic techniques such as depth-first
    search and descendant analysis.

    Attributes:
        None
    """

    @staticmethod
    def _get_num_poles_and_wire_length(graph: Union[nx.Graph, nx.DiGraph]):
        """
        Calculates the number of poles in the graph and the total wire length for
        different voltage types.

        This function iterates over the edges and nodes of the graph to compute
        the total wire length categorized by voltage type ("low" and "high") and
        count the total number of poles. It assumes that the edges in the graph
        have an attribute `length` for wire length and `voltage` for the type of
        voltage. Nodes in the graph are expected to have a `type` attribute to
        identify poles.

        Args:
            graph (Union[nx.Graph, nx.DiGraph]): A NetworkX graph representing the
                network of wires and poles. The graph's edges should contain the
                attributes `length` (float) and `voltage` (str), and its nodes
                should have a `type` attribute.

        Returns:
            Tuple[int, float, float]: A tuple containing:
                - The number of poles (int) in the graph.
                - The total wire length (float) for "low" voltage.
                - The total wire length (float) for "high" voltage.
        """
        low_m = high_m = 0.0

        for u, v, d in graph.edges(data=True):
            length = d.get("length", 0.0)
            voltage = d.get("voltage", "unknown")

            if voltage == "low":
                low_m += length
            elif voltage == "high":
                high_m += length

        n_poles = sum(1 for idx, data in graph.nodes(data=True) if data['type'] == "pole")

        return n_poles, low_m, high_m

    def _get_ordered_nodes_and_remap_edges(self, graph: Union[nx.DiGraph, nx.Graph]):
        """Return nodes in canonical order: Source → Terminals → Poles (sorted by distance from source)
        with dense contiguous indices 0,1,2,... and remap all edges accordingly."""
        source_nodes = []
        terminal_nodes = []
        pole_nodes = []

        for idx, data in graph.nodes(data=True):
            node = Node(
                index=idx,
                lat=data['lat'],
                lng=data['lng'],
                name=data.get('name') or f"{data['type']} {idx}",
                type=data['type'],
            )
            if data['type'] == "source":
                source_nodes.append(node)
            elif data['type'] == "terminal":
                terminal_nodes.append(node)
            elif data['type'] == "pole":
                pole_nodes.append(node)

        # Keep original relative order for terminals
        terminal_nodes.sort(key=lambda n: n.index)

        # Sort poles by their CURRENT name (which was set by rename_poles to "Pole 001", "Pole 002", ...)
        # This guarantees distance-based ordering
        pole_nodes.sort(key=lambda n: n.name)

        ordered_nodes = source_nodes + terminal_nodes + pole_nodes

        # Build old → new index mapping
        old_to_new = {node.index: new_idx for new_idx, node in enumerate(ordered_nodes)}

        # Create final nodes with dense indices
        final_nodes = []
        for new_idx, node in enumerate(ordered_nodes):
            final_nodes.append(Node(
                index=new_idx,
                lat=node.lat,
                lng=node.lng,
                name=node.name,
                type=node.type,
            ))

        # Remap edges
        final_edges = []
        for start_idx, end_idx, edge_data in graph.edges(data=True):
            new_start = old_to_new[start_idx]
            new_end = old_to_new[end_idx]

            start_data = graph.nodes[start_idx]
            end_data = graph.nodes[end_idx]

            final_edges.append(Edge(
                start=Node(
                    index=new_start,
                    lat=start_data['lat'],
                    lng=start_data['lng'],
                    name=start_data.get('name'),
                    type=start_data['type']
                ),
                end=Node(
                    index=new_end,
                    lat=end_data['lat'],
                    lng=end_data['lng'],
                    name=end_data.get('name'),
                    type=end_data['type']
                ),
                lengthMeters=round(edge_data.get('length', 0.0), 4),
                voltage=edge_data.get("voltage", "low"),
            ))

        return final_nodes, final_edges

    def _get_pole_optimization_order(self, graph: Union[nx.DiGraph, nx.Graph],
                                     farthest_first: bool = True) -> List[int]:
        """
        Determines the optimization order of poles in the provided graph based on their
        distance from a source node. By default, the poles are sorted in farthest-first
        order.

        This function computes the shortest-path distances between a source node and poles
        and sorts the poles accordingly. If the 'length' attribute exists on the graph's
        edges, it is used as the weight for distance computation. Otherwise, path lengths
        are calculated without weights.

        Args:
            graph: Graph containing nodes and edges, represented as either a directed or
                undirected graph (networkx.DiGraph or networkx.Graph).
            farthest_first: Boolean flag to determine sorting order. If True, poles are
                sorted in descending order by distance (farthest-first). If False, poles
                are sorted in ascending order by distance (closest-first).

        Returns:
            List[int]: A list of node indices representing the optimization order of poles.
        """
        source_idx = self._source_idx
        poles = [
            idx for idx, data in graph.nodes(data=True)
            if data.get('type') == 'pole'
        ]
        if not poles:
            return []

        # Compute shortest-path distance (using edge 'length' if present)
        try:
            dist_dict = nx.single_source_dijkstra_path_length(
                graph, source_idx, weight='length'
            )
        except (nx.NetworkXError, KeyError):
            # fallback for graphs without 'length' or disconnected nodes
            dist_dict = nx.single_source_shortest_path_length(graph, source_idx)

        # Sort poles
        sorted_poles = sorted(
            poles,
            key=lambda p: dist_dict.get(p, 999999.0),
            reverse=farthest_first
        )

        if self.request.debug >= 2:
            print(f"  Pole optimization order: {'farthest-first' if farthest_first else 'closest-first'} "
                  f"({len(sorted_poles)} poles)")

        return sorted_poles

    def _normalize_node_order(self):
        """
        Rearranges the list of nodes in a specified order and regenerates metadata.

        This method organizes nodes into groups based on their types ('source',
        'terminal', 'pole') while preserving the original order within each group.
        It then rebuilds the node list in the desired order and regenerates associated
        metadata such as indices, coordinates, and names.

        Args:
            None

        Raises:
            None
        """
        if not self._nodes:
            return

        # Group nodes by type (preserving original relative order within groups)
        source_nodes = [n for n in self._nodes if n.type == "source"]
        terminal_nodes = [n for n in self._nodes if n.type == "terminal"]
        pole_nodes = [n for n in self._nodes if n.type == "pole"]

        # Rebuild in the desired order
        ordered_nodes = source_nodes + terminal_nodes + pole_nodes

        # Re-index everything densely
        self._nodes = []
        self._terminal_indices = []
        self._pole_indices = []
        self._source_idx = 0

        for i, node in enumerate(ordered_nodes):
            new_node = Node(
                index=i,
                lat=node.lat,
                lng=node.lng,
                name=node.name or f"{node.type} {i}",
                type=node.type,
            )
            self._nodes.append(new_node)

            if node.type == "terminal":
                self._terminal_indices.append(i)
            elif node.type == "pole":
                self._pole_indices.append(i)

        # Rebuild derived arrays
        self._coords = np.array([get_node_coord_tuple(n) for n in self._nodes], dtype=np.float64)
        self._names = [n.name for n in self._nodes]

        if self.request.debug >= 1:
            print(f"✅ Normalized node order → {len(source_nodes)} source + "
                  f"{len(terminal_nodes)} terminals + {len(pole_nodes)} poles")

    def rename_poles(self, graph: Union[nx.DiGraph, nx.Graph]) -> Union[nx.DiGraph, nx.Graph]:
        """
        Renames the nodes classified as 'poles' in a graph sequentially, based on the depth-first
        search (DFS) discovery order starting from a specified source node. This function also marks
        the renamed poles as used.

        Nodes in the graph are renamed in the format "Pole 001", "Pole 002", etc., for easier identification
        and reference. If the DFS traversal fails or the input graph is malformed, the function falls back
        to handling nodes in their original graph order. The process ensures that only nodes marked as
        'pole' in their attributes are affected.

        Args:
            graph (Union[nx.DiGraph, nx.Graph]): Input graph to be processed. It should support
                NetworkX-compatible functionality such as `dfs_preorder_nodes`.

        Returns:
            Union[nx.DiGraph, nx.Graph]: A new graph with renamed pole nodes and updated attributes.
        """
        if self._source_idx is None or not graph:
            return graph

        graph = graph.copy()

        try:
            # DFS preorder traversal from source (depth-first discovery order)
            dfs_order = list(nx.dfs_preorder_nodes(graph, self._source_idx))
        except (nx.NetworkXError, KeyError):
            # Fallback if graph is malformed
            dfs_order = list(graph.nodes())

        # Collect poles in the exact DFS discovery order
        poles = []
        for idx in dfs_order:
            data = graph.nodes[idx]
            if data.get('type') == 'pole':
                poles.append((idx, data))

        # Rename poles sequentially
        for i, (idx, data) in enumerate(poles, 1):
            graph.nodes[idx]['name'] = f"Pole {i:03d}"
            graph.nodes[idx]['used'] = True

        if self.request.debug >= 1:
            print(f"✅ Renamed {len(poles)} poles using DFS (depth-first) order from source")

        return graph

    def prune_dead_end_pole_branches(self, graph: Union[nx.Graph, nx.DiGraph]) -> Union[nx.Graph, nx.DiGraph]:
        """
        Prunes dead-end pole branches in a Directed Graph (DiGraph).

        This function removes leaf nodes in the provided graph that represent poles and do not serve
        any terminal nodes in their subtree. The pruning process continues iteratively until no such
        dead-end poles remain in the graph. It modifies a copy of the input graph without affecting
        the original.

        Args:
            graph: A directed graph representing the network structure.

        Returns:
            A new graph with dead-end pole branches removed.
        """
        graph = graph.copy()

        removed = True
        while removed:
            removed = False
            leaves = [n for n in graph.nodes(data=True) if graph.out_degree(n[0]) == 0]
            for leaf in leaves:
                if leaf[1]['type'] == "pole":
                    # Check if this leaf (or its subtree) serves any terminal
                    descendants = nx.descendants(graph, leaf[0]) | {leaf[0]}
                    if not any(graph.nodes(data=True)[d]['type'] == 'terminal' for d in descendants):
                        # No terminal served → safe to remove
                        predecessors = list(graph.predecessors(leaf[0]))
                        for pred in predecessors:
                            graph.remove_edge(pred, leaf[0])
                        graph.remove_node(leaf[0])
                        removed = True

        graph = self.rename_poles(graph)

        return graph

    def _recompute_edges_for_node(self, graph: Union[nx.DiGraph, nx.Graph], node_idx: int):
        """
        Recomputes the edge attributes for all edges connected to a specific node in
        the graph. The method updates the 'length' and 'weight' attributes of each
        edge based on the Haversine distance between the nodes and the edge's
        associated voltage level.

        Args:
            graph (Union[nx.DiGraph, nx.Graph]): The graph object representing the
                network. It can be either a directed or undirected graph and must
                contain 'lat' and 'lng' attributes for its nodes.
            node_idx (int): The index of the node for which the edges need to be
                recomputed.
        """
        # Get ALL edges touching this node (incoming + outgoing)
        if isinstance(graph, nx.DiGraph):
            incident_edges = list(graph.in_edges(node_idx, data=True)) + \
                             list(graph.out_edges(node_idx, data=True))
        else:
            incident_edges = list(graph.edges(node_idx, data=True))

        for u, v, data in incident_edges:
            lat1, lng1 = graph.nodes[u]['lat'], graph.nodes[u]['lng']
            lat2, lng2 = graph.nodes[v]['lat'], graph.nodes[v]['lng']

            length = self.haversine_meters(lat1, lng1, lat2, lng2)

            # Update both the edge data and the stored attributes
            graph[u][v]['length'] = length
            graph[u][v]['weight'] = self.calc_edge_weight(
                length,
                graph[u][v].get('voltage', 'low')
            )

    def _all_edges_valid(self, graph, node_idx: int) -> bool:
        """
        Validates edges of a graph based on length constraints and node type requirements.

        This method checks whether all the edges incident to a specific node in a graph meet the specified
        criteria for length and other node-dependent conditions. It accommodates both directed and undirected
        graphs and differentiates between terminal-to-pole and pole-to-pole node types to enforce appropriate
        constraints.

        Args:
            graph (nx.Graph or nx.DiGraph): Input graph, which can either be a directed or undirected networkx graph.
            node_idx (int): Index of the node to validate within the graph.

        Returns:
            bool: True if all edges incident to the specified node satisfy the constraints, False otherwise.
        """
        if isinstance(graph, nx.DiGraph):
            incident_edges = list(graph.in_edges(node_idx, data=True)) + \
                             list(graph.out_edges(node_idx, data=True))
        else:
            incident_edges = list(graph.edges(node_idx, data=True))

        for u, v, data in incident_edges:
            length = data.get('length', 0.0)
            voltage = data.get('voltage', 'low')

            # Determine max allowed length
            u_type = graph.nodes[u].get('type')
            v_type = graph.nodes[v].get('type')

            if u_type == 'terminal' or v_type == 'terminal':
                max_len = self.get_max_pole_to_term()
            else:
                max_len = self.get_max_pole_to_pole()

            min_len = self.get_min_pole_to_term()

            if (length < min_len + 0.01) or (length > max_len + 0.01):
                return False
        return True

    def _enforce_min_pole_terminal_distances(self, graph: Union[nx.DiGraph, nx.Graph]) -> Union[nx.DiGraph, nx.Graph]:
        """
        Enforces minimum distance constraints between poles and terminals in a graph.

        This method ensures that the physical constraints regarding the minimum distance
        between poles and terminals are upheld within the provided graph. If any poles
        and terminals are found to be closer than the prescribed minimum distance, the
        positions of the poles are adjusted accordingly to meet the constraint. The
        operation is performed on a modified copy of the graph, leaving the original
        graph unaltered.

        Parameters:
            graph (Union[nx.DiGraph, nx.Graph]): The directed or undirected graph
                containing nodes and edges representing poles, terminals, and their
                connections.

        Returns:
            Union[nx.DiGraph, nx.Graph]: A modified graph that satisfies the minimum
            distance constraints between poles and terminals.

        Raises:
            ValueError: If distance calculations fail or graph node attributes are
            missing necessary geographic properties (`lat` and `lng`).
        """
        graph = graph.copy()
        min_dist = self.get_min_pole_to_term()

        if self.request.debug >= 1:
            print(f"\n--- Enforcing min pole-to-terminal distance ({min_dist:.1f}m) ---")

        fixed = 0
        for u, v, data in list(graph.edges(data=True)):
            u_type = graph.nodes[u].get('type')
            v_type = graph.nodes[v].get('type')

            if (u_type == 'terminal' or v_type == 'terminal') and (u_type == 'pole' or v_type == 'pole'):
                pole_idx = u if u_type == 'pole' else v
                term_idx = v if v_type == 'terminal' else u

                lat_p, lon_p = graph.nodes[pole_idx]['lat'], graph.nodes[pole_idx]['lng']
                lat_t, lon_t = graph.nodes[term_idx]['lat'], graph.nodes[term_idx]['lng']

                dist = self.haversine_meters(lat_p, lon_p, lat_t, lon_t)

                if dist < min_dist - 0.01:  # small tolerance
                    # Move pole away from terminal along the line
                    scale = min_dist / dist
                    new_lat = lat_t - scale * (lat_t - lat_p)
                    new_lon = lon_t - scale * (lon_t - lon_p)

                    graph.nodes[pole_idx]['lat'] = float(new_lat)
                    graph.nodes[pole_idx]['lng'] = float(new_lon)
                    fixed += 1

                    if self.request.debug >= 2:
                        print(f"    Fixed pole {pole_idx} → terminal {term_idx} ({dist:.2f}m → {min_dist:.2f}m)")

        if fixed > 0:
            self._recompute_all_edges(graph)
            if self.request.debug >= 1:
                print(f"    → Fixed {fixed} violating edges")
                self._plot_current_graph(graph, title="After min-distance enforcement")

        return graph

    def _post_solver_local_opt(self, graph: Union[nx.DiGraph, nx.Graph]) -> Union[nx.DiGraph, nx.Graph]:
        """
        Performs a local optimization on the given graph to reduce the total cost by
        iteratively applying optimization techniques. This process includes splitting
        long edges, renaming poles, and optimizing pole positions. The function
        terminates when no significant improvement is observed or when a predefined
        maximum number of iterations is reached.

        Args:
            graph (Union[nx.DiGraph, nx.Graph]): The input graph representing the
                structure to be optimized. The graph may be directed or undirected
                and should conform to the assumptions made by the optimization
                algorithms.

        Returns:
            Union[nx.DiGraph, nx.Graph]: The optimized graph after local adjustments
            to minimize the total cost.
        """
        # Initial cleanup
        graph = self.rename_poles(graph)

        previous_cost = self._compute_total_cost(graph)
        best_cost = previous_cost
        best_graph = graph  # optional: for reversion

        iteration = 0
        max_iterations = 12
        convergence_tol = 1e-3
        stagnant_count = 0
        max_stagnant = 1

        if self.request.debug >= 1:
            print(f"\n=== Starting Post-Solver Local Optimization ===")
            print(f"Initial cost: {previous_cost:.2f} | Nodes: {graph.number_of_nodes()}")

        while iteration < max_iterations:
            iteration += 1
            if self.request.debug >= 1:
                print(f"\n--- Iteration {iteration} ---")

            graph = self._pole_gradient_optimizer(graph)
            graph = self._merge_collinear_pole_chains(graph)
            graph = self._drop_redundant_poles(graph)
            graph = self.split_long_edges_w_poles(graph)

            # rebuild graph to refresh attributes and ensure consistency and shortest path
            nodes = [Node(index=x[0], **x[1]) for x in graph.nodes(data=True)]
            graph = self.build_graph_from_nodes(nodes, directed=True)
            graph = self._minimum_spanning_arborescence_w_attrs(graph)
            graph = self.prune_dead_end_pole_branches(graph)

            graph = self.split_long_edges_w_poles(graph)

            if self.request.debug >= 2:
                print(f"Nodes: {graph.number_of_nodes()}")
                self._plot_current_graph(graph, title=f"After iteration {iteration}")

            current_cost = self._compute_total_cost(graph)
            delta = current_cost - previous_cost
            is_close = math.isclose(current_cost, previous_cost, abs_tol=convergence_tol)

            if self.request.debug >= 1:
                print(f"   Cost: {previous_cost:.2f} → {current_cost:.2f} (Δ = {delta:+.2f})")

            # Stopping conditions
            if current_cost > previous_cost + convergence_tol:
                if self.request.debug >= 1:
                    print("   Cost increased significantly → stopping")
                graph = best_graph  # revert
                break

            if is_close:
                stagnant_count += 1
                if stagnant_count >= max_stagnant:
                    if self.request.debug >= 1:
                        print(f"   No meaningful improvement for {max_stagnant} iterations → stopping")
                    break
            else:
                stagnant_count = 0

            previous_cost = current_cost
            if current_cost < best_cost:
                best_cost = current_cost
                best_graph = graph.copy()

        graph = self._enforce_min_pole_terminal_distances(graph)

        final_cost = self._compute_total_cost(graph)

        if self.request.debug >= 1:
            print(f"\n=== Post-opt finished after {iteration} iteration(s). "
                  f"Final cost: {final_cost:.2f} ===\n")

        return graph

    def _drop_redundant_poles(self, pruned_graph: Union[nx.Graph, nx.DiGraph]) -> Union[nx.Graph, nx.DiGraph]:
        """
        Removes redundant pole nodes from the graph that do not contribute to connecting
        terminals. A pole is considered redundant if its removal does not disconnect any
        terminal from the source, and doing so reduces the total cost.

        Args:
            pruned_graph (nx.DiGraph): The directed graph representing the current network
                structure, with nodes containing 'type' and positional attributes.

        Returns:
            nx.DiGraph: A new directed graph with redundant poles removed and poles renamed.

        """
        if self.request.debug >= 1:
            print("\n--- Starting Fast Drop Phase (with proper reconnection) ---")

        current_graph = pruned_graph.copy()
        cur_cost = self._compute_total_cost(current_graph)

        pole_indices = sorted(
            [idx for idx, data in current_graph.nodes(data=True)
             if data.get('type') == 'pole'],
            reverse=True
        )

        for pole_to_drop in pole_indices:
            if self.request.debug >= 2:
                print(f"  Trying to drop pole {pole_to_drop}...")

            # === Build reduced coordinates (without the pole) ===
            coords_list = []
            names_list = []
            for idx, data in sorted(current_graph.nodes(data=True)):
                if idx == pole_to_drop:
                    continue
                coords_list.append([data['lat'], data['lng']])
                names_list.append(data.get('name', f"Node {len(coords_list)}"))

            coords_array = np.array(coords_list, dtype=float) if coords_list else np.empty((0, 2))

            # Fast cost check
            trial_cost = self._fast_total_cost_for_coords(coords_array)

            if trial_cost <= cur_cost + 1e-3:
                # === ACCEPTED DROP → rebuild the correct graph ===
                if self.request.debug >= 1:
                    print(f"Drop Phase: Removed pole {pole_to_drop} (cost {cur_cost:.2f} → {trial_cost:.2f})")

                trial_nodes = self._build_nodes(coords_array, np.empty((0, 2)), names_list)

                DG = self.build_directed_graph_for_arborescence(trial_nodes)
                arbo_graph = self._minimum_spanning_arborescence_w_attrs(DG)
                new_graph = self.prune_dead_end_pole_branches(arbo_graph)

                current_graph = new_graph
                cur_cost = trial_cost
            else:
                if self.request.debug >= 2:
                    print(f"Drop Phase: Kept pole {pole_to_drop} (would increase cost to {trial_cost:.2f})")

        if self.request.debug >= 1:
            print("--- Fast Drop Phase Complete ---\n")
            self._plot_current_graph(current_graph, added_points=None, title="After Drop Phase")

        current_graph = self.rename_poles(current_graph)
        current_graph = self.rename_poles(current_graph)
        return current_graph

    def _pole_gradient_optimizer(self, graph: Union[nx.DiGraph, nx.Graph]) -> Union[nx.DiGraph, nx.Graph]:
        """
        Performs a gradient-based optimization on the positions of specified "pole" nodes within
        a graph to minimize a cost function. The optimization adjusts the latitude and longitude
        of the pole nodes within a defined movement constraint to achieve a reduction in the total cost.

        The process involves multiple passes of sequential optimization for the poles, using a
        BFGS optimization algorithm for fine-tuning the positions of nodes.

        Args:
            graph: A networkx graph (directed or undirected) containing nodes and edges. The graph
                nodes must have the attributes 'lat', 'lng', and 'type', where 'type' indicates
                the node type, and certain nodes with 'type' set to 'pole' will be optimized.

        Returns:
            A modified version of the input graph with adjusted node positions for pole nodes if
            optimizations resulted in cost reductions. If no optimizations were possible, the
            input graph is returned without modifications.

        """
        pole_indices = [idx for idx, data in graph.nodes(data=True)
                        if data.get('type') == 'pole']
        if not pole_indices:
            return graph

        graph = graph.copy()
        n_passes = 3

        max_move_meters = 20.0
        one_meter_deg = 1.0 / 111111.0
        max_delta_deg = max_move_meters * one_meter_deg

        if self.request.debug >= 1:
            initial_cost = self._compute_total_cost(graph)
            print(f"\n=== Sequential Pole Optimization ({len(pole_indices)} poles, "
                  f"{n_passes} passes, max move {max_move_meters}m) ===")
            print(f"Initial cost: {initial_cost:.2f}")

        improved_anywhere = True
        total_improvement = 0.0

        for pass_num in range(n_passes):
            if not improved_anywhere and pass_num > 0:
                if self.request.debug >= 1:
                    print(f"   No improvement in pass {pass_num} → stopping early")
                break

            improved_anywhere = False
            pole_order = self._get_pole_optimization_order(
                graph,
                farthest_first=False
            )

            for node_idx in pole_order:
                if node_idx not in graph:
                    continue

                lat0 = graph.nodes[node_idx]['lat']
                lon0 = graph.nodes[node_idx]['lng']
                old_cost = self._compute_total_cost(graph)

                def objective(x):
                    lat, lon = x
                    # Temporarily move pole
                    graph.nodes[node_idx]['lat'] = float(lat)
                    graph.nodes[node_idx]['lng'] = float(lon)
                    self._recompute_all_edges(graph)

                    return self._compute_total_cost(graph)

                res = minimize(
                    objective,
                    [lat0, lon0],
                    method='BFGS',
                )

                new_cost = res.fun

                best_lat, best_lon = res.x
                graph.nodes[node_idx]['lat'] = float(best_lat)
                graph.nodes[node_idx]['lng'] = float(best_lon)
                self._recompute_all_edges(graph)

                if new_cost < old_cost - 0.5:  # only accept meaningful real savings
                    improved_anywhere = True
                    total_improvement += (new_cost - old_cost)
                    edge_lengths = [e[2]['length'] for e in graph.edges(data=True)]
                    if self.request.debug >= 1:
                        print("Max edge length after move:", max(edge_lengths) if edge_lengths else 0.0)
                    if self.request.debug >= 1:
                        move_m = math.hypot(
                            (res.x[0] - lat0) / one_meter_deg,
                            (res.x[1] - lon0) / one_meter_deg
                        )
                        print(f"   Pole {node_idx:3d} improved by {new_cost - old_cost:+.2f} $ "
                              f"(moved {move_m:.3f}m)")
                    if self.request.debug >= 3:
                        self._plot_current_graph(graph, added_points=[(res.x[0], res.x[1])], )
                else:
                    # Revert to original position
                    graph.nodes[node_idx]['lat'] = lat0
                    graph.nodes[node_idx]['lng'] = lon0
                    self._recompute_all_edges(graph)

        final_cost = self._compute_total_cost(graph)
        if self.request.debug >= 1:
            print(f"Optimization finished → cost {initial_cost:.2f} → {final_cost:.2f} "
                  f"(total improvement {total_improvement:.2f})")

        if self.request.debug >= 1:
            self._plot_current_graph(graph,
                                     title=f"After Sequential Pole Optimization(${self._compute_total_cost(graph):.2f}) + {self.print_min_max_edge_len(graph)}")

        return graph

    def _merge_collinear_pole_chains(self, graph: Union[nx.Graph, nx.DiGraph]) -> Union[nx.Graph, nx.DiGraph]:
        """
        Merges collinear pole chains in a graph by identifying and collapsing straight sequences of nodes
        between branching points or terminals into single long edges. This process improves the
        graph's simplicity and efficiency by reducing intermediate nodes.

        Args:
            graph (Union[nx.Graph, nx.DiGraph]): The input graph, which may represent electrical or similar
                networks. The graph nodes should have attributes `lat`, `lng`, and `type`. If the graph
                is undirected, it will be transformed into a directed graph for processing.

        Returns:
            Union[nx.Graph, nx.DiGraph]: A graph with merged pole chains as long straight segments. The
            returned graph will have fewer intermediate nodes, with edge lengths properly aggregated.

        Raises:
            ValueError: If required graph attributes are missing or invalid for processing.

        """
        graph = graph.copy()
        merged_count = 0

        # Ensure we have a proper directed arborescence (edges point away from source)
        if not isinstance(graph, nx.DiGraph):
            graph = self.build_directed_graph_for_arborescence(
                [Node(index=i, lat=n['lat'], lng=n['lng'], type=n['type'], name=n.get('name'))
                 for i, n in graph.nodes(data=True)]
            )

        terminal_nodes = [
            n for n, data in graph.nodes(data=True)
            if data.get('type') == 'terminal'
        ]

        visited = set()  # prevent re-processing overlapping chains

        for term_idx in terminal_nodes:
            if term_idx in visited:
                continue

            # Build chain UPSTREAM from terminal
            chain = [term_idx]
            current = term_idx

            while True:
                preds = list(graph.predecessors(current))
                if len(preds) != 1:  # not a straight path
                    break
                pred = preds[0]

                # Stop when we hit a branching node (more than 1 successor)
                if graph.out_degree(pred) > 1:
                    chain.append(pred)
                    break

                # Also stop at source (it has no predecessor)
                if pred == self._source_idx:
                    chain.append(pred)
                    break

                chain.append(pred)
                current = pred

                if current in visited:
                    break

            # Reverse so chain[0] = upstream branching node / source
            #          chain[-1] = terminal
            chain = chain[::-1]

            # Need at least 2 edges (3 nodes) to be worth merging
            if len(chain) < 3:
                continue

            # Check collinearity
            is_straight = True
            for i in range(len(chain) - 2):
                p1 = np.array([graph.nodes[chain[i]]['lat'], graph.nodes[chain[i]]['lng']])
                p2 = np.array([graph.nodes[chain[i + 1]]['lat'], graph.nodes[chain[i + 1]]['lng']])
                p3 = np.array([graph.nodes[chain[i + 2]]['lat'], graph.nodes[chain[i + 2]]['lng']])

                v1 = p2 - p1
                v2 = p3 - p2
                cross = abs(v1[0] * v2[1] - v1[1] * v2[0])
                if cross > 1e-5:  # tight tolerance (~0.5–1°)
                    is_straight = False
                    break

            if not is_straight:
                continue

            # === MERGE the straight chain ===
            start_idx = chain[0]  # branching node or source
            end_idx = chain[-1]  # terminal
            end_type = graph.nodes[end_idx].get('type')

            # Compute true total length of the chain
            total_length = 0.0
            for i in range(len(chain) - 1):
                total_length += graph[chain[i]][chain[i + 1]]['length']

            # Remove all intermediate poles
            for mid in chain[1:-1]:
                if graph.nodes[mid].get('type') == 'pole':
                    graph.remove_node(mid)
                    merged_count += 1

            # Add single long edge
            is_to_terminal = (end_type == 'terminal')
            graph.add_edge(
                start_idx, end_idx,
                length=total_length,
                voltage=graph.nodes[start_idx].get('voltage', self.request.voltageLevel),
                weight=self.calc_edge_weight(total_length, to_terminal=is_to_terminal)
            )

            # Mark all nodes in this chain as visited
            visited.update(chain)

        graph = self.rename_poles(graph)

        if self.request.debug >= 1 and merged_count > 0:
            print(f"  _merge_collinear_pole_chains: merged {merged_count} intermediate poles "
                  f"into long straight segments (terminal-first, stop at branch points)")
            self._plot_current_graph(graph, title="After Collinear Merge (terminal-first + branch stop)")

        return graph

    def _place_max_stretched_last_divided(
            self,
            new_graph: Union[nx.Graph, nx.DiGraph],
            start_idx: int,
            end_idx: int,
            segment_length: float,
            max_spacing: float,
            node_data: dict,
            next_index: int,
            voltage: str,
            is_terminal_segment: bool = False,
    ) -> Tuple[int, int]:
        """
        Places intermediate nodes and edges in a graph to create evenly spaced segments between a
        start node and an end node. The function prioritizes spacing close to the maximum segment
        length, but the last two segments are spaced equally to evenly distribute the remainder of
        the distance.

        Args:
            new_graph: A directed graph to which new nodes and edges will be added.
            start_idx: Index of the start node in the segment.
            end_idx: Index of the end node in the segment.
            segment_length: Total length of the segment to be divided, in meters.
            max_spacing: Maximum allowable distance between two consecutive intermediate nodes.
            node_data: A dictionary containing node attributes such as latitude, longitude, and type.
            next_index: The next available index for new nodes in the graph.
            voltage: Voltage level of the power line or edge being created.
            is_terminal_segment: A boolean indicating whether this segment ends at a terminal node.
                Defaults to False.

        Returns:
            tuple[int, int]: A tuple containing the updated next available index for new nodes and
            the index of the last intermediate node added.
        """
        if segment_length <= max_spacing + 0.1:
            # Nothing to split — direct edge already exists or will be added outside
            return next_index, start_idx

        import math
        num_segments = math.ceil(segment_length / max_spacing)

        start_pos = np.array([node_data[start_idx]["lat"], node_data[start_idx]["lng"]], dtype=float)
        end_pos = np.array([node_data[end_idx]["lat"], node_data[end_idx]["lng"]], dtype=float)

        prev_idx = start_idx
        current_next = next_index
        current_pos = start_pos.copy()

        # Number of FULL maximum segments before the final two
        num_full = max(0, num_segments - 2)

        # 1. Place the full stretched segments
        for _ in range(num_full):
            move_m = max_spacing
            frac = move_m / segment_length
            current_pos += frac * (end_pos - start_pos)

            # Add pole
            new_graph.add_node(
                current_next,
                lat=float(current_pos[0]),
                lng=float(current_pos[1]),
                type="pole",
                name=f"Pole {current_next}",
            )
            node_data[current_next] = {
                "lat": float(current_pos[0]),
                "lng": float(current_pos[1]),
                "type": "pole",
            }

            new_graph.add_edge(
                prev_idx,
                current_next,
                length=move_m,
                voltage=voltage,
                weight=self.calc_edge_weight(move_m, to_terminal=False),
            )

            prev_idx = current_next
            current_next += 1

        # 2. Remaining length for the last TWO equal segments
        remaining_length = segment_length - num_full * max_spacing
        last_segment_length = remaining_length / 2.0

        # Place the penultimate pole (start of the two equal segments)
        frac = last_segment_length / segment_length
        current_pos += frac * (end_pos - start_pos)

        new_graph.add_node(
            current_next,
            lat=float(current_pos[0]),
            lng=float(current_pos[1]),
            type="pole",
            name=f"Pole {current_next}",
        )
        node_data[current_next] = {
            "lat": float(current_pos[0]),
            "lng": float(current_pos[1]),
            "type": "pole",
        }

        new_graph.add_edge(
            prev_idx,
            current_next,
            length=last_segment_length,
            voltage=voltage,
            weight=self.calc_edge_weight(last_segment_length, to_terminal=False),
        )

        prev_idx = current_next
        current_next += 1

        # Final edge (second half of the last stretch)
        new_graph.add_edge(
            prev_idx,
            end_idx,
            length=last_segment_length,
            voltage=voltage,
            weight=self.calc_edge_weight(last_segment_length, to_terminal=is_terminal_segment),
        )

        return current_next, prev_idx

    def split_long_edges_w_poles(self, graph: Union[nx.Graph, nx.DiGraph]) -> Union[nx.Graph, nx.DiGraph]:
        """
        Splits long edges in the given graph with new pole nodes if their length exceeds
        the allowable distance for either pole-to-terminal or pole-to-pole connections.

        This method modifies edges in the graph to make sure that no edge has a length
        greater than the maximum allowable distance for its type. For terminal edges, a
        serving pole is added at the maximum allowable distance, and for pole-to-pole
        edges, additional poles are added at regular intervals.

        Args:
            graph (Union[nx.Graph, nx.DiGraph]): The input network graph, where edges
                represent segments between nodes and their attributes contain details
                such as length, voltage, and type.

        Returns:
            nx.DiGraph: A directed graph that includes newly added poles to ensure that
                all edges comply with maximum allowable lengths, depending on their type.

        Raises:
            nx.NetworkXError: If shortest-path calculations fail for the given graph.
            KeyError: If expected graph attributes for node positions or edge properties
                are missing during processing.

        """
        new_graph = graph.copy()

        node_data = {n: data.copy() for n, data in new_graph.nodes(data=True)}
        if not node_data:
            return new_graph

        next_index = max(new_graph.nodes) + 1

        # Pre-compute source distances for pole-pole direction heuristic
        source_dist = {}
        try:
            source_dist = nx.single_source_dijkstra_path_length(
                new_graph, self._source_idx, weight="length"
            )
        except (nx.NetworkXError, KeyError):
            pass

        for u, v, data in list(new_graph.edges(data=True)):
            if u not in new_graph or v not in new_graph:
                continue

            u_type = new_graph.nodes[u].get("type", "")
            v_type = new_graph.nodes[v].get("type", "")
            length_m = float(data.get("length", 0.0))
            voltage = data.get("voltage", self.request.voltageLevel)

            is_terminal_edge = u_type == "terminal" or v_type == "terminal"

            if is_terminal_edge:
                max_allowed = self.get_max_pole_to_term()
            else:
                max_allowed = self.get_max_pole_to_pole()

            if length_m <= max_allowed + 0.1:
                continue

            # Determine start/end of the segment
            if is_terminal_edge:
                term_idx = u if u_type == "terminal" else v
                far_idx = v if u_type == "terminal" else u
                start_idx = term_idx
                end_idx = far_idx
                to_terminal_for_serving = True
            else:
                # Pole-pole: bias toward source
                d_u = source_dist.get(u, self._distance_from_source(new_graph, u))
                d_v = source_dist.get(v, self._distance_from_source(new_graph, v))
                start_idx, end_idx = (u, v) if d_u <= d_v else (v, u)
                to_terminal_for_serving = False

            new_graph.remove_edge(u, v)

            prev_idx = start_idx
            remaining_m = length_m

            # ── Terminal edge special case: exact serving pole ──
            if is_terminal_edge:
                start_pos = np.array([node_data[start_idx]["lat"], node_data[start_idx]["lng"]])
                end_pos = np.array([node_data[end_idx]["lat"], node_data[end_idx]["lng"]])

                frac = max_allowed / length_m
                serving_pos = start_pos + frac * (end_pos - start_pos)

                new_graph.add_node(
                    next_index,
                    lat=float(serving_pos[0]),
                    lng=float(serving_pos[1]),
                    type="pole",
                    name=f"Pole {next_index}",
                )
                node_data[next_index] = {
                    "lat": float(serving_pos[0]),
                    "lng": float(serving_pos[1]),
                    "type": "pole",
                }

                new_graph.add_edge(
                    start_idx,
                    next_index,
                    length=max_allowed,
                    voltage=voltage,
                    weight=self.calc_edge_weight(max_allowed, to_terminal=True),
                )

                prev_idx = next_index
                next_index += 1
                remaining_m = length_m - max_allowed
                max_allowed = self.get_max_pole_to_pole()  # now treat trunk as pole-pole

            # ── Main trunk (pole-pole): fully stretched + last stretch divided in two ──
            next_index, _ = self._place_max_stretched_last_divided(
                new_graph=new_graph,
                start_idx=prev_idx,
                end_idx=end_idx,
                segment_length=remaining_m,
                max_spacing=max_allowed,
                node_data=node_data,
                next_index=next_index,
                voltage=voltage,
                is_terminal_segment=to_terminal_for_serving and (prev_idx != end_idx),
            )

        new_graph = self.rename_poles(new_graph)

        if self.request.debug >= 1:
            added_poles = next_index - (max(node_data.keys()) + 1 if node_data else 0)
            print(f"  split_long_edges_w_poles: added {added_poles} new poles "
                  f"(max stretched + last stretch divided in two → no clusters)")
            self._plot_current_graph(new_graph, title="After Max-Stretched + Last-Divided Splitting")

        return new_graph
