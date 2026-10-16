"""
Prize-Collecting Steiner Tree (PCST) Subgraph Retriever.
From-Scratch Prize Assignment via Cosine Similarity Scoring.

Extracts the maximally relevant, minimally redundant connected subgraph answering a user query.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

from .pcst_solver import run_pcst_solver
from ..embeddings.embedder import SentenceTransformerEmbedder
from ..graph.store import Neo4jGraphStore
from ..extraction.models import ExtractedEntity, ExtractedRelationship

logger = logging.getLogger(__name__)


class PCSTSubgraphRetriever:
    """
    Retrieves connected subgraphs using Prize-Collecting Steiner Tree.
    Implements cosine similarity prize assignment from scratch.
    """

    def __init__(
        self,
        embedder: SentenceTransformerEmbedder,
        graph_store: Neo4jGraphStore,
        cost_weight: float = 0.20,
        prize_threshold: float = 0.35,
        max_subgraph_nodes: int = 25,
        use_gnn: bool = True,
    ):
        self.embedder = embedder
        self.graph_store = graph_store
        self.cost_weight = cost_weight
        self.prize_threshold = prize_threshold
        self.max_subgraph_nodes = max_subgraph_nodes
        self.use_gnn = use_gnn

    def assign_node_prizes_from_scratch(
        self,
        query_embedding: np.ndarray,
        nodes: List[Dict[str, Any]],
        threshold: float,
        use_gnn: bool = True,
    ) -> np.ndarray:
        """
        FROM-SCRATCH Prize Assignment Function.
        Computes cosine similarity between query vector and each node representation,
        scaling by node importance and thresholding.
        When use_gnn=True, utilizes the residual GNN embedding (or falls back to text embedding).
        When use_gnn=False, utilizes the text embedding (Arm D ablation).
        """
        N = len(nodes)
        prizes = np.zeros(N, dtype=np.float64)
        norm_q = np.linalg.norm(query_embedding) + 1e-9

        for i, node in enumerate(nodes):
            if use_gnn:
                emb = node.get("gnn_embedding") or node.get("embedding")
            else:
                emb = node.get("embedding")

            if emb is not None and len(emb) > 0:
                v = np.array(emb, dtype=np.float32)
                norm_v = np.linalg.norm(v) + 1e-9
                cosine_sim = float(np.dot(query_embedding, v) / (norm_q * norm_v))
            else:
                # Text-based fallback similarity
                cosine_sim = 0.1

            # Prize formula: normalized surplus above threshold
            if cosine_sim > threshold:
                normalized_score = (cosine_sim - threshold) / (1.0 - threshold + 1e-9)
                importance = float(node.get("importance_score", 1.0))
                prizes[i] = float(normalized_score * importance)
            else:
                prizes[i] = 0.0

        return prizes

    def assign_edge_costs(
        self,
        query_embedding: np.ndarray,
        edges: List[Dict[str, Any]],
        base_cost: float,
    ) -> np.ndarray:
        """
        Assigns costs to candidate edges.
        Edges with higher weight or semantic relevance incur lower costs.
        Guaranteed to be strictly positive (c > 0).
        """
        M = len(edges)
        costs = np.zeros(M, dtype=np.float64)

        for i, edge in enumerate(edges):
            weight = float(edge.get("weight", 1.0))
            # Lower cost for stronger relationships
            discount = min(0.6, 0.2 * weight)
            c = max(0.01, base_cost * (1.0 - discount))
            costs[i] = float(c)

        return costs

    def retrieve_subgraph(
        self,
        query: str,
        k_hop_seed_top_k: int = 10,
        cost_weight: Optional[float] = None,
        threshold: Optional[float] = None,
        use_gnn: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        End-to-end PCST retrieval:
        1. Embeds incoming query.
        2. Queries colocated Neo4j vector index for top seed candidates.
        3. Retrieves 2-hop neighborhood to form candidate graph G_c = (V_c, E_c).
        4. Assigns node prizes via cosine similarity scoring from scratch.
        5. Assigns positive edge costs.
        6. Solves PCST to extract connected, high-prize subgraph.
        """
        c_weight = cost_weight if cost_weight is not None else self.cost_weight
        th = threshold if threshold is not None else self.prize_threshold
        gnn_flag = use_gnn if use_gnn is not None else self.use_gnn

        # 1. Embed query
        q_emb = self.embedder.embed_text(query)

        # 2. Vector search in Neo4j to find top seed nodes
        vector_candidates = self.graph_store.search_vector_index(
            query_embedding=q_emb.tolist(), top_k=k_hop_seed_top_k, use_gnn=gnn_flag
        )
        seed_names = []
        for c in vector_candidates:
            name = c.get("name")
            if not name and isinstance(c.get("node"), dict):
                name = c["node"].get("name")
            if name:
                seed_names.append(name)

        if not seed_names:
            return {
                "nodes": [],
                "edges": [],
                "total_prize": 0.0,
                "total_cost": 0.0,
            }

        # 3. Retrieve k-hop candidate neighborhood (V_c, E_c)
        cand_nodes, cand_edges = self.graph_store.get_k_hop_neighborhood(
            seed_entity_names=seed_names, k=2
        )

        if not cand_nodes:
            cand_nodes = [c.get("node") if "node" in c and isinstance(c["node"], dict) else c for c in vector_candidates]
            cand_edges = []

        node_names = [n["name"] for n in cand_nodes if "name" in n]
        name_to_idx = {name: i for i, name in enumerate(node_names)}
        N = len(node_names)

        # 4. From-Scratch Prize Assignment
        prizes = self.assign_node_prizes_from_scratch(q_emb, cand_nodes, threshold=th, use_gnn=gnn_flag)

        # 5. Build edge array and cost assignment
        edge_pairs = []
        valid_edges = []
        for e in cand_edges:
            s = e.get("src")
            t = e.get("tgt")
            if s in name_to_idx and t in name_to_idx:
                edge_pairs.append([name_to_idx[s], name_to_idx[t]])
                valid_edges.append(e)

        if edge_pairs:
            edges_arr = np.array(edge_pairs, dtype=np.int64)
            costs = self.assign_edge_costs(q_emb, valid_edges, base_cost=c_weight)
        else:
            edges_arr = np.empty((0, 2), dtype=np.int64)
            costs = np.empty(0, dtype=np.float64)

        # 6. Solve PCST
        selected_node_indices, selected_edge_indices = run_pcst_solver(
            edges=edges_arr,
            prizes=prizes,
            costs=costs,
            root=-1,
            num_clusters=1,
            pruning="gw",
        )

        # Filter and cap max nodes
        selected_node_indices = selected_node_indices[: self.max_subgraph_nodes]

        retrieved_nodes = [cand_nodes[i] for i in selected_node_indices if i < N]
        retrieved_edges = [valid_edges[j] for j in selected_edge_indices if j < len(valid_edges)]

        total_prize = float(np.sum(prizes[selected_node_indices])) if len(selected_node_indices) > 0 else 0.0
        total_cost = float(np.sum(costs[selected_edge_indices])) if len(selected_edge_indices) > 0 else 0.0

        return {
            "nodes": retrieved_nodes,
            "edges": retrieved_edges,
            "total_prize": round(total_prize, 3),
            "total_cost": round(total_cost, 3),
            "prizes": {node_names[i]: float(prizes[i]) for i in selected_node_indices if i < N},
        }
