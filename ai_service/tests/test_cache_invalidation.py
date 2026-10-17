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


def test_stale_fact_removal_on_edit():
    from app.graph.neo4j_client import Neo4jClient
    from app.graph.store import Neo4jGraphStore
    from app.extraction.models import ExtractedEntity, ExtractedRelationship

    client = Neo4jClient()
    store = Neo4jGraphStore(client=client)

    # Ingest Document 1 containing Entity_A and Entity_B
    e_a = ExtractedEntity(id="e1", name="Alpha", type="CONCEPT", description="First entity", importance_score=1.0)
    e_b = ExtractedEntity(id="e2", name="Beta", type="CONCEPT", description="Second entity", importance_score=1.0)
    store.upsert_entities([e_a, e_b], document_id="doc_1")
    store.upsert_relationships([
        ExtractedRelationship(id="r1", source_name="Alpha", target_name="Beta", relation_type="CONNECTS", weight=1.0)
    ])

    # Ingest Document 2 also mentioning Entity_A
    store.upsert_entities([e_a], document_id="doc_2")

    # Verify both entities exist
    nodes, _ = store.get_k_hop_neighborhood(seed_entity_names=["Alpha"], k=1)
    names = [n["name"] for n in nodes]
    assert "Alpha" in names
    assert "Beta" in names

    # Now edit Document 1: Fact "Beta" is removed, replaced by "Gamma"
    # Partial invalidation removes Document 1's previous contributions:
    del_res = store.delete_document_contributions("doc_1")
    assert "Beta" in del_res["deleted_entities"]  # Beta was orphaned!
    assert "Alpha" not in del_res["deleted_entities"]  # Alpha is preserved because doc_2 still mentions it!

    # Re-verify graph after deletion
    nodes_after, edges_after = store.get_k_hop_neighborhood(seed_entity_names=["Alpha"], k=1)
    names_after = [n["name"] for n in nodes_after]
    assert "Alpha" in names_after
    assert "Beta" not in names_after  # Stale fact successfully removed!
    assert len(edges_after) == 0  # Edge connected to Beta was also pruned!

