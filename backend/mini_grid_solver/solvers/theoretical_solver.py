from typing import Union, List, Tuple

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.patches import Ellipse

from .candidate_generation import CandidateGeneration
from ..utils.models import Node, SolverRequest
from ..utils.registry import register_solver

METERS_PER_DEG_LAT = 111111.0


@register_solver
class TheoreticalBoundSteinerSolver(CandidateGeneration):
    """
    Implements the strictly bounded O(1) approximation algorithm for the BLT-STP.
    Modularized into distinct algorithmic phases mapping to the theoretical proof.
    """

    def __init__(self, request: SolverRequest):
        super().__init__(request)
        self._pole_cost_beta = request.params.get('poleCost', 1000.0) if hasattr(request, 'params') and request.params else 1000.0

    @staticmethod
    def get_input_params():
        return []

    def _plot_cluster_cover(
        self,
        term_coords: np.ndarray,
        disk_center_pole_coords: np.ndarray,
        R: float,
        title: str
    ) -> None:
        fig, ax = plt.subplots(figsize=(11, 9))
        ax.set_title(title)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_aspect("equal")

        ax.scatter(
            term_coords[:, 1],
            term_coords[:, 0],
            c="red",
            s=90,
            marker="o",
            edgecolors="darkred",
            linewidth=1,
            label=f"Terminals ({len(term_coords)})",
        )

        if len(disk_center_pole_coords) > 0:
            ax.scatter(
                disk_center_pole_coords[:, 1],
                disk_center_pole_coords[:, 0],
                c="blue",
                s=180,
                marker="*",
                edgecolors="black",
                linewidth=1.5,
                label=f"Disk Centers ({len(disk_center_pole_coords)})",
            )

            avg_lat = float(np.mean(term_coords[:, 0])) if len(term_coords) > 0 else 45.0
            meters_per_deg_lon = METERS_PER_DEG_LAT * np.cos(np.radians(avg_lat))
            r_lat_deg = R / METERS_PER_DEG_LAT
            r_lon_deg = R / meters_per_deg_lon

            for center in disk_center_pole_coords:
                ellipse = Ellipse(
                    xy=(center[1], center[0]),
                    width=2 * r_lon_deg,
                    height=2 * r_lat_deg,
                    fill=False,
                    color="blue",
                    alpha=0.25,
                    linewidth=2,
                    linestyle="--",
                )
                ax.add_patch(ellipse)

        ax.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.show()
        plt.close(fig)

    def _generate_greedy_clusters(self, coords: np.ndarray, term_indices: List[int], R: float) -> List[
        Tuple[np.ndarray, List[int]]]:
        """
        Step 1: Partition terminals into clusters bounded by beta and R.
        """
        remaining_term_indices = set(term_indices)
        disk_center_clusters = []

        # Offset to prevent zero-length edges dropping from the graph
        min_dist = max(self.get_min_pole_to_term(), 1.0)
        dlat = min_dist / 111111.0

        while remaining_term_indices:
            anchor_term_idx = remaining_term_indices.pop()
            anchor_term_coord = coords[anchor_term_idx]
            cluster_term_indices = [anchor_term_idx]

            if remaining_term_indices:
                other_term_indices = list(remaining_term_indices)
                other_term_coords = coords[other_term_indices]

                # Vectorized haversine distance array
                term_distances = self.haversine_vec(np.array([anchor_term_coord]), other_term_coords).flatten()
                sorted_indices = np.argsort(term_distances)

                cumulative_distance = 0.0

                for i in sorted_indices:
                    candidate_term_idx = other_term_indices[i]
                    candidate_distance = term_distances[i]

                    if cumulative_distance + candidate_distance > self._pole_cost_beta or candidate_distance > R:
                        break

                    cluster_term_indices.append(candidate_term_idx)
                    cumulative_distance += candidate_distance
                    remaining_term_indices.remove(candidate_term_idx)

            disk_center_pole_coord = np.array([anchor_term_coord[0] + dlat, anchor_term_coord[1]])
            disk_center_clusters.append((disk_center_pole_coord, cluster_term_indices))

            if self.request.debug >= 2:
                selected_centers = np.array([cluster[0] for cluster in disk_center_clusters], dtype=float)
                self._plot_cluster_cover(
                    term_coords=coords[term_indices],
                    disk_center_pole_coords=selected_centers,
                    R=R,
                    title=f"Theoretical Cluster Cover - Step {len(disk_center_clusters)}",
                )

        if self.request.debug >= 2:
            final_centers = np.array([cluster[0] for cluster in disk_center_clusters], dtype=float)
            self._plot_cluster_cover(
                term_coords=coords[term_indices],
                disk_center_pole_coords=final_centers,
                R=R,
                title=f"FINAL Theoretical Cluster Cover - {len(final_centers)} centers",
            )

        return disk_center_clusters

    def _build_star_graph(self,
                          disk_center_clusters: List[Tuple[np.ndarray, List[int]]],
                          coords: np.ndarray,
                          term_indices: List[int],
                          source_idx: int) -> Tuple[nx.DiGraph, List[int]]:
        """
        Step 3 Setup: Construct base nodes and add star edges from poles to terminals.
        """
        best_graph = nx.DiGraph()

        # Initialize source and terminals
        best_graph.add_node(source_idx, name=self._names[source_idx], type="source", lat=coords[source_idx][0],
                            lng=coords[source_idx][1])
        for t_idx in term_indices:
            best_graph.add_node(t_idx, name=self._names[t_idx], type="terminal", lat=coords[t_idx][0], lng=coords[t_idx][1])

        disk_center_pole_start_idx = max(best_graph.nodes) + 1 if best_graph.nodes else 0
        disk_center_pole_node_ids = []

        for i, (disk_center_pole_coord, cluster_term_indices) in enumerate(disk_center_clusters):
            disk_center_pole_node_id = disk_center_pole_start_idx + i
            disk_center_pole_node_ids.append(disk_center_pole_node_id)
            best_graph.add_node(
                disk_center_pole_node_id,
                name=f"DiskCenterPole {i + 1}",
                type="pole",
                lat=disk_center_pole_coord[0],
                lng=disk_center_pole_coord[1]
            )

            for term_idx in cluster_term_indices:
                dist = self.haversine_meters(
                    disk_center_pole_coord[0],
                    disk_center_pole_coord[1],
                    coords[term_idx][0],
                    coords[term_idx][1]
                )
                weight = self.calc_edge_weight(dist, to_terminal=True)
                best_graph.add_edge(
                    disk_center_pole_node_id,
                    term_idx,
                    weight=weight,
                    length=dist,
                    voltage=self.request.voltageLevel
                )

        return best_graph, disk_center_pole_node_ids

    def _connect_backbone(self, best_graph: nx.DiGraph, disk_center_pole_node_ids: List[int], coords: np.ndarray,
                          source_idx: int) -> nx.DiGraph:
        """
        Step 2 & 3 Execution: Find MST on poles + source, direct outward, and inject into main graph.
        """
        backbone_node_ids = [source_idx] + disk_center_pole_node_ids
        backbone_graph = nx.Graph()

        for node_id in backbone_node_ids:
            node_data = best_graph.nodes[node_id]
            backbone_graph.add_node(node_id, **node_data)

        # Build complete weighted graph over source + poles using original node IDs.
        for i in range(len(backbone_node_ids)):
            node_i = backbone_node_ids[i]
            lat_i = best_graph.nodes[node_i]["lat"]
            lng_i = best_graph.nodes[node_i]["lng"]
            for j in range(i + 1, len(backbone_node_ids)):
                node_j = backbone_node_ids[j]
                lat_j = best_graph.nodes[node_j]["lat"]
                lng_j = best_graph.nodes[node_j]["lng"]
                dist = self.haversine_meters(lat_i, lng_i, lat_j, lng_j)
                weight = self.calc_edge_weight(dist)
                backbone_graph.add_edge(
                    node_i,
                    node_j,
                    weight=weight,
                    length=dist,
                    voltage=self.request.voltageLevel,
                )

        backbone_mst = nx.minimum_spanning_tree(backbone_graph, weight='weight')

        # Force directed arborescence outward from source
        for u, v in nx.bfs_edges(backbone_mst, source=source_idx):
            edge_data = backbone_mst[u][v]
            best_graph.add_edge(u, v, **edge_data)

        return best_graph

    def _solve(self) -> Union[nx.Graph, nx.DiGraph]:
        """
        Main orchestration of the bounded algorithm.
        """
        coords = self._coords
        term_indices = self._terminal_indices
        source_idx = self._source_idx
        R = self.get_max_pole_to_term()

        # Step 1: Greedy Procedure
        if self.request.debug >= 1:
            print(f"Step 1: Cluster cover with R={R:.1f}m for {len(term_indices)} terminals")
        disk_center_clusters = self._generate_greedy_clusters(coords, term_indices, R)

        # Step 2 & 3: Topology Construction (Star Edges + Backbone)
        if self.request.debug >= 1:
            print("Step 2: Build star graph from cluster disk centers")
        best_graph, disk_center_pole_node_ids = self._build_star_graph(
            disk_center_clusters,
            coords,
            term_indices,
            source_idx
        )
        if self.request.debug >= 2:
            self._plot_current_graph(best_graph, title="Theoretical solver - star graph")

        if self.request.debug >= 1:
            print("Step 3: Connect backbone from source through disk centers")
        best_graph = self._connect_backbone(best_graph, disk_center_pole_node_ids, coords, source_idx)
        if self.request.debug >= 2:
            self._plot_current_graph(best_graph, title="Theoretical solver - star graph + backbone")

        # Step 4: Split long edges to satisfy R constraint
        if self.request.debug >= 1:
            print("Step 4: Split long edges with intermediate poles")
        final_graph = self.split_long_edges_w_poles(best_graph)

        if self.request.debug >= 1:
            n_poles = sum(1 for _, d in final_graph.nodes(data=True) if d.get('type') == 'pole')
            print(f"TheoreticalBoundSteinerSolver completed. Final pole count: {n_poles}")
            self._plot_current_graph(final_graph, title="Theoretical solver - final graph")

        return final_graph
