"""
Bounded k-Hop Neighborhood Re-Embedding Manager.
Core Latency Property: Limits the ROLAND GRU update pass strictly to nodes within
k hops of newly changed or added document entities.
"""

"""
Bounded k-hop re-embedding (the latency property the evaluation is built on).

Design (L = number of GNN layers, k = context radius around the changed entities):
  * An L-layer GNN gives a node an exact embedding only if its whole L-hop
    neighbourhood is present in the subgraph we feed it.
  * A node at hop-distance d from the seeds therefore has an exact embedding iff d + L <= k.
  * So we run the model on the k-hop subgraph but COMMIT (cache + return) only nodes
    with d <= k - L. Boundary nodes are used as context and never written back, so
    truncated neighbourhoods cannot pollute the state cache.
  * Nodes whose embedding genuinely changes are those within L hops of a seed, so
    k >= 2L re-embeds every truly affected node. k < L is clamped (seeds only) with a warning.
"""

import logging
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

import torch

from .roland_gru import RolandHierarchicalGRU

logger = logging.getLogger(__name__)


def hop_distances(seed_names: List[str], node_names: List[str], edges: List[Tuple[str, str]]) -> Dict[str, int]:
    """BFS hop distance from the nearest seed over an undirected edge list."""
    adj: Dict[str, List[str]] = {n: [] for n in node_names}
    for s, t in edges:
        if s in adj and t in adj:
            adj[s].append(t)
            adj[t].append(s)
    dist: Dict[str, int] = {}
    q = deque()
    for s in seed_names:
        if s in adj and s not in dist:
            dist[s] = 0
            q.append(s)
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


class BoundedNeighborhoodManager:
    def __init__(self, roland_model: RolandHierarchicalGRU, default_k: int = 4):
        self.model = roland_model
        self.default_k = default_k

    def run_bounded_update(
        self,
        seed_entity_names: List[str],
        neighborhood_nodes: List[Dict[str, Any]],
        neighborhood_edges: List[Dict[str, Any]],
        k: Optional[int] = None,
    ) -> Tuple[Dict[str, List[float]], Dict[str, Any]]:
        """
        Runs the ROLAND update on the induced k-hop subgraph.
        Returns ({entity_name: new_embedding} for committed nodes only, metrics).
        """
        k_hops = self.default_k if k is None else k
        t0 = time.perf_counter()
        L = self.model.num_layers

        # Nodes without a text embedding cannot be featurised: skip them, never invent features.
        nodes = [n for n in neighborhood_nodes if n.get("name") and n.get("embedding") is not None
                 and len(n["embedding"]) == self.model.in_dim]
        skipped = len(neighborhood_nodes) - len(nodes)
        if skipped:
            logger.warning("Skipped %d neighbourhood nodes with missing/misshapen text embeddings", skipped)
        if not nodes:
            return {}, {"processing_time_ms": 0.0, "affected_nodes": 0, "committed_nodes": 0, "k_hops": k_hops}

        names = [n["name"] for n in nodes]
        idx = {nm: i for i, nm in enumerate(names)}
        und_edges = [(e["src"], e["tgt"]) for e in neighborhood_edges if e.get("src") in idx and e.get("tgt") in idx]

        src, dst = [], []
        for s, t in und_edges:
            src += [idx[s], idx[t]]
            dst += [idx[t], idx[s]]
        edge_index = torch.tensor([src, dst], dtype=torch.long) if src else torch.empty((2, 0), dtype=torch.long)
        x = torch.tensor([n["embedding"] for n in nodes], dtype=torch.float32)

        # Which nodes have an exact L-layer embedding?
        commit_radius = k_hops - L
        if commit_radius < 0:
            logger.warning("k=%d < num_layers=%d: only seed nodes are committed; use k >= %d for exact updates",
                           k_hops, L, 2 * L)
            commit_radius = 0
        dist = hop_distances(seed_entity_names, names, und_edges)
        commit_mask = torch.tensor([dist.get(nm, 10**9) <= commit_radius for nm in names], dtype=torch.bool)

        self.model.eval()
        with torch.no_grad():
            out = self.model(x=x, edge_index=edge_index, node_ids=names, update_cache=True, commit_mask=commit_mask)

        updated = {nm: out[i].tolist() for i, nm in enumerate(names) if bool(commit_mask[i])}
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        metrics = {
            "processing_time_ms": round(elapsed_ms, 3),
            "affected_nodes": len(names),            # nodes the model ran on (context size)
            "committed_nodes": len(updated),         # nodes actually re-embedded and stored
            "edges_evaluated": edge_index.size(1),
            "k_hops": k_hops,
            "commit_radius": commit_radius,
            "seed_nodes_count": len(seed_entity_names),
        }
        logger.info("Bounded update: ran on %d nodes, committed %d, %.2f ms (k=%d)",
                    len(names), len(updated), elapsed_ms, k_hops)
        return updated, metrics