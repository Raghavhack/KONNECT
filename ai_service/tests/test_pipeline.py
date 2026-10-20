"""
Integration Tests for End-to-End Incremental & Query Pipelines.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.preprocessing.text_processor import TextProcessor
from app.preprocessing.chunker import SemanticChunker
from app.embeddings.embedder import SentenceTransformerEmbedder
from app.llm.client import LLMClient
from app.llm.generator import AnswerGenerator
from app.extraction.graphrag_extractor import GraphRAGIncrementalExtractor
from app.graph.neo4j_client import Neo4jClient
from app.graph.store import Neo4jGraphStore
from app.graph.community import CommunityDetector
from app.gnn.roland_gru import RolandHierarchicalGRU
from app.gnn.neighborhood import BoundedNeighborhoodManager
from app.cache.semantic_cache import SemanticCache
from app.retrieval.pcst_retriever import PCSTSubgraphRetriever
from app.pipeline.incremental_engine import IncrementalEngine
from app.pipeline.query_engine import QueryEngine


def test_end_to_end_pipeline(llm):
    dim = 64
    processor = TextProcessor()
    chunker = SemanticChunker(processor=processor, chunk_size=40, chunk_overlap=10)
    embedder = SentenceTransformerEmbedder(embedding_dim=dim)
    extractor = GraphRAGIncrementalExtractor(llm_client=llm, embedder=embedder)

    neo4j_client = Neo4jClient(embedding_dim=dim)
    graph_store = Neo4jGraphStore(client=neo4j_client)
    community_detector = CommunityDetector(client=neo4j_client, llm_client=llm)

    roland = RolandHierarchicalGRU(in_dim=dim, hidden_dim=64, out_dim=dim, num_layers=2)
    neighborhood_mgr = BoundedNeighborhoodManager(roland_model=roland, default_k=2)

    cache = SemanticCache()
    pcst_retriever = PCSTSubgraphRetriever(embedder=embedder, graph_store=graph_store)
    answer_gen = AnswerGenerator(llm_client=llm)

    events_received = []

    def on_delta(evt):
        events_received.append(evt)

    inc_engine = IncrementalEngine(
        text_processor=processor,
        chunker=chunker,
        embedder=embedder,
        extractor=extractor,
        graph_store=graph_store,
        neighborhood_manager=neighborhood_mgr,
        community_detector=community_detector,
        semantic_cache=cache,
        stream_subscribers=[on_delta],
    )

    query_engine = QueryEngine(
        embedder=embedder,
        semantic_cache=cache,
        pcst_retriever=pcst_retriever,
        answer_generator=answer_gen,
    )

    # 1. Incremental update
    doc_content = (
        "KONNECT utilizes GraphRAG and ROLAND GRU. "
        "The ROLAND framework updates node states dynamically across temporal graph edits. "
        "PCST retrieval identifies prize-maximizing connected subgraphs."
    )
    res_update = inc_engine.process_document_update(
        document_id="doc_int_1",
        title="KONNECT Architecture Overview",
        content=doc_content,
        k_hops=2,
    )

    assert res_update["success"] is True
    assert res_update["affected_nodes_count"] > 0
    assert res_update["k_hops_applied"] == 2
    assert len(events_received) > 0

    # 2. Query answering
    res_query = query_engine.execute_query(
        query="What framework does KONNECT use for dynamic graph representation?"
    )

    assert res_query["answer"] is not None
    assert res_query["total_latency_ms"] >= 0.0


def test_k_hop_multi_hop_expansion():
    """Verifies that k-hop neighborhood query actually expands across hops and does not collapse to 1-hop."""
    client = Neo4jClient()
    store = Neo4jGraphStore(client=client)

    # Build a linear chain: N0 - N1 - N2 - N3 - N4
    for i in range(5):
        client.in_memory_fallback.upsert_node(
            label="Entity",
            name=f"Node_{i}",
            properties={"importance_score": 1.0, "embedding": [0.1] * 64},
        )
    for i in range(4):
        client.in_memory_fallback.upsert_edge(
            src=f"Node_{i}",
            tgt=f"Node_{i+1}",
            relation_type="LINKS_TO",
            properties={"weight": 1.0},
        )

    # Sweep over k from 1 to 3
    nodes_k1, _ = store.get_k_hop_neighborhood(seed_entity_names=["Node_0"], k=1)
    nodes_k2, _ = store.get_k_hop_neighborhood(seed_entity_names=["Node_0"], k=2)
    nodes_k3, _ = store.get_k_hop_neighborhood(seed_entity_names=["Node_0"], k=3)

    assert len(nodes_k1) == 2  # Node_0, Node_1
    assert len(nodes_k2) == 3  # Node_0, Node_1, Node_2
    assert len(nodes_k3) == 4  # Node_0, Node_1, Node_2, Node_3
    # Sweep over k is strictly increasing, proving it does NOT fall back to 1 hop!
    assert len(nodes_k1) < len(nodes_k2) < len(nodes_k3)


def test_main_app_pipeline_wiring():
    """Verifies that app.main correctly wires all components together into pipeline_container and FastAPI."""
    from app.main import initialize_pipeline, create_app
    from app.api.routes import pipeline_container

    container = initialize_pipeline()
    assert "incremental_engine" in container
    assert "query_engine" in container
    assert "neighborhood_manager" in container
    assert "graph_store" in container
    assert "roland_model" in container

    app = create_app()
    assert app.title == "KONNECT Intelligence Service"
    assert len(app.routes) > 0