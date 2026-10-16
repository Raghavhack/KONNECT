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


def test_in_memory_retrieval_returns_nodes_when_neo4j_disconnected():
    dim = 64
    embedder = SentenceTransformerEmbedder(embedding_dim=dim)
    client = Neo4jClient(embedding_dim=dim)
    assert client.is_connected is False  # In-memory fallback mode
    store = Neo4jGraphStore(client=client)

    # Ingest entities into fallback graph
    q_vec = embedder.embed_text("Quantum Computing Algorithms")
    client.in_memory_fallback.upsert_node(
        label="Entity",
        name="Quantum Computing",
        properties={
            "id": "e1",
            "type": "TECHNOLOGY",
            "description": "High speed quantum processor.",
            "importance_score": 1.0,
            "embedding": q_vec.tolist(),
            "gnn_embedding": q_vec.tolist(),
        },
    )
    client.in_memory_fallback.upsert_node(
        label="Entity",
        name="Qubits",
        properties={
            "id": "e2",
            "type": "CONCEPT",
            "description": "Basic unit of quantum information.",
            "importance_score": 0.9,
            "embedding": q_vec.tolist(),
            "gnn_embedding": q_vec.tolist(),
        },
    )
    client.in_memory_fallback.upsert_edge(
        src="Quantum Computing",
        tgt="Qubits",
        relation_type="UTILIZES",
        properties={"weight": 1.0, "description": "Utilizes qubits"},
    )

    retriever = PCSTSubgraphRetriever(embedder=embedder, graph_store=store, prize_threshold=0.2)
    subgraph = retriever.retrieve_subgraph("Quantum Computing Algorithms")

    # In-memory fallback must NOT return empty results
    assert len(subgraph["nodes"]) > 0
    node_names = [n["name"] for n in subgraph["nodes"]]
    assert "Quantum Computing" in node_names
    assert subgraph["total_prize"] > 0.0


def test_arm_d_ablation_pcst_without_gnn():
    dim = 64
    embedder = SentenceTransformerEmbedder(embedding_dim=dim)
    client = Neo4jClient(embedding_dim=dim)
    store = Neo4jGraphStore(client=client)

    q_vec = np.ones(dim, dtype=np.float32) / np.sqrt(dim)
    orthogonal_vec = np.zeros(dim, dtype=np.float32)
    orthogonal_vec[0] = 1.0

    # Node where text embedding is aligned with query, but gnn_embedding is orthogonal
    nodes = [
        {
            "name": "HybridNode",
            "embedding": q_vec.tolist(),
            "gnn_embedding": orthogonal_vec.tolist(),
            "importance_score": 1.0,
        }
    ]

    retriever = PCSTSubgraphRetriever(embedder=embedder, graph_store=store)

    # Arm D (use_gnn=False): evaluates text embedding -> high prize
    prizes_arm_d = retriever.assign_node_prizes_from_scratch(q_vec, nodes, threshold=0.5, use_gnn=False)
    assert prizes_arm_d[0] > 0.5

    # Full GNN (use_gnn=True): evaluates gnn_embedding -> lower prize
    prizes_gnn = retriever.assign_node_prizes_from_scratch(q_vec, nodes, threshold=0.5, use_gnn=True)
    assert prizes_arm_d[0] > prizes_gnn[0]

