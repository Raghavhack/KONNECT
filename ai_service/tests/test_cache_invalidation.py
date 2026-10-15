"""
Tests for Redis Semantic Cache and Graph-Node Driven Cache Invalidation (Section 5).
"""

import pytest
import sys
import os
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.cache.semantic_cache import SemanticCache


def test_semantic_cache_lookup_and_invalidation():
    cache = SemanticCache(similarity_threshold=0.90)

    q_vec = np.ones(64, dtype=np.float32) / np.sqrt(64)

    # 1. Store a query answer citing entities ["Entity_X", "Entity_Y"]
    cache.store(
        query="What is the architecture of Entity_X?",
        query_embedding=q_vec,
        answer="Entity_X utilizes Entity_Y for distributed coordination.",
        citations=[{"entity_name": "Entity_X"}, {"entity_name": "Entity_Y"}],
        subgraph={"nodes": [{"name": "Entity_X"}, {"name": "Entity_Y"}]},
        cited_entity_names=["Entity_X", "Entity_Y"],
    )

    # 2. Lookup identical query vector -> Must HIT
    hit = cache.lookup(query_embedding=q_vec, similarity_threshold=0.90)
    assert hit is not None
    assert "Entity_X" in hit["answer"]

    # 3. Lookup orthogonal vector -> Must MISS
    ortho_vec = np.zeros(64, dtype=np.float32)
    ortho_vec[0] = 1.0
    miss = cache.lookup(query_embedding=ortho_vec, similarity_threshold=0.90)
    assert miss is None

    # 4. Invalidate cache citing "Entity_X" (incremental update occurred!)
    evicted = cache.invalidate_for_entities(["Entity_X"])
    assert len(evicted) >= 1

    # 5. Lookup again with original query vector -> Must MISS because it was evicted!
    evicted_lookup = cache.lookup(query_embedding=q_vec, similarity_threshold=0.90)
    assert evicted_lookup is None
