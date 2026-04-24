from typing import Tuple, List

import networkx as nx
import numpy as np
import scipy.sparse as sp
from joblib import Parallel, delayed
from matplotlib import pyplot as plt
from scipy.sparse.csgraph import minimum_spanning_tree


from .candidate_generation import CandidateGeneration
from ..utils.models import *
from ..utils.registry import register_solver


@register_solver
class GreedyIterSteinerSolver(CandidateGeneration):
    """
    Solver implementation using a greedy approach for refining the Minimum Spanning Tree (MST)
    based on Steiner points.

    This class provides mechanisms for solving tree optimization problems using Steiner
    points, by identifying and adding projection, cluster center, and Fermat point
    candidates.

    Attributes:
         None
    """

    def __init__(self, request: SolverRequest):
        super().__init__(request)
        self._delaunay_cache = None  # scipy.spatial.Delaunay object
        self._cached_coords = None  # the coords used to build the cache
        self._kdtree_cache = None  # will hold the KDTree object
        self._cached_kd_coords = None  # copy of coords used to build it

    def generate_candidates(self,
                            coords,
                            cur_edges,
                            fermat_candidates,
                            terminal_cluster_centers,
                            added_candidates,
                            num_per_edge=2):
        """
        Generates a pool of candidate points for network optimization based on various methods.

        This method synthesizes several types of candidates, including Fermat points, adaptive Fermat
        points, collinear points, and projection candidates. The method also filters candidates based
        on constraints such as bounding boxes of terminal nodes and removes already added candidates.

        Parameters:
            coords (list): A list of [latitude, longitude] coordinates representing existing points.
            cur_edges (list): A list of current edges represented by indices of the coordinates.
            terminal_cluster_centers (numpy.ndarray): Array of cluster centers derived from terminal nodes.
            added_candidates (list): A list of candidates already added, each as a [latitude, longitude] pair.
            num_per_edge (int, optional): Number of candidates to generate per edge. Default is 2.

        Returns:
            numpy.ndarray: A 2D array where each row represents a generated candidate point as
                           [latitude, longitude].

        Raises:
            None
        """

        # remove candidates outside of terminal bounding box
        def mask_outside_terminal_bb(_coords, _cands):
            if len(_cands) > 0:
                coords_bb = self.compute_bounding_box(_coords)
                lat_mask = (coords_bb['min_lat'] <= _cands[:, 0]) * (_cands[:, 0] <= coords_bb['max_lat'])
                lng_mask = (coords_bb['min_lng'] <= _cands[:, 1]) * (_cands[:, 1] <= coords_bb['max_lng'])
                mask = lat_mask * lng_mask
                _cands = _cands[mask]
            return _cands

        n_terminals = len(self._terminal_indices) + 1  # +1 for source
        pole_indices = list(range(n_terminals, len(coords)))
        terminal_indices = list(range(n_terminals))

        adaptive_fermat = self.generate_adaptive_fermat_candidates(
            np.array(coords),
            terminal_indices,
            pole_indices
        )

        projection_candidates = np.empty((0, 2))
        collinear_candidates = np.empty((0, 2))

        # if cur_edges is not None:
        #     collinear_candidates = self.generate_collinear_candidates(np.array(coords),
        #                                                               cur_edges,
        #                                                               num_per_edge=num_per_edge)

        # projection_candidates = self.generate_projection_candidates(
        #     np.array(coords),
        #     cur_edges,
        #     terminal_indices=self._terminal_indices,
        #     max_dist_to_line=40.0,
        #     min_dist_to_existing=5.0
        # )

        # === 2. Store ALL candidates in a dictionary (raw, before any masking) ===
        candidate_dict = {
            'Fermat Candidates': fermat_candidates,
            'Adaptive Fermat Candidates': adaptive_fermat,
            # 'Collinear Candidates': collinear_candidates,
            # 'Projection Candidates': projection_candidates,
            'Cluster Candidates': terminal_cluster_centers,
        }

        # === 4. Build final candidate pool by concatenating only the sets we actually use ===
        to_concat = [
            candidate_dict['Fermat Candidates'],
            candidate_dict['Adaptive Fermat Candidates'],
            # masked_dict['Collinear Candidates'],
            candidate_dict['Cluster Candidates'],
            # masked_dict['Projection Candidates'],
        ]

        if any(len(arr) > 0 for arr in to_concat):
            candidates = np.concatenate([arr for arr in to_concat if len(arr) > 0])
        else:
            candidates = np.empty((0, 2), dtype=float)

        # -------------- FILTER CANDIDATES --------------
        n_terminals = len(self._terminal_indices) + 1  # +1 for source
        pole_indices = list(range(n_terminals, len(coords)))
        terminal_indices_for_filter = self._terminal_indices  # real homes only

        candidates = self.filter_candidates(
            candidates=candidates,
            current_coords=np.array(coords),
            added_candidates=np.array(added_candidates),
            pole_indices=pole_indices,
            terminal_indices=terminal_indices_for_filter
        )

        # === 5. Debug plot using the dictionary (loop instead of 5 separate scatters) ===
        if self.request.debug >= 1 and len(candidates) > 0:
            fig, ax = plt.subplots(figsize=(10, 8))
            ax.set_title("Generated Candidates")
            ax.set_xlabel("Longitude")
            ax.set_ylabel("Latitude")
            ax.set_aspect('equal')

            # Loop through the dictionary — one scatter per candidate type
            for label, cands in candidate_dict.items():  # using raw (pre-mask) just like original
                if len(cands) > 0:
                    ax.scatter(cands[:, 1], cands[:, 0], s=100, marker='o', label=label)

            ax.scatter(coords[:, 1], coords[:, 0], c='black', s=100, marker='o', label='Existing Points')
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3)
            plt.show()

        return candidates

    def _fast_scipy_rollout_eval(self, coords: np.ndarray) -> float:
        """
        Evaluates the cost of a network rollout using a fast implementation relying on
        SciPy's minimum spanning tree (MST) computation.

        This method computes the total cost of the network rollout, including the
        wire cost, pole cost, and penalties for exceeding length constraints. It uses
        optimized, vectorized operations for calculating costs and constraints, and
        employs the MST algorithm to minimize the overall cost. Pruning is then applied
        to remove redundant dead-end poles.

        Parameters:
        coords: numpy.ndarray
            A 2D array representing geographic coordinates (latitude and longitude)
            of network nodes.

        Returns:
        float
            The total cost of the network rollout, considering wire costs, pole costs,
            and penalties.

        Raises:
        None
        """
        n = len(coords)
        source_idx = self._source_idx
        terminals = self._terminal_indices
        poles = [i for i in range(n) if i != source_idx and i not in terminals]

        # 1. Fast Distance Matrix
        dist = self.haversine_vec(coords, coords)

        # 2. Extract Constraints & Costs
        low_cost = self.request.costs.lowVoltageCostPerMeter
        pole_cost = self.request.costs.poleCost
        max_pole_pole = self.request.lengthConstraints.low.poleToPoleMaxLength
        max_pole_term = self.request.lengthConstraints.low.poleToTerminalMaxLength
        MAX_PENALTY = 10000.0  # From your base class

        # 3. Vectorized Edge Weight Calculations
        wire_cost = dist * low_cost

        # Trunk Cost (Pole-Pole, Source-Pole)
        extra_poles_trunk = np.maximum(0, np.ceil(dist / max_pole_pole) - 1)
        excess_trunk = np.maximum(0, dist - max_pole_pole)
        trunk_cost = wire_cost + (extra_poles_trunk * pole_cost) + (excess_trunk * MAX_PENALTY)

        # Terminal Drop Cost (Pole-Terminal, Source-Terminal)
        dist_adj = np.maximum(0, dist - max_pole_term)
        extra_poles_term = np.maximum(0, np.ceil(dist_adj / max_pole_pole) - 1)
        excess_term = np.maximum(0, dist - max_pole_term)
        term_cost = wire_cost + (extra_poles_term * pole_cost) + (excess_term * MAX_PENALTY)

        # 4. Assemble Adjacency Matrix (0 means no edge in SciPy MST)
        adj = np.zeros((n, n), dtype=float)

        # Source <-> Poles
        if poles:
            adj[source_idx, poles] = trunk_cost[source_idx, poles]
            adj[poles, source_idx] = trunk_cost[poles, source_idx]

        # Pole <-> Pole
        if len(poles) > 1:
            p_grid = np.ix_(poles, poles)
            adj[p_grid] = trunk_cost[p_grid]

        # Source/Pole <-> Terminals
        valid_sources = [source_idx] + poles
        if valid_sources and terminals:
            st_grid = np.ix_(valid_sources, terminals)
            ts_grid = np.ix_(terminals, valid_sources)
            adj[st_grid] = term_cost[st_grid]
            adj[ts_grid] = term_cost[ts_grid]

        # Remove very short invalid edges and self-loops
        adj[dist < 0.1] = 0.0
        np.fill_diagonal(adj, 0.0)

        # 5. Compute MST using SciPy's C-backend
        csr_adj = sp.csr_matrix(adj)
        mst = minimum_spanning_tree(csr_adj)

        # 6. Fast Pruning of Dead-End Poles
        # Convert upper-triangular MST to full symmetric matrix to get true degrees
        mst_dense = mst.toarray()
        undirected_mst = mst_dense + mst_dense.T

        # Count non-zero edges for each node
        degrees = np.count_nonzero(undirected_mst, axis=1)

        pruned_nodes = set()
        removed = True
        while removed:
            removed = False
            for p in poles:
                if p not in pruned_nodes and degrees[p] == 1:
                    pruned_nodes.add(p)
                    # Find the single neighbor and sever the connection
                    neighbors = np.nonzero(undirected_mst[p])[0]
                    if len(neighbors) > 0:
                        neighbor = neighbors[0]
                        undirected_mst[p, neighbor] = 0.0
                        undirected_mst[neighbor, p] = 0.0
                        degrees[p] = 0
                        degrees[neighbor] -= 1
                    removed = True

        # 7. Final Cost Calculation
        # undirected_mst contains symmetric edge weights, so sum / 2 is the exact total
        total_wire_and_extra_pole_cost = np.sum(undirected_mst) / 2.0
        num_active_poles = len(poles) - len(pruned_nodes)

        return total_wire_and_extra_pole_cost + (num_active_poles * pole_cost)

    def _evaluate_rollout(self, current_coords, candidate, depth=2):
        """
        Evaluates the rollout cost for a candidate location in relation to current coordinates.

        This method performs a multi-level look-ahead to determine the best cost achievable by
        adding a candidate location to the current set of coordinates. The evaluation is completed
        using a recursive approach, iterating up to the given depth. The process includes generating
        and testing proximity candidates at each level to improve the overall cost. The method
        returns the best cost achieved at the end of the evaluation.

        Parameters:
            current_coords (np.ndarray): A 2D array representing the current coordinates.
            candidate (np.ndarray): A 1D array representing the candidate coordinate to evaluate.
            depth (int, optional): The number of look-ahead levels to evaluate. Defaults to 2.

        Returns:
            float: The best achievable cost after evaluating the candidate and performing look-ahead
            up to the specified depth.
        """
        # First level: add the primary candidate
        temp_coords = np.vstack([current_coords, candidate])

        # Evaluate primary candidate cost
        best_future_cost = self._fast_scipy_rollout_eval(temp_coords)

        # Look-ahead (second level and beyond)
        for d in range(depth):
            look_ahead_cands = self.generate_proximity_fermat_candidates(temp_coords, max_candidates=8)

            if len(look_ahead_cands) == 0:
                break

            best_step_cand = None
            for fc in look_ahead_cands:
                # Add the future candidate to the temporary test stack
                test_coords = np.vstack([temp_coords, fc])

                # Lightning-fast evaluation
                cost = self._fast_scipy_rollout_eval(test_coords)

                if cost < best_future_cost:
                    best_future_cost = cost
                    best_step_cand = fc

            # If a future step improves the score, commit it to the local temporary stack and dig deeper
            if best_step_cand is not None:
                temp_coords = np.vstack([temp_coords, best_step_cand])
            else:
                break

        return best_future_cost

    def _distances_from_new_point(self, current_coords: np.ndarray, new_point: np.ndarray) -> np.ndarray:
        """
        Calculates the distances from a new point to a series of current coordinates using the Haversine formula.

        This method computes the pairwise distances between a new point and a collection of current coordinates,
        leveraging the vectorized implementation of the Haversine formula.

        Args:
            current_coords (np.ndarray): A 2D array of shape (n, 2) where each row represents the latitude and
                longitude of a point in radians.
            new_point (np.ndarray): A 1D array-like object of shape (2,) representing the latitude and longitude
                of a single point in radians.

        Returns:
            np.ndarray: A flattened 1D array of shape (n,) containing the calculated distances from the new point
            to each point in the `current_coords` array.
        """
        new_point = np.array(new_point).reshape(1, 2)  # shape (1, 2)
        return self.haversine_vec(new_point, current_coords).flatten()

    def _build_directed_graph_with_new_point(
            self,
            nodes,
            base_dist_matrix: np.ndarray,
            cand_dists: np.ndarray,
            new_point_idx: int
    ) -> nx.DiGraph:
        """
        Constructs a directed graph (DiGraph) with a new node added to represent a new point,
        alongside existing nodes and their relationships as defined by distances and parameters.

        This function integrates the new point into the graph, updates edge weights and
        attributes, and maintains relationships between different node types (source, poles,
        and terminals). It calculates the appropriate weights for edges based on distance
        and voltage levels.

        Parameters:
        nodes : list
            A list of node objects where each node defines attributes such as index, name,
            type, latitude, and longitude.
        base_dist_matrix : np.ndarray
            A 2D array representing the base distance matrix between existing nodes.
        cand_dists : np.ndarray
            A 1D array representing candidate distances from the new point to all nodes.
        new_point_idx : int
            The index of the newly added point in the nodes list.

        Returns:
        nx.DiGraph
            A directed graph representing the updated relationships and attributes of nodes,
            including the newly integrated point.
        """
        DG = nx.DiGraph()

        source_idx = self._source_idx

        # Add all nodes with attributes
        for node in nodes:
            DG.add_node(node.index,
                        name=node.name,
                        type=node.type,
                        lat=node.lat,
                        lng=node.lng)

        pole_indices = [i for i, node in enumerate(nodes) if node.type == "pole"]
        terminal_indices = [i for i, node in enumerate(nodes) if node.type == "terminal"]

        # 1. Source → all poles (including the new one)
        for p in pole_indices:
            if p == new_point_idx:
                d = cand_dists[source_idx]
            else:
                d = base_dist_matrix[source_idx, p]

            if 0.1 < d < 1e6:  # safety upper bound
                w = self.calc_edge_weight(d)
                DG.add_edge(source_idx, p, weight=w, length=d, voltage=self.request.voltageLevel)

        # 2. Pole ↔ Pole (bidirectional)
        for i in range(len(pole_indices)):
            for j in range(i + 1, len(pole_indices)):
                p1 = pole_indices[i]
                p2 = pole_indices[j]

                if p1 == new_point_idx:
                    d = cand_dists[p2]
                elif p2 == new_point_idx:
                    d = cand_dists[p1]
                else:
                    d = base_dist_matrix[p1, p2]

                if 0.1 < d < 1e6:
                    w = self.calc_edge_weight(d)
                    DG.add_edge(p1, p2, weight=w, length=d, voltage=self.request.voltageLevel)
                    DG.add_edge(p2, p1, weight=w, length=d, voltage=self.request.voltageLevel)

        # 3. Poles → Terminals (service drops)
        for p in pole_indices:
            for h in terminal_indices:
                if p == new_point_idx:
                    d = cand_dists[h]
                else:
                    d = base_dist_matrix[p, h]

                if 0.1 < d < 1e6:
                    w = self.calc_edge_weight(d, to_terminal=True)
                    DG.add_edge(p, h, weight=w, length=d, voltage=self.request.voltageLevel)

        # 4. Source → Terminals (unchanged, can use base matrix)
        for h in terminal_indices:
            d = base_dist_matrix[source_idx, h]
            if 0.1 < d < 1e6:
                w = self.calc_edge_weight(d, to_terminal=True)
                DG.add_edge(source_idx, h, weight=w, length=d, voltage=self.request.voltageLevel)

        return DG

    def _evaluate_candidate_fast(self, cand, current_coords, current_names, dist_matrix):
        """
        Fast path for evaluating one candidate.
        Uses the optimized builder. Falls back only if something goes wrong.
        """
        try:
            cand_dists = self._distances_from_new_point(current_coords, cand)
            trial_names = current_names + ['pole']
            trial_nodes = self._build_nodes(current_coords, [cand], trial_names)

            DG = self._build_directed_graph_with_new_point(
                trial_nodes, dist_matrix, cand_dists, new_point_idx=len(current_coords)
            )

            arbo_graph = self._minimum_spanning_arborescence_w_attrs(DG)
            pruned = self.prune_dead_end_pole_branches(arbo_graph)
            cost = self._compute_total_cost(pruned)

            return {
                "cost": cost,
                "cand": cand.copy(),
                "graph": pruned,
                "nodes": trial_nodes,
                "success": True
            }

        except Exception as e:
            if self.request.debug >= 1:
                print(f"Fast evaluation failed for candidate: {e}. Falling back to full method.")

            # Fallback to the slower full method
            trial_nodes = self._build_nodes(current_coords, [cand], current_names + ['pole'])
            DG = self.build_directed_graph_for_arborescence(trial_nodes)
            arbo_graph = self._minimum_spanning_arborescence_w_attrs(DG)
            pruned = self.prune_dead_end_pole_branches(arbo_graph)
            cost = self._compute_total_cost(pruned)

            return {
                "cost": cost,
                "cand": cand.copy(),
                "graph": pruned,
                "nodes": trial_nodes,
                "success": False
            }

    def _solve(self) -> nx.DiGraph:
        """
        Solves the optimization problem of constructing the minimum spanning arborescence with additional candidate nodes
        from an initial set of nodes and edges. The algorithm iteratively improves upon the solution by adding and pruning
        nodes efficiently to minimize total weight.

        Args:
            input_tuple (Tuple): A tuple containing the following parameters:
                - nodes (Iterable): Initial nodes of the graph.
                - coords (np.ndarray): Coordinates of the nodes.
                - source_idx (int): Index of the source node in the graph.
                - terminal_indices (List[int]): Indices of the terminal nodes.
                - names (List[str]): List of node names corresponding to `coords`.
                - solver (np.ndarray): Cost matrix used for the spanning arborescence calculation.

        Returns:
            Tuple[nx.DiGraph, List[Node], np.ndarray]: A tuple containing:
                - Directed graph representing the optimized spanning arborescence.
                - List of Node objects based on the optimized graph.
                - Numpy array of the final coordinate set including additional nodes.

        """

        # Initial state tracking
        current_coords = np.array(self._coords)
        current_names = list(self._names)
        added_candidates = np.empty((0, 2), dtype=float)

        # Constants for Beam Search and Rollout
        BEAM_WIDTH = 5  # Evaluate top 3 immediate candidates deeper
        ROLLOUT_DEPTH = 3  # Look ahead 1 step beyond the current choice
        MAX_STAGNATION = 3
        IMPROVEMENT_THRESHOLD = 0.05  # Minimum meters to keep iterating

        iteration = 0
        stagnation_counter = 0
        cur_total_weight = np.inf

        # Persist the best state found
        best_pruned_graph = None
        cur_edges = None

        # 1. Initial Cluster Center Generation
        # terminal_cluster_centers = self.kmeans_generate_cluster_center_candidates(current_coords, n_init=5)
        terminal_cluster_centers = self.dbscan_generate_cluster_center_candidates(current_coords, eps_meters=30,
                                                                                  min_samples=2)
        fermat_candidates = self.generate_proximity_fermat_candidates(np.array(current_coords),
                                                                      max_distance=40,
                                                                      max_candidates=50)

        fermat_candidates = self.filter_candidates(fermat_candidates, current_coords, [], [], [])
        terminal_cluster_centers = self.filter_candidates(terminal_cluster_centers, current_coords, [], [], [])

        while True:
            iteration += 1
            if self.request.debug >= 1:
                print(f"\n--- Iteration {iteration} (Stagnation: {stagnation_counter}/{MAX_STAGNATION}) ---")

            # 2. Generate candidates
            candidates = self.generate_candidates(
                current_coords,
                cur_edges,
                fermat_candidates,
                terminal_cluster_centers,
                added_candidates,
                num_per_edge=3
            )

            if len(candidates) == 0:
                if self.request.debug: print("No more candidates to evaluate.")
                break

            # --- STEP 1: IMMEDIATE FILTERING (The "Beam" Selection) ---
            def eval_wrapper(cand):
                # Instantly evaluate the candidate purely in NumPy/SciPy
                temp_coords = np.vstack([current_coords, cand])
                cost = self._fast_scipy_rollout_eval(temp_coords)
                return {"cost": cost, "cand": cand}

            if self.request.debug >= 1:
                print(f"Evaluating {len(candidates)} candidates sequentially using SciPy...")

            # Small problems → serial is faster
            if len(candidates) > 0:
                if self.request.debug >= 1:
                    print(f"Evaluating {len(candidates)} candidates serially")
                immediate_results = [eval_wrapper(c) for c in candidates]
            else:
                n_jobs = -1
                if self.request.debug >= 1:
                    print(f"Evaluating {len(candidates)} candidates in parallel (n_jobs={n_jobs}, threading)")

                immediate_results = Parallel(
                    n_jobs=n_jobs,
                    backend="loky",
                    verbose=self.request.debug
                )(delayed(eval_wrapper)(cand) for cand in candidates)

            # Sort by cost and take the top candidates for the Beam
            immediate_results.sort(key=lambda x: x["cost"])
            beam = immediate_results[:BEAM_WIDTH]

            # --- STEP 2: ROLLOUT EVALUATION ---
            best_rollout_score = np.inf
            winner = None

            for item in beam:
                # Look into the future for this specific candidate using SciPy
                rollout_score = self._evaluate_rollout(
                    current_coords, item["cand"], depth=ROLLOUT_DEPTH
                )

                if rollout_score < best_rollout_score:
                    best_rollout_score = rollout_score
                    winner = item

            # --- STEP 3: SELECTION & STAGNATION CHECK ---
            if winner is None: break

            improvement = cur_total_weight - winner["cost"]

            if self.request.debug >= 1:
                print(f"Rollout Score: {rollout_score:.2f} (Improvement: {improvement:.2f})")

            if improvement < IMPROVEMENT_THRESHOLD:
                stagnation_counter += 1
                if self.request.debug: print(f"Stagnating: improvement of {improvement:.4f}m is below threshold.")
            else:
                stagnation_counter = 0

            if stagnation_counter >= MAX_STAGNATION:
                if self.request.debug: print("Stopping due to stagnation.")
                break

            # --- STEP 4: COMMIT WINNER ---
            if self.request.debug >= 1:
                print(
                    f"Winner selected via Rollout: Imm Cost: {winner['cost']:.2f} | Rollout Potential: {best_rollout_score:.2f}")

            # 1. Build the formal NetworkX graph ONLY for the chosen winner
            trial_names = current_names + ['pole']
            trial_nodes = self._build_nodes(current_coords, [winner["cand"]], trial_names)

            DG = self.build_directed_graph_for_arborescence(trial_nodes)
            arbo_graph = self._minimum_spanning_arborescence_w_attrs(DG)
            best_pruned_graph = self.prune_dead_end_pole_branches(arbo_graph)

            if iteration % 3:
                best_pruned_graph = self._drop_redundant_poles(best_pruned_graph)

            # 2. Update state tracking variables
            added_candidates = np.vstack([added_candidates, winner["cand"]])
            current_coords = np.vstack([current_coords, winner["cand"]])
            current_names = trial_names

            # 3. Invalidate caches
            self._kdtree_cache = None
            self._cached_kd_coords = None
            self._dist_matrix = None
            self._cached_coords_hash = None

            cur_total_weight = winner["cost"]
            cur_edges = list(best_pruned_graph.edges())

            # Visualization for debugging
            if self.request.debug >= 1:
                self._plot_current_graph(best_pruned_graph, added_points=[winner["cand"]],
                                         title=f"Iteration {iteration} (Δ {improvement:+.2f} m)")

        # Finally Gradient Decent each pole placement to ensure not local optimization is left on the table
        final_graph = self._post_solver_local_opt(best_pruned_graph)

        return final_graph
