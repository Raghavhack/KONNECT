"""
Tests for Prize-Collecting Steiner Tree (PCST) Retrieval and Prize Assignment.
"""

import pytest
import sys
import os
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.retrieval.pcst_solver import run_pcst_solver, solve_pcst_approx_python
from app.retrieval.pcst_retriever import PCSTSubgraphRetriever
from app.retrieval.context_builder import ContextBuilder
from app.embeddings.embedder import SentenceTransformerEmbedder
from app.graph.neo4j_client import Neo4jClient
from app.graph.store import Neo4jGraphStore


def test_pcst_solver_approx():
    # 3 nodes: 0, 1, 2
    # Prizes: 0->1.0, 1->2.0, 2->0.0
    # Edges: (0, 1) cost 0.2, (1, 2) cost 1.5
    edges = np.array([[0, 1], [1, 2]], dtype=np.int64)
    prizes = np.array([1.0, 2.0, 0.0], dtype=np.float64)
    costs = np.array([0.2, 1.5], dtype=np.float64)

    verts, sel_edges = solve_pcst_approx_python(edges, prizes, costs)
    # Node 1 and 0 should be selected; node 2 should be pruned (0 prize, 1.5 cost)
    assert 1 in verts
    assert 0 in verts
    assert 2 not in verts
    assert 0 in sel_edges  # edge (0, 1)


def test_pcst_prize_assignment_from_scratch():
    embedder = SentenceTransformerEmbedder(embedding_dim=64)
    client = Neo4jClient()
    store = Neo4jGraphStore(client=client)
    retriever = PCSTSubgraphRetriever(embedder=embedder, graph_store=store)

    q_vec = np.ones(64, dtype=np.float32) / np.sqrt(64)

    # Candidate nodes: one aligned with query, one orthogonal
    aligned_emb = q_vec.tolist()
    ortho_vec = np.zeros(64, dtype=np.float32)
    ortho_vec[0] = 1.0  # partial
    ortho_emb = ortho_vec.tolist()

    nodes = [
        {"name": "HighlyRelevantEntity", "embedding": aligned_emb, "importance_score": 1.0},
        {"name": "IrrelevantEntity", "embedding": ortho_emb, "importance_score": 1.0},
    ]

    prizes = retriever.assign_node_prizes_from_scratch(q_vec, nodes, threshold=0.5)
    assert prizes[0] > 0.0  # highly aligned entity gets prize
    assert prizes[0] > prizes[1]


def test_context_builder():
    subgraph = {
        "nodes": [
            {"name": "Apple", "type": "ORGANIZATION", "description": "Consumer electronics giant."},
            {"name": "M4 Chip", "type": "TECHNOLOGY", "description": "High performance silicon processor."},
        ],
        "edges": [
            {"src": "Apple", "tgt": "M4 Chip", "type": "DEVELOPED", "weight": 1.0, "description": "Developed by Apple"}
        ],
        "prizes": {"Apple": 0.95, "M4 Chip": 0.88},
    }

    context = ContextBuilder.build_llm_context(subgraph)
    assert "Apple" in context
    assert "M4 Chip" in context
    assert "DEVELOPED" in context
