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


def test_graphrag_extractor_and_delta(llm):
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

    delta = extractor.compute_graph_delta(
        document_id="doc_1",
        existing_entity_names=["FastAPI"],
        extracted_entities=entities,
        extracted_relationships=relationships,
    )

    assert isinstance(delta, GraphDelta)
    assert len(delta.affected_entity_names) > 0
    assert any(e.name.lower() == "fastapi" for e in delta.updated_entities)


def test_llm_client_requires_provider_key_and_model():
    with pytest.raises(ValueError):
        LLMClient(provider="gemini", api_key=None, model="some-model")
    with pytest.raises(ValueError):
        LLMClient(provider="gemini", api_key="k", model="")
    with pytest.raises(ValueError):
        LLMClient(provider="nonsense", api_key="k", model="m")


def test_extractor_raises_when_llm_call_fails():
    """Real client with an invalid key: the real API rejects it and the error must propagate."""
    from app.config import settings
    bad = LLMClient(provider="gemini", api_key="invalid-key", model=settings.GEMINI_MODEL,
                    max_retries=1, base_delay=0.0)
    extractor = GraphRAGIncrementalExtractor(llm_client=bad)
    chunk = Chunk(chunk_id="c", document_id="d", chunk_index=0, text="FastAPI uses PyTorch.",
                  start_char=0, end_char=20, token_count=4, detected_entities=["FastAPI"])
    with pytest.raises(RuntimeError):
        extractor.extract_from_chunk(chunk)