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


def test_end_to_end_pipeline():
    dim = 64
    processor = TextProcessor()
    chunker = SemanticChunker(processor=processor, chunk_size=40, chunk_overlap=10)
    embedder = SentenceTransformerEmbedder(embedding_dim=dim)
    llm = LLMClient(provider="openai")
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

    # 3. Latency benchmark for tunable k
    bench = neighborhood_mgr.benchmark_comparison(num_total_nodes=1000, num_total_edges=5000, k=2)
    assert bench["k_hops"] == 2
    assert bench["speedup_factor"] >= 1.0
