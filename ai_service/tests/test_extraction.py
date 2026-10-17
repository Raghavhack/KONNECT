"""
Tests for GraphRAG Entity & Relationship Extraction Wrapper.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.extraction.models import ExtractedEntity, ExtractedRelationship, GraphDelta
from app.extraction.graphrag_extractor import GraphRAGIncrementalExtractor
from app.preprocessing.chunker import Chunk
from app.llm.client import LLMClient


def test_extraction_models():
    ent = ExtractedEntity(
        id="ent_1",
        name="KONNECT",
        type="SYSTEM",
        description="Core knowledge platform.",
        importance_score=1.0,
    )
    assert ent.name == "KONNECT"

    rel = ExtractedRelationship(
        id="rel_1",
        source_name="KONNECT",
        target_name="ROLAND",
        relation_type="USES",
        weight=0.9,
    )
    assert rel.relation_type == "USES"


def test_graphrag_extractor_fallback_and_delta():
    llm = LLMClient(provider="openai")
    extractor = GraphRAGIncrementalExtractor(llm_client=llm)

    chunk = Chunk(
        chunk_id="chk_1",
        document_id="doc_1",
        chunk_index=0,
        text="FastAPI runs alongside gRPC servicer. PyTorch Geometric handles graph neural networks.",
        start_char=0,
        end_char=80,
        token_count=12,
        detected_entities=["FastAPI", "gRPC", "PyTorch Geometric"],
    )

    entities, relationships = extractor.extract_from_chunk(chunk)
    assert len(entities) >= 2

    # Compute delta against empty graph
    delta = extractor.compute_graph_delta(
        document_id="doc_1",
        existing_entity_names=["FastAPI"],
        extracted_entities=entities,
        extracted_relationships=relationships,
    )

    assert isinstance(delta, GraphDelta)
    assert len(delta.affected_entity_names) > 0
    # FastAPI was existing, so it should be categorized as updated
    assert any(e.name == "FastAPI" for e in delta.updated_entities)


def test_llm_client_strict_mode(monkeypatch):
    """Test that BENCH_STRICT_LLM=1 causes LLMClient to raise instead of simulating."""
    # Strict mode enabled
    monkeypatch.setenv("BENCH_STRICT_LLM", "1")
    strict_llm = LLMClient(provider="openai", openai_api_key=None)
    assert strict_llm.strict is True
    with pytest.raises(RuntimeError, match="LLM unavailable; refusing to simulate in benchmark mode"):
        strict_llm.generate("Hello world")

    # Non-strict mode
    monkeypatch.setenv("BENCH_STRICT_LLM", "0")
    lenient_llm = LLMClient(provider="openai", openai_api_key=None)
    assert lenient_llm.strict is False
    assert lenient_llm.simulated_calls == 0
    resp = lenient_llm.generate("Hello world")
    assert lenient_llm.simulated_calls == 1
    assert isinstance(resp, str)


def test_graphrag_extractor_strict_mode(monkeypatch):
    """Test that BENCH_STRICT_LLM=1 causes extractor to raise instead of falling back."""
    monkeypatch.setenv("BENCH_STRICT_LLM", "1")
    strict_llm = LLMClient(provider="openai", openai_api_key=None)
    extractor = GraphRAGIncrementalExtractor(llm_client=strict_llm)

    chunk = Chunk(
        chunk_id="chk_2",
        document_id="doc_2",
        chunk_index=0,
        text="A test chunk for strict mode evaluation.",
        start_char=0,
        end_char=40,
        token_count=8,
        detected_entities=["Aarav", "KONNECT"],
    )

    with pytest.raises(RuntimeError):
        extractor.extract_from_chunk(chunk)

    # Lenient mode
    monkeypatch.setenv("BENCH_STRICT_LLM", "0")
    lenient_llm = LLMClient(provider="openai", openai_api_key=None)
    extractor_lenient = GraphRAGIncrementalExtractor(llm_client=lenient_llm)
    assert extractor_lenient.fallback_count == 0
    # Provide an invalid mock generator that causes an exception
    class FailingLLM:
        def generate(self, *args, **kwargs):
            raise ConnectionError("Simulated network drop")
    extractor_failing = GraphRAGIncrementalExtractor(llm_client=FailingLLM())
    ents, rels = extractor_failing.extract_from_chunk(chunk)
    assert extractor_failing.fallback_count == 1
    assert len(ents) > 0


def test_bootstrap_index_logger():
    """Verify scripts/bootstrap_index.py imports cleanly and defines logger."""
    import scripts.bootstrap_index as bi
    assert hasattr(bi, "logger")
    assert bi.logger.name == "bootstrap"
