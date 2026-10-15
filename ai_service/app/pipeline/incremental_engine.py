"""
Incremental Knowledge Graph Engine.
Coordinates: Document Edit -> spaCy Preprocessing -> GraphRAG Extraction ->
Neo4j Store -> k-Hop ROLAND GRU Re-embedding -> Leiden Community Update ->
Redis Cache Invalidation -> Real-time Streaming Deltas.
"""

import time
import logging
from typing import List, Dict, Any, Tuple, Optional, Callable

from ..preprocessing.text_processor import TextProcessor
from ..preprocessing.chunker import SemanticChunker
from ..embeddings.embedder import SentenceTransformerEmbedder
from ..extraction.graphrag_extractor import GraphRAGIncrementalExtractor
from ..extraction.models import ExtractedEntity, ExtractedRelationship, GraphDelta
from ..graph.store import Neo4jGraphStore
from ..graph.community import CommunityDetector
from ..gnn.neighborhood import BoundedNeighborhoodManager
from ..cache.semantic_cache import SemanticCache

logger = logging.getLogger(__name__)


class IncrementalEngine:
    """
    Main orchestration engine executing the incremental intelligence pipeline.
    Owns the full edit -> updated graph path.
    """

    def __init__(
        self,
        text_processor: TextProcessor,
        chunker: SemanticChunker,
        embedder: SentenceTransformerEmbedder,
        extractor: GraphRAGIncrementalExtractor,
        graph_store: Neo4jGraphStore,
        neighborhood_manager: BoundedNeighborhoodManager,
        community_detector: CommunityDetector,
        semantic_cache: SemanticCache,
        stream_subscribers: Optional[List[Callable[[Dict[str, Any]], None]]] = None,
    ):
        self.text_processor = text_processor
        self.chunker = chunker
        self.embedder = embedder
        self.extractor = extractor
        self.graph_store = graph_store
        self.neighborhood_manager = neighborhood_manager
        self.community_detector = community_detector
        self.semantic_cache = semantic_cache
        self.subscribers = stream_subscribers if stream_subscribers is not None else []

    def subscribe_stream(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Registers a listener for real-time graph delta events."""
        self.subscribers.append(callback)

    def _broadcast_delta_event(self, event: Dict[str, Any]) -> None:
        """Emits graph delta events to all registered stream subscribers."""
        for cb in self.subscribers:
            try:
                cb(event)
            except Exception as e:
                logger.debug(f"Error notifying delta subscriber: {e}")

    def process_document_update(
        self,
        document_id: str,
        title: str,
        content: str,
        k_hops: int = 2,
        trigger_leiden: bool = True,
        invalidate_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes the end-to-end incremental update pipeline:
        1. spaCy Preprocessing & Chunking
        2. GraphRAG entity & relation extraction
        3. Upsert to Neo4j knowledge store
        4. Bounded k-hop neighborhood retrieval
        5. ROLAND GRU dynamic re-embedding
        6. Neo4j vector embedding update
        7. Local Leiden community update
        8. Redis semantic cache invalidation
        9. Delta event broadcast
        """
        t_start = time.perf_counter()

        # Step 1: Preprocess & Chunk
        t0 = time.perf_counter()
        chunks = self.chunker.chunk_document(document_id=document_id, text=content)
        prep_time_ms = (time.perf_counter() - t0) * 1000.0

        # Step 2: GraphRAG Extraction
        t0 = time.perf_counter()
        entities, relationships = self.extractor.extract_from_document(
            document_id=document_id, title=title, chunks=chunks
        )
        extract_time_ms = (time.perf_counter() - t0) * 1000.0

        # Step 3: Upsert to Neo4j
        self.graph_store.upsert_document_and_chunks(document_id, title, chunks)
        self.graph_store.upsert_entities(entities, document_id=document_id)
        self.graph_store.upsert_relationships(relationships)

        affected_names = [e.name for e in entities]
        for r in relationships:
            affected_names.append(r.source_name)
            affected_names.append(r.target_name)
        affected_names = list(set(affected_names))

        # Step 4 & 5: Bounded k-hop ROLAND GRU Re-embedding
        t0 = time.perf_counter()
        neighborhood_nodes, neighborhood_edges = self.graph_store.get_k_hop_neighborhood(
            seed_entity_names=affected_names, k=k_hops
        )

        updated_embeddings, gnn_metrics = self.neighborhood_manager.run_bounded_update(
            seed_entity_names=affected_names,
            neighborhood_nodes=neighborhood_nodes,
            neighborhood_edges=neighborhood_edges,
            k=k_hops,
        )
        roland_time_ms = (time.perf_counter() - t0) * 1000.0

        # Step 6: Commit new node representations to Neo4j
        self.graph_store.update_node_embeddings(updated_embeddings)

        # Step 7: Scoped Leiden Community Detection
        communities_updated = []
        if trigger_leiden:
            communities_updated = self.community_detector.detect_communities_incremental(
                affected_entity_names=affected_names,
                neighborhood_nodes=neighborhood_nodes,
                neighborhood_edges=neighborhood_edges,
            )

        # Step 8: Incremental Redis Cache Invalidation (Section 5 requirement)
        invalidated_keys = []
        if invalidate_cache and affected_names:
            invalidated_keys = self.semantic_cache.invalidate_for_entities(affected_names)

        total_time_ms = (time.perf_counter() - t_start) * 1000.0

        # Step 9: Broadcast streaming deltas to JS backend / frontend
        for ent in entities:
            self._broadcast_delta_event({
                "action": "ADDED_OR_UPDATED_NODE",
                "document_id": document_id,
                "entity": ent.model_dump(),
                "timestamp": time.time(),
            })
        for rel in relationships:
            self._broadcast_delta_event({
                "action": "ADDED_OR_UPDATED_EDGE",
                "document_id": document_id,
                "relationship": rel.model_dump(),
                "timestamp": time.time(),
            })

        return {
            "success": True,
            "document_id": document_id,
            "new_entities_count": len(entities),
            "new_relationships_count": len(relationships),
            "affected_nodes_count": len(affected_names),
            "updated_embeddings_count": len(updated_embeddings),
            "communities_updated_count": len(communities_updated),
            "invalidated_cache_keys": invalidated_keys,
            "k_hops_applied": k_hops,
            "preprocessing_time_ms": round(prep_time_ms, 2),
            "extraction_time_ms": round(extract_time_ms, 2),
            "roland_gru_time_ms": round(roland_time_ms, 2),
            "total_time_ms": round(total_time_ms, 2),
        }
