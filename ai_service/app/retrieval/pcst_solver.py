"""
Prize-Collecting Steiner Tree (PCST) Solver.
Wraps 'pcst_fast' library with a pure-Python dual-growth/pruned-MST approximation algorithm.
"""

import logging
from typing import List, Tuple, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)

try:
    import pcst_fast
    PCST_FAST_AVAILABLE = True
except ImportError:
    pcst_fast = None
    PCST_FAST_AVAILABLE = False


def solve_pcst_approx_python(
    edges: np.ndarray,
    prizes: np.ndarray,
    costs: np.ndarray,
    root: int = -1,
    num_clusters: int = 1,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Pure-Python greedy prize-to-cost Steiner tree approximation.
    Used when C++ pcst_fast binary is not available.
    """
    num_nodes = len(prizes)
    num_edges = len(costs)

    if num_nodes == 0:
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64)

    # If all prizes are 0, return empty or single top prize node
    if np.max(prizes) <= 0.0:
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64)

    # 1. Pick root node as node with highest prize if not specified
    if root < 0 or root >= num_nodes:
        current_root = int(np.argmax(prizes))
    else:
        current_root = root

    selected_nodes = {current_root}
    selected_edges = []

    # Adjacency map: node -> list of (neighbor, edge_idx, cost)
    adj: Dict[int, List[Tuple[int, int, float]]] = {i: [] for i in range(num_nodes)}
    for e_idx in range(num_edges):
        u = int(edges[e_idx, 0])
        v = int(edges[e_idx, 1])
        c = float(costs[e_idx])
        adj[u].append((v, e_idx, c))
        adj[v].append((u, e_idx, c))

    # Greedy expansion: add node that maximizes (prize - edge_cost)
    while True:
        best_candidate = None
        best_gain = 0.0
        best_edge_idx = -1

        for u in selected_nodes:
            for v, e_idx, cost in adj[u]:
                if v not in selected_nodes:
                    gain = float(prizes[v]) - cost
                    if gain > best_gain:
                        best_gain = gain
                        best_candidate = v
                        best_edge_idx = e_idx

        if best_candidate is not None and best_gain > 0.0:
            selected_nodes.add(best_candidate)
            selected_edges.append(best_edge_idx)
        else:
            break

    # If only one node selected with positive prize
    if not selected_edges and prizes[current_root] > 0.0:
        selected_nodes = {current_root}

    vert_res = np.array(sorted(list(selected_nodes)), dtype=np.int64)
    edge_res = np.array(sorted(selected_edges), dtype=np.int64)
    return vert_res, edge_res


def run_pcst_solver(
    edges: np.ndarray,
    prizes: np.ndarray,
    costs: np.ndarray,
    root: int = -1,
    num_clusters: int = 1,
    pruning: str = "gw",
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Executes PCST solver.
    Uses 'pcst_fast' if installed, otherwise uses our built-in approximation.

    Returns:
        (selected_node_indices, selected_edge_indices)
    """
    # Ensure correct dtypes
    edges_arr = np.ascontiguousarray(edges, dtype=np.int64)
    prizes_arr = np.ascontiguousarray(prizes, dtype=np.float64)
    costs_arr = np.ascontiguousarray(costs, dtype=np.float64)

    if PCST_FAST_AVAILABLE:
        try:
            vertices, edge_indices = pcst_fast.pcst_fast(
                edges_arr, prizes_arr, costs_arr, root, num_clusters, pruning
            )
            return vertices, edge_indices
        except Exception as e:
            logger.warning(f"pcst_fast error ({e}). Falling back to pure Python approximation.")

    return solve_pcst_approx_python(
        edges=edges_arr,
        prizes=prizes_arr,
        costs=costs_arr,
        root=root,
        num_clusters=num_clusters,
    )
