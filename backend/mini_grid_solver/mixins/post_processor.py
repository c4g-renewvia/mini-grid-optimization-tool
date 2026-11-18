import math
from typing import Union, List, Tuple

import networkx as nx
import numpy as np
from scipy.optimize import minimize

from .costs import EDGE_LENGTH_TOLERANCE_METERS
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
        """Count poles and sum wire lengths by voltage level.

        Args:
            graph (Union[nx.Graph, nx.DiGraph]): Network graph with node types
                and edge lengths and voltage levels.

        Returns:
            Tuple[int, float, float]: Pole count, low-voltage wire length, and
                high-voltage wire length.
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
        """Order nodes as source, terminals, then poles and remap edge indices.

        Args:
            graph (Union[nx.DiGraph, nx.Graph]): Graph whose nodes and edges
                will be converted to ordered node and edge objects.

        Returns:
            tuple[list[Node], list[Edge]]: Reindexed nodes and remapped edges.
        """
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
        """Sort poles by shortest-path distance from the source.

        Args:
            graph (Union[nx.DiGraph, nx.Graph]): Graph containing the poles.
            farthest_first (bool): Whether to sort from farthest to closest.

        Returns:
            List[int]: Pole indices in optimization order.
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
        """Reorder source, terminal, and pole nodes and rebuild derived metadata."""
        if not self._nodes:
            return

        # Group nodes by type (preserving original relative order within groups)
        source_nodes, terminal_nodes, pole_nodes = [], [], []
        for n in self._nodes:
            if n.type == "source":
                source_nodes.append(n)
            elif n.type == "terminal":
                terminal_nodes.append(n)
            elif n.type == "pole":
                pole_nodes.append(n)

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
        """Rename pole nodes in depth-first discovery order from the source.

        Args:
            graph (Union[nx.DiGraph, nx.Graph]): Graph containing poles to rename.

        Returns:
            Union[nx.DiGraph, nx.Graph]: Copy of the graph with sequentially
                named poles marked as used.
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
        """Remove dead-end pole branches from a graph copy.

        Args:
            graph (Union[nx.Graph, nx.DiGraph]): Graph containing typed nodes.

        Returns:
            Union[nx.Graph, nx.DiGraph]: Copy with dangling pole branches removed.
        """
        graph = graph.copy()
        out_degrees = dict(graph.out_degree())
        leaves = [n for n, deg in out_degrees.items() if deg == 0]

        while leaves:
            leaf = leaves.pop()
            if leaf in graph and graph.nodes[leaf].get('type') == 'pole':
                preds = list(graph.predecessors(leaf))
                graph.remove_node(leaf)
                for pred in preds:
                    out_degrees[pred] -= 1
                    if out_degrees[pred] == 0:
                        leaves.append(pred)
        return graph

    def _recompute_edges_for_node(self, graph: Union[nx.DiGraph, nx.Graph], node_idx: int):
        """Recompute lengths and weights for edges incident to a node.

        Args:
            graph (Union[nx.DiGraph, nx.Graph]): Graph containing the node.
            node_idx (int): Index of the node whose incident edges are updated.
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
        """Check whether all edges incident to a node meet length constraints.

        Args:
            graph (nx.Graph or nx.DiGraph): Graph containing the node.
            node_idx (int): Index whose incident edges are validated.

        Returns:
            bool: Whether every incident edge satisfies the applicable limits.
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
        """Move poles as needed to enforce minimum pole-to-terminal distances.

        Args:
            graph (Union[nx.DiGraph, nx.Graph]): Graph containing pole-terminal edges.

        Returns:
            Union[nx.DiGraph, nx.Graph]: Copy with violating pole positions adjusted.
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

    def _drop_redundant_poles(self, pruned_graph: Union[nx.Graph, nx.DiGraph]) -> Union[nx.Graph, nx.DiGraph]:
        """Remove poles when bypassing them does not increase graph cost.

        Args:
            pruned_graph (Union[nx.Graph, nx.DiGraph]): Graph to simplify.

        Returns:
            Union[nx.Graph, nx.DiGraph]: Graph after accepted pole removals, or the
                original graph when no removal improves cost.
        """
        if self.request.debug >= 1:
            print("\n--- Starting _drop_redundant_poles (pred→succ + terminal→nearest-pole) ---")

        # Copy exactly once to avoid mutating the caller's graph
        current_graph = pruned_graph.copy()
        cur_cost = self._compute_total_cost(current_graph)

        iteration = 0
        max_drop_iterations = 50
        changed = False

        while iteration < max_drop_iterations:
            iteration += 1

            pole_indices = sorted(
                [idx for idx, data in current_graph.nodes(data=True)
                 if data.get('type') == 'pole'],
                reverse=True
            )

            if not pole_indices:
                break

            dropped_this_pass = False

            for pole_to_drop in pole_indices:
                if pole_to_drop not in current_graph:
                    continue

                if self.request.debug >= 2:
                    print(f"  Trying to drop pole {pole_to_drop}...")

                # --- 1. SAVE ORIGINAL STATE FOR POTENTIAL REVERT ---
                is_directed = current_graph.is_directed()

                try:
                    upstream = list(current_graph.predecessors(pole_to_drop))
                    downstream = list(current_graph.successors(pole_to_drop))
                except AttributeError:
                    # Robust fallback for undirected nx.Graph
                    upstream = list(current_graph.neighbors(pole_to_drop))
                    downstream = list(current_graph.neighbors(pole_to_drop))

                if not upstream or not downstream:
                    continue

                original_node_data = current_graph.nodes[pole_to_drop].copy()

                if is_directed:
                    original_in_edges = list(current_graph.in_edges(pole_to_drop, data=True))
                    original_out_edges = list(current_graph.out_edges(pole_to_drop, data=True))
                else:
                    original_edges = list(current_graph.edges(pole_to_drop, data=True))

                direct_terminals = [
                    n for n in set(upstream + downstream)
                    if current_graph.nodes[n].get('type') == 'terminal'
                ]

                # --- 2. APPLY TRIAL MODIFICATIONS IN-PLACE ---
                current_graph.remove_node(pole_to_drop)
                added_edges = []

                # 2a. Bypass: upstream -> downstream
                for pred in upstream:
                    if pred not in current_graph:
                        continue
                    for succ in downstream:
                        if current_graph.nodes[succ].get('type') == 'terminal':
                            continue
                        if succ not in current_graph or pred == succ:
                            continue
                        if current_graph.has_edge(pred, succ):
                            continue

                        dist = self.haversine_meters(
                            current_graph.nodes[pred]['lat'], current_graph.nodes[pred]['lng'],
                            current_graph.nodes[succ]['lat'], current_graph.nodes[succ]['lng']
                        )
                        voltage = current_graph.nodes[pred].get('voltage', self.request.voltageLevel)

                        current_graph.add_edge(
                            pred, succ,
                            length=round(dist, 4),
                            voltage=voltage,
                            weight=self.calc_edge_weight(dist, to_terminal=False)
                        )
                        added_edges.append((pred, succ))

                # 2b. Reconnect orphans: terminal -> nearest remaining pole
                for term in direct_terminals:
                    if term not in current_graph:
                        continue

                    other_poles = [
                        n for n in current_graph.nodes
                        if current_graph.nodes[n].get('type') == 'pole'
                    ]
                    if not other_poles:
                        continue

                    best_target = None
                    best_dist = float('inf')

                    for target in other_poles:
                        if (current_graph.has_edge(target, term) or
                                current_graph.has_edge(term, target)):
                            continue

                        d = self.haversine_meters(
                            current_graph.nodes[term]['lat'], current_graph.nodes[term]['lng'],
                            current_graph.nodes[target]['lat'], current_graph.nodes[target]['lng']
                        )
                        if d < best_dist:
                            best_dist = d
                            best_target = target

                    if best_target is not None:
                        voltage = current_graph.nodes[best_target].get('voltage', self.request.voltageLevel)
                        current_graph.add_edge(
                            best_target, term,
                            length=round(best_dist, 4),
                            voltage=voltage,
                            weight=self.calc_edge_weight(best_dist, to_terminal=True)
                        )
                        added_edges.append((best_target, term))

                # --- 3. EVALUATE & COMMIT OR REVERT ---
                trial_cost = self._compute_total_cost(current_graph)

                if trial_cost <= cur_cost + 1e-3:
                    # SUCCESS: Keep modifications and move on
                    if self.request.debug >= 1:
                        print(f"Drop Phase: Removed pole {pole_to_drop} "
                              f"(cost {cur_cost:.2f} → {trial_cost:.2f})")
                    cur_cost = trial_cost
                    dropped_this_pass = True
                    changed = True
                    break  # Restart loop to catch cascading improvements

                else:
                    # FAIL: Revert to exact original state
                    if self.request.debug >= 2:
                        print(f"  → Drop would increase cost to {trial_cost:.2f} → kept pole")

                    # Remove trial bypass/serving edges
                    current_graph.remove_edges_from(added_edges)

                    # Re-insert pole and original edges
                    current_graph.add_node(pole_to_drop, **original_node_data)

                    if is_directed:
                        current_graph.add_edges_from([(u, v, d) for u, v, d in original_in_edges])
                        current_graph.add_edges_from([(u, v, d) for u, v, d in original_out_edges])
                    else:
                        current_graph.add_edges_from([(u, v, d) for u, v, d in original_edges])

            if not dropped_this_pass:
                # No improvements were found across all poles; terminate
                break

        if not changed:
            if self.request.debug >= 1:
                print("No redundant poles dropped - returning original graph unchanged")
            return pruned_graph

        if self.request.debug >= 1:
            print(f"--- _drop_redundant_poles Complete after {iteration} pass(es) ---")
            self._plot_current_graph(current_graph, title="After Targeted Drop Phase (pred→succ + terminal nearest)")

        # Final cleanup pass
        current_graph = self.prune_dead_end_pole_branches(current_graph)

        return current_graph

    def _pole_gradient_optimizer(self, graph: Union[nx.DiGraph, nx.Graph]) -> Union[nx.DiGraph, nx.Graph]:
        """Optimize pole coordinates with sequential BFGS passes.

        Args:
            graph (Union[nx.DiGraph, nx.Graph]): Graph containing typed nodes with
                geographic coordinates.

        Returns:
            Union[nx.DiGraph, nx.Graph]: Copy with any cost-improving pole positions.
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
                    """Return graph cost after temporarily moving the pole.

                    Args:
                        x: Candidate latitude and longitude.

                    Returns:
                        float: Total graph cost at the candidate coordinates.
                    """
                    lat, lon = x
                    # Temporarily move pole
                    graph.nodes[node_idx]['lat'] = float(lat)
                    graph.nodes[node_idx]['lng'] = float(lon)
                    self._recompute_edges_for_node(graph, node_idx)

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
                        self._plot_current_graph(graph, added_points=[(res.x[0], res.x[1])], title="Optimized Point Candidate")
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
        """Collapse straight pole chains into single edges.

        Args:
            graph (Union[nx.Graph, nx.DiGraph]): Graph with typed nodes and coordinates.

        Returns:
            Union[nx.Graph, nx.DiGraph]: Copy with collinear intermediate poles removed.
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
        """Split a segment and add intermediate poles to meet spacing limits.

        Args:
            new_graph (Union[nx.Graph, nx.DiGraph]): Graph receiving nodes and edges.
            start_idx (int): Starting node index.
            end_idx (int): Ending node index.
            segment_length (float): Segment length in meters.
            max_spacing (float): Maximum allowed spacing in meters.
            node_data (dict): Node metadata, including geographic coordinates.
            next_index (int): Index to assign to the next inserted pole.
            voltage (str): Voltage level for the segment.
            is_terminal_segment (bool): Whether the final edge ends at a terminal.

        Returns:
            Tuple[int, int]: Next available index and the last inserted or start index.
        """
        if segment_length <= max_spacing + EDGE_LENGTH_TOLERANCE_METERS:
            # CRITICAL FIX: short segment → just add the direct edge back
            new_graph.add_edge(
                start_idx,
                end_idx,
                length=segment_length,
                voltage=voltage,
                weight=self.calc_edge_weight(segment_length, to_terminal=is_terminal_segment),
            )
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

            # CRITICAL FIX: Ensure edge points strictly outward (prev -> current)
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

        # Place the penultimate pole
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
        """Split overlong edges by inserting intermediate poles.

        Args:
            graph (Union[nx.Graph, nx.DiGraph]): Network graph whose long edges
                may need intermediate poles.

        Returns:
            Union[nx.Graph, nx.DiGraph]: Copy with overlong edges split while
                maintaining upstream-to-downstream direction.
        """
        new_graph = graph.copy()

        node_data = {n: data.copy() for n, data in new_graph.nodes(data=True)}
        if not node_data:
            return new_graph

        next_index = max(new_graph.nodes) + 1

        # Pre-compute source distances to guarantee strict upstream -> downstream directionality
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

            if length_m <= max_allowed + EDGE_LENGTH_TOLERANCE_METERS:
                continue

            # CRITICAL FIX: Always ensure start_idx is upstream, end_idx is downstream.
            # Terminals are leaves, so they will always naturally become the end_idx.
            d_u = source_dist.get(u, self._distance_from_source(new_graph, u))
            d_v = source_dist.get(v, self._distance_from_source(new_graph, v))
            start_idx, end_idx = (u, v) if d_u <= d_v else (v, u)

            new_graph.remove_edge(u, v)
            remaining_m = length_m

            # ── Terminal edge special case: exact serving pole ──
            if is_terminal_edge:
                start_pos = np.array([node_data[start_idx]["lat"], node_data[start_idx]["lng"]])
                end_pos = np.array([node_data[end_idx]["lat"], node_data[end_idx]["lng"]])

                # We know end_idx is the terminal. Place serving pole exactly max_allowed away from it.
                frac = (length_m - max_allowed) / length_m
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

                # Add final serving edge pointing outward (Serving Pole -> Terminal)
                new_graph.add_edge(
                    next_index,
                    end_idx,
                    length=max_allowed,
                    voltage=voltage,
                    weight=self.calc_edge_weight(max_allowed, to_terminal=True),
                )

                # The upstream trunk now ends at the new serving pole
                end_idx = next_index
                next_index += 1
                remaining_m = length_m - max_allowed
                max_allowed = self.get_max_pole_to_pole()  # Treat the upstream trunk as pole-pole

            # ── Main trunk (pole-pole): fully stretched + last stretch divided in two ──
            next_index, _ = self._place_max_stretched_last_divided(
                new_graph=new_graph,
                start_idx=start_idx,
                end_idx=end_idx,
                segment_length=remaining_m,
                max_spacing=max_allowed,
                node_data=node_data,
                next_index=next_index,
                voltage=voltage,
                is_terminal_segment=False, # Serving weight was already applied if it was a terminal edge
            )

        new_graph = self.rename_poles(new_graph)

        if self.request.debug >= 1:
            added_poles = next_index - (max(node_data.keys()) + 1 if node_data else 0)
            print(f"  split_long_edges_w_poles: added {added_poles} new poles "
                  f"(max stretched + last stretch divided in two → no clusters)")
            self._plot_current_graph(new_graph, title="After Max-Stretched + Last-Divided Splitting")

        return new_graph

    def _post_solver_opt(self, graph: Union[nx.DiGraph, nx.Graph]) -> Union[nx.DiGraph, nx.Graph]:
        """Iteratively apply local graph optimizations to reduce total cost.

        Args:
            graph (Union[nx.DiGraph, nx.Graph]): Graph to optimize.

        Returns:
            Union[nx.DiGraph, nx.Graph]: Graph after local optimization.
        """
        previous_cost = self._compute_total_cost(graph)
        best_cost = previous_cost
        best_graph = graph.copy()

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
            graph = self._pole_block_coordinate_pass(graph)
            graph = self._merge_collinear_pole_chains(graph)
            graph = self.split_long_edges_w_poles(graph)
            graph = self._drop_redundant_poles(graph)

            if self.request.debug >= 2:
                print(f"Nodes: {graph.number_of_nodes()}")
                self._plot_current_graph(graph, title=f"Candidate after iteration {iteration} (before acceptance)")

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

        if self.request.debug >= 2:
            self._plot_current_graph(graph, title="Final accepted local optimization graph")

        return graph

    def _pole_block_coordinate_pass(self, graph: Union[nx.DiGraph, nx.Graph]) -> Union[nx.DiGraph, nx.Graph]:
        """Optimize small connected pole neighborhoods with shared translations.

        Args:
            graph (Union[nx.DiGraph, nx.Graph]): Graph containing poles to optimize.

        Returns:
            Union[nx.DiGraph, nx.Graph]: Graph with accepted block coordinate updates.
        """
        if graph.number_of_nodes() == 0:
            return graph

        pole_nodes = [n for n, d in graph.nodes(data=True) if d.get("type") == "pole"]
        if not pole_nodes:
            return graph

        und = graph.to_undirected() if isinstance(graph, nx.DiGraph) else graph
        nbr_map = {}
        for p in pole_nodes:
            nbrs = [q for q in und.neighbors(p) if und.nodes[q].get("type") == "pole"]
            nbr_map[p] = nbrs

        seen_blocks = set()
        blocks = []
        for p in pole_nodes:
            deg = len(nbr_map[p])
            if deg == 0:
                continue
            if deg == 1:
                q = nbr_map[p][0]
                block = tuple(sorted((p, q)))
            else:
                # 3-node local neighborhood around branching/chain points
                nbrs = sorted(nbr_map[p], key=lambda n: n)
                block = tuple(sorted((p, nbrs[0], nbrs[-1])))
            if block not in seen_blocks:
                seen_blocks.add(block)
                blocks.append(list(block))

        if not blocks:
            return graph

        base_cost = self._compute_total_cost(graph)
        accepted = 0
        max_shift_m = 35.0
        shift_grid = [-max_shift_m, -max_shift_m / 2, 0.0, max_shift_m / 2, max_shift_m]

        for block in blocks:
            # Keep runtime bounded on large instances
            if len(pole_nodes) >= 60 and len(block) > 2:
                continue

            trial = graph.copy()
            original = {n: (trial.nodes[n]["lat"], trial.nodes[n]["lng"]) for n in block if n in trial}
            if len(original) != len(block):
                continue

            ref_lat = float(np.mean([lat for lat, _ in original.values()]))
            m_per_deg_lon = 111111.0 * np.cos(np.radians(ref_lat))
            if abs(m_per_deg_lon) < 1e-6:
                m_per_deg_lon = 1e-6

            best_local_cost = base_cost
            best_assign = None

            # Shared translation search (block move together), then edge constraints prune.
            for dn in shift_grid:
                for de in shift_grid:
                    dlat = dn / 111111.0
                    dlon = de / m_per_deg_lon

                    for n in block:
                        lat0, lon0 = original[n]
                        trial.nodes[n]["lat"] = float(lat0 + dlat)
                        trial.nodes[n]["lng"] = float(lon0 + dlon)

                    invalid = False
                    for n in block:
                        self._recompute_edges_for_node(trial, n)
                        if not self._all_edges_valid(trial, n):
                            invalid = True
                            break
                    if invalid:
                        continue

                    cost = self._compute_total_cost(trial)
                    if cost < best_local_cost - 1e-3:
                        best_local_cost = cost
                        best_assign = {n: (trial.nodes[n]["lat"], trial.nodes[n]["lng"]) for n in block}

            if best_assign is not None:
                for n, (lat, lon) in best_assign.items():
                    graph.nodes[n]["lat"] = float(lat)
                    graph.nodes[n]["lng"] = float(lon)
                base_cost = best_local_cost
                accepted += 1

        if self.request.debug >= 1:
            print(f"  _pole_block_coordinate_pass: accepted {accepted}/{len(blocks)} block moves")
        if self.request.debug >= 2 and accepted > 0:
            self._plot_current_graph(graph, title="After block-coordinate pole pass")

        return graph
