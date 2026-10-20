"""
gRPC Intelligence Servicer Implementation.
Fulfills the gRPC contract between the Node.js orchestration backend and Python intelligence layer.
"""

import time
import queue
import logging
from typing import Iterator

from .generated import intelligence_pb2 as pb2
from .generated import intelligence_pb2_grpc as pb2_grpc
from ..pipeline.incremental_engine import IncrementalEngine
from ..pipeline.query_engine import QueryEngine
from ..gnn.neighborhood import BoundedNeighborhoodManager

logger = logging.getLogger(__name__)


class IntelligenceServicer(pb2_grpc.IntelligenceServiceServicer):
    """
    Implements the gRPC IntelligenceService interface.
    Serves parsing, incremental graph updates, streaming deltas, PCST query answering,
    cache invalidation, and latency benchmarking.
    """

    def __init__(
        self,
        incremental_engine: IncrementalEngine,
        query_engine: QueryEngine,
        neighborhood_manager: BoundedNeighborhoodManager,
    ):
        self.incremental_engine = incremental_engine
        self.query_engine = query_engine
        self.neighborhood_manager = neighborhood_manager
        self.stream_queues = []

        # Hook into incremental engine to receive broadcast events
        self.incremental_engine.subscribe_stream(self._on_graph_event)

    def _on_graph_event(self, event_dict: dict) -> None:
        """Pushes graph delta event to all active streaming subscriber queues."""
        for q in list(self.stream_queues):
            try:
                q.put_nowait(event_dict)
            except Exception:
                pass

    def ParseDocument(self, request: pb2.ParseDocumentRequest, context) -> pb2.ParseDocumentResponse:
        t0 = time.perf_counter()
        chunks = self.incremental_engine.chunker.chunk_document(
            document_id=request.document_id, text=request.content
        )
        entities, relationships = self.incremental_engine.extractor.extract_from_document(
            document_id=request.document_id, title=request.title, chunks=chunks
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        pb_chunks = [
            pb2.DocumentChunk(
                chunk_id=c.chunk_id,
                text=c.text,
                chunk_index=c.chunk_index,
                start_char=c.start_char,
                end_char=c.end_char,
                detected_entities=c.detected_entities,
            )
            for c in chunks
        ]

        pb_entities = [
            pb2.ExtractedEntity(
                id=e.id,
                name=e.name,
                type=e.type,
                description=e.description,
                aliases=e.aliases,
                importance_score=e.importance_score,
                embedding=e.embedding or [],
            )
            for e in entities
        ]

        pb_rels = [
            pb2.ExtractedRelationship(
                id=r.id,
                source_name=r.source_name,
                target_name=r.target_name,
                relation_type=r.relation_type,
                description=r.description,
                weight=r.weight,
            )
            for r in relationships
        ]

        return pb2.ParseDocumentResponse(
            document_id=request.document_id,
            chunks=pb_chunks,
            entities=pb_entities,
            relationships=pb_rels,
            processing_time_ms=round(elapsed_ms, 2),
        )

    def UpdateKnowledgeGraph(
        self, request: pb2.UpdateKnowledgeGraphRequest, context
    ) -> pb2.UpdateKnowledgeGraphResponse:
        result = self.incremental_engine.process_document_update(
            document_id=request.document_id,
            title=request.title,
            content=request.content,
            k_hops=request.k_hops if request.k_hops > 0 else 2,
            trigger_leiden=request.trigger_leiden,
            invalidate_cache=request.invalidate_cache,
        )

        return pb2.UpdateKnowledgeGraphResponse(
            success=result["success"],
            document_id=request.document_id,
            affected_nodes_count=result["affected_nodes_count"],
            new_entities_count=result["new_entities_count"],
            new_relationships_count=result["new_relationships_count"],
            updated_embeddings_count=result["updated_embeddings_count"],
            k_hops_applied=result["k_hops_applied"],
            roland_gru_time_ms=result["roland_gru_time_ms"],
            total_time_ms=result["total_time_ms"],
            invalidated_cache_keys=result["invalidated_cache_keys"],
            message="Knowledge graph incrementally updated successfully",
        )

    def StreamGraphUpdates(
        self, request: pb2.StreamGraphUpdatesRequest, context
    ) -> Iterator[pb2.GraphDeltaEvent]:
        """
        Server streaming RPC emitting real-time graph updates to JS orchestration layer.
        """
        client_q = queue.Queue(maxsize=100)
        self.stream_queues.append(client_q)
        logger.info(f"Client '{request.client_id}' connected to graph update stream.")

        try:
            while True:
                try:
                    # Timeout to allow checking client disconnection
                    event = client_q.get(timeout=1.0)
                    yield pb2.GraphDeltaEvent(
                        event_id=f"evt_{int(time.time()*1000)}",
                        timestamp=int(event.get("timestamp", time.time())),
                        document_id=event.get("document_id", ""),
                        action=1,  # ADDED_OR_UPDATED
                    )
                except queue.Empty:
                    # Heartbeat
                    continue
        except Exception as e:
            logger.info(f"Stream client '{request.client_id}' disconnected ({e}).")
        finally:
            if client_q in self.stream_queues:
                self.stream_queues.remove(client_q)

    def Query(self, request: pb2.QueryRequest, context) -> pb2.QueryResponse:
        res = self.query_engine.execute_query(
            query=request.query,
            query_id=request.query_id,
            bypass_cache=request.bypass_cache,
            cost_weight=request.pcst_cost_weight if request.pcst_cost_weight > 0 else None,
            similarity_threshold=request.similarity_threshold if request.similarity_threshold > 0 else None,
            use_gnn=getattr(request, "use_gnn", True),
        )

        citations_pb = [
            pb2.Citation(
                entity_id=c.get("entity_id", ""),
                entity_name=c.get("entity_name", ""),
                document_id=c.get("document_id", ""),
                quote=c.get("quote", ""),
                relevance_score=c.get("relevance_score", 1.0),
            )
            for c in res.get("citations", [])
        ]

        subgraph_dict = res.get("subgraph", {})
        nodes_pb = [
            pb2.ExtractedEntity(
                id=n.get("id", n.get("name", "")),
                name=n.get("name", ""),
                type=n.get("type", "CONCEPT"),
                description=n.get("description", ""),
                importance_score=n.get("importance_score", 1.0),
            )
            for n in subgraph_dict.get("nodes", [])
        ]

        edges_pb = [
            pb2.ExtractedRelationship(
                id=e.get("id", ""),
                source_name=e.get("src", ""),
                target_name=e.get("tgt", ""),
                relation_type=e.get("type", "RELATES_TO"),
                weight=e.get("weight", 1.0),
                description=e.get("description", ""),
            )
            for e in subgraph_dict.get("edges", [])
        ]

        subgraph_pb = pb2.SubgraphData(
            nodes=nodes_pb,
            edges=edges_pb,
            total_prize_collected=subgraph_dict.get("total_prize", 0.0),
            total_cost_incurred=subgraph_dict.get("total_cost", 0.0),
        )

        return pb2.QueryResponse(
            query_id=res["query_id"],
            answer=res["answer"],
            citations=citations_pb,
            subgraph=subgraph_pb,
            cache_hit=res["cache_hit"],
            retrieval_time_ms=res["retrieval_time_ms"],
            generation_time_ms=res["generation_time_ms"],
            total_latency_ms=res["total_latency_ms"],
        )

    def InvalidateCache(
        self, request: pb2.InvalidateCacheRequest, context
    ) -> pb2.InvalidateCacheResponse:
        evicted = self.incremental_engine.semantic_cache.invalidate_for_entities(
            list(request.entity_ids)
        )
        return pb2.InvalidateCacheResponse(
            evicted_keys_count=len(evicted),
            evicted_keys=evicted,
        )

    def BenchmarkLatency(
        self, request: pb2.BenchmarkRequest, context
    ) -> pb2.BenchmarkResponse:
        # The old implementation returned extrapolated/hard-coded numbers. Real measurements
        # come from the offline harness in bench/.
        import grpc
        context.abort(grpc.StatusCode.UNIMPLEMENTED, "Use the offline benchmark harness in bench/")

    def CheckHealth(self, request: pb2.HealthCheckRequest, context) -> pb2.HealthCheckResponse:
        subsystems = {
            "neo4j": self.incremental_engine.graph_store.client.is_connected,
            "redis": self.incremental_engine.semantic_cache._connected,
            "spacy": self.incremental_engine.text_processor.nlp is not None,
            "embeddings": self.incremental_engine.embedder.model is not None,
            "roland_gru": True,
        }
        return pb2.HealthCheckResponse(
            status="SERVING",
            service_name="konnect-intelligence-service",
            version="1.0.0",
            subsystems=subsystems,
        )