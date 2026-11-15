from typing import List, Union, Literal

import networkx as nx
import numpy as np
from matplotlib import pyplot as plt
from matplotlib import collections as mc

from ..utils.models import Node, get_node_coord_tuple


class GraphMixin:
    """
    Mixin class for graph-related operations.

    This class provides utility methods for constructing and modifying graph
    representations, including graph plotting, node reindexing, and converting
    input data to graph structures. These methods are intended to facilitate
    operations on graphs that represent nodes with geographical coordinates and
    various node types.

    Attributes:
        None
    """


    @staticmethod
    def _plot_current_graph(graph, added_points=None, title="Current tree after candidate addition", filename=None):
        """Plot graph nodes and edges, optionally highlighting candidate points.

        Args:
            graph: Graph containing node types and geographic coordinates.
            added_points: Optional latitude/longitude coordinates to highlight.
            title: Plot title.
            filename: Optional path to save the plot; otherwise display it.
        """
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.set_title(title)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_aspect('equal')

        # 1. Safely map indices to their true coordinates
        coord_dict = {}
        source_coords = []
        term_coords = []
        pole_coords = []
        for idx, node_data in graph.nodes(data=True):
            coord_dict[idx] = (node_data['lat'], node_data['lng'])
            if node_data['type'] == "source":
                source_coords.append(coord_dict[idx])
            elif node_data['type'] == "terminal":
                term_coords.append(coord_dict[idx])
            elif node_data['type'] == "pole":
                pole_coords.append(coord_dict[idx])

        # Plot Source
        if source_coords:
            sc = np.array(source_coords)
            ax.scatter(sc[:, 1], sc[:, 0], c='blue', s=120, marker='s', label='Source')

        # Plot Terminals
        if term_coords:
            tc = np.array(term_coords)
            ax.scatter(tc[:, 1], tc[:, 0], c='red', s=80, marker='o', label='Terminals')

        # Plot Existing poles
        if pole_coords:
            pc = np.array(pole_coords)
            ax.scatter(pc[:, 1], pc[:, 0], c='black', s=60, marker='^', label='Poles')

        # Highlight newly added candidate
        if added_points is not None:
            added_points = np.array(added_points)
            if len(added_points) > 0:
                ax.scatter(added_points[:, 1], added_points[:, 0], c='orange', s=200, marker='*', edgecolor='black',
                           linewidth=1.5,
                           label='Newly added pole')

        # Plot edges
        edge_lines = []
        for u, v in graph.edges():
            if u in coord_dict and v in coord_dict:
                pt_u = [coord_dict[u][1], coord_dict[u][0]]  # [lng, lat]
                pt_v = [coord_dict[v][1], coord_dict[v][0]]
                edge_lines.append([pt_u, pt_v])

        if edge_lines:
            lc = mc.LineCollection(edge_lines, colors='green', linewidths=1.5, alpha=0.7)
            ax.add_collection(lc)

        # ─── NEW: Display node indices on the graph ─────────────────────────
        for idx, (lat, lon) in coord_dict.items():
            node_type = graph.nodes[idx].get('type', 'unknown')
            if node_type == 'source':
                color = 'blue'
                offset = (0.00003, 0.00003)
                fontsize = 9
            elif node_type == 'terminal':
                color = 'darkred'
                offset = (0.00003, 0.00003)
                fontsize = 8
            else:  # pole
                color = 'black'
                offset = (0.00003, 0.00003)
                fontsize = 8

            ax.text(
                lon + offset[0],
                lat + offset[1],
                str(idx),
                fontsize=fontsize,
                color=color,
                ha='left',
                va='bottom',
                bbox=dict(boxstyle="round,pad=0.1", facecolor="white", alpha=0.75, edgecolor='none'),
                zorder=10
            )

        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        if filename:
            plt.savefig(filename, dpi=150, bbox_inches='tight')
            plt.close(fig)
            print(f"Saved plot: {filename}")
        else:
            plt.show()
            plt.close(fig)


    # ─── Helpful common utilities (can be used or overridden) ────────────────
    def reindex_nodes(self, nodes):
        """Return copies of nodes with contiguous indices starting at zero.

        Args:
            nodes: Nodes to reindex.

        Returns:
            list[Node]: Copies of the nodes with updated indices.
        """
        new_nodes = []
        for i, node in enumerate(nodes):
            new_nodes.append(Node(
                index=i,
                lat=node.lat,
                lng=node.lng,
                name=node.name,
                type=node.type,
            ))

        return new_nodes

    def _build_nodes(self, coords, candidates, names):
        """Build node objects from coordinates, names, and candidate poles.

        Args:
            coords: Array of original latitude/longitude coordinates.
            candidates: Latitude/longitude coordinates of candidate poles.
            names: Names corresponding to the original nodes.

        Returns:
            list[Node]: Nodes with indices, coordinates, types, and names.
        """
        nodes = []
        n_orig = len(coords)

        for i in range(n_orig):
            if i == self._source_idx:
                t: Literal['source', 'pole', 'terminal'] = "source"
            else:
                if "pole" in names[i].lower():
                    t = "pole"
                else:
                    t = "terminal"
            nodes.append(Node(
                index=i,
                lat=float(coords[i, 0]),
                lng=float(coords[i, 1]),
                type=t,
                name=names[i],
            ))

        offset = n_orig
        for j, (lat, lon) in enumerate(candidates, start=offset):
            nodes.append(Node(
                index=j,
                lat=float(lat),
                lng=float(lon),
                type="pole",
            ))

        return nodes

    def build_graph_from_nodes(self, nodes, edges=None,
                               include_terminals=False, directed=False) -> Union[nx.DiGraph, nx.Graph]:
        """Build a directed or undirected graph from nodes and optional edges.

        Args:
            nodes (List[Node]): Nodes to include in the graph.
            edges (Optional[List[Edge]]): Optional explicit edges; when omitted,
                eligible edges are generated from distances.
            include_terminals (bool): Whether automatic generation includes
                terminal-connected edges.
            directed (bool): Whether to create a directed graph.

        Returns:
            Union[nx.DiGraph, nx.Graph]: Graph with node and edge attributes.
        """
        G = nx.DiGraph() if directed else nx.Graph()
        nodes = self.reindex_nodes(nodes)
        for node in nodes:
            G.add_node(node.index)
            G.nodes[node.index]["name"] = node.name
            G.nodes[node.index]["type"] = node.type
            G.nodes[node.index]["lat"] = node.lat
            G.nodes[node.index]["lng"] = node.lng

        coords = np.array([get_node_coord_tuple(n) for n in nodes])

        dist_matrix = self.compute_distance_matrix(coords)
        if edges is None:
            for i in G.nodes:
                i_type = G.nodes[i]["type"]
                for j in G.nodes:
                    if i == j:
                        continue
                    j_type = G.nodes[j]["type"]

                    if ((i_type == "source" and j_type == "pole") or
                            (i_type == "pole" and j_type == "pole") or
                            (i_type == "pole" and j_type == "terminal") or
                            (i_type == "source" and j_type == "terminal") or
                            include_terminals):
                        G.add_edge(i, j)
                        d = dist_matrix[i, j]
                        weight = self.calc_edge_weight(d, to_terminal=(j in self._terminal_indices))
                        G.edges[i, j]["weight"] = weight
                        G.edges[i, j]["length"] = d
                        G.edges[i, j]["voltage"] = self.request.voltageLevel

        else:
            for edge in edges:
                start, end = edge.start, edge.end
                i, j = start.index, end.index
                G.add_edge(i, j)
                G.edges[i, j]["weight"] = self.calc_edge_weight(edge.lengthMeters,
                                                                to_terminal=(j in self._terminal_indices))
                G.edges[i, j]["length"] = edge.lengthMeters
                G.edges[i, j]["voltage"] = self.request.voltageLevel

        return G

    def build_directed_graph_for_arborescence(self, nodes) -> nx.DiGraph:
        """Build a directed candidate graph for an arborescence.

        Args:
            nodes (list): Source, pole, and terminal nodes to connect.

        Returns:
            nx.DiGraph: Directed graph with distance-based edge weights.
        """

        DG = nx.DiGraph()

        pole_indices = [n.index for n in nodes if n.type == "pole"]
        terminal_indices = [n.index for n in nodes if n.type == "terminal"]
        source_idx = nodes[self._source_idx].index

        all_points = np.array([get_node_coord_tuple(n) for n in nodes])

        if hasattr(self, '_get_distance_matrix'):
            dist_matrix = self._get_distance_matrix(all_points)
        else:
            dist_matrix = self.compute_distance_matrix(all_points)

        for n in nodes:
            DG.add_node(n.index, name=n.name, type=n.type, lat=n.lat, lng=n.lng)

        # 1: source → poles (main trunk)
        for p in pole_indices:
            d = dist_matrix[source_idx, p]
            if 0.1 < d:
                w = self.calc_edge_weight(d)
                DG.add_edge(source_idx, p, weight=w, length=d, voltage=self.request.voltageLevel)

        # 2: Bidirectional pole ↔ pole (undirected spans)
        for i in range(len(pole_indices)):
            for j in range(i + 1, len(pole_indices)):
                p1, p2 = pole_indices[i], pole_indices[j]
                d = dist_matrix[p1, p2]
                w = self.calc_edge_weight(d)
                if 0.1 < d:
                    DG.add_edge(p1, p2, weight=w, length=d, voltage=self.request.voltageLevel)
                    DG.add_edge(p2, p1, weight=w, length=d, voltage=self.request.voltageLevel)

        # 3: poles → terminals (service drops)
        for p in pole_indices:
            for h in terminal_indices:
                d = dist_matrix[p, h]
                if 0.1 < d:
                    w = self.calc_edge_weight(d, to_terminal=True)
                    DG.add_edge(p, h, weight=w, length=d, voltage=self.request.voltageLevel)

        # 4. Source to Terminals
        for h in terminal_indices:
            d = dist_matrix[source_idx, h]
            if 0.1 < d:
                w = self.calc_edge_weight(d, to_terminal=True)
                DG.add_edge(source_idx, h, weight=w, length=d, voltage=self.request.voltageLevel)

        return DG

    def _recompute_all_edges(self, graph: Union[nx.Graph, nx.DiGraph]):
        """Recalculate lengths and weights for every graph edge.

        Args:
            graph (Union[nx.Graph, nx.DiGraph]): Graph whose nodes have geographic
                coordinates and whose edges receive updated lengths and weights.
        """
        for u, v, data in list(graph.edges(data=True)):
            lat1, lon1 = graph.nodes[u]['lat'], graph.nodes[u]['lng']
            lat2, lon2 = graph.nodes[v]['lat'], graph.nodes[v]['lng']
            length = self.haversine_meters(lat1, lon1, lat2, lon2)
            data['length'] = length

            # Same logic you already use elsewhere
            to_terminal = (graph.nodes[v].get('type') == 'terminal' or
                           graph.nodes[u].get('type') == 'terminal')
            data['weight'] = self.calc_edge_weight(length, to_terminal=to_terminal)

    def _distance_from_source(self, graph: Union[nx.Graph, nx.DiGraph], node_idx: int) -> float:
        """Return the shortest distance from the configured source to a node.

        Args:
            graph (Union[nx.Graph, nx.DiGraph]): Graph used for path calculation.
            node_idx (int): Destination node index.

        Returns:
            float: Weighted distance, unweighted path length as fallback, or
                ``999999.0`` when no path can be found.
        """
        try:
            dists = nx.single_source_dijkstra_path_length(graph, self._source_idx, weight='length')
            return float(dists.get(node_idx, 999999.0))
        except (nx.NetworkXError, KeyError):
            # fallback for graphs without length attributes
            try:
                return float(nx.shortest_path_length(graph, self._source_idx, node_idx))
            except:
                return 999999.0

    @staticmethod
    def _minimum_spanning_arborescence_w_attrs(DG, attr="weight", default=1e18, preserve_attrs=True):
        """Compute a minimum spanning arborescence with optional node attributes.

        Args:
            DG (networkx.DiGraph): Directed graph to process.
            attr (str): Edge attribute used as the weight.
            default (float): Weight assigned when the attribute is missing.
            preserve_attrs (bool): Whether to copy input node attributes.

        Returns:
            networkx.DiGraph: Minimum spanning arborescence.
        """

        arbo_graph = nx.minimum_spanning_arborescence(DG, attr=attr, default=default, preserve_attrs=preserve_attrs)

        if preserve_attrs:
            for n, d in DG.nodes(data=True):
                if n in arbo_graph:
                    arbo_graph.nodes[n].update(d)  # or arbo_graph.nodes[n] = d.copy()

        return arbo_graph

    def compute_distance_matrix(self, points: np.ndarray) -> np.ndarray:
        """Compute pairwise Haversine distances between points.

        Args:
            points (np.ndarray): Latitude/longitude coordinate array.

        Returns:
            np.ndarray: Matrix of pairwise distances in meters.
        """
        return self.haversine_vec(points, points)


    def print_min_max_edge_len(self, graph):
        """Format the maximum and minimum edge lengths in a graph.

        Args:
            graph: Graph whose edges may contain a ``length`` attribute.

        Returns:
            str: Formatted maximum and minimum edge lengths in meters.
        """
        edge_lengths = [e[2]['length'] for e in graph.edges(data=True)]
        max_len = max(edge_lengths) if edge_lengths else 0.0
        min_len = min(edge_lengths) if edge_lengths else 0.0

        return f"Max edge length: {max_len}m | Min edge length: {min_len}m"
