"""
FastAPI Routes for KONNECT Intelligence Layer.
Provides high-performance async REST interfaces matching the gRPC servicer methods.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any

from .schemas import (
    DocumentIngestRequest,
    DocumentIngestResponse,
    QueryRequestModel,
    QueryResponseModel,
    CacheInvalidateRequest,
    CacheInvalidateResponse,
    BenchmarkRequestModel,
    BenchmarkResponseModel,
    HealthResponse,
)

router = APIRouter(prefix="/api/v1", tags=["intelligence"])

# Dependency container placeholder populated at app startup
pipeline_container: Dict[str, Any] = {}


def get_incremental_engine():
    engine = pipeline_container.get("incremental_engine")
    if not engine:
        raise HTTPException(status_code=503, detail="Incremental Engine not initialized")
    return engine


def get_query_engine():
    engine = pipeline_container.get("query_engine")
    if not engine:
        raise HTTPException(status_code=503, detail="Query Engine not initialized")
    return engine


def get_neighborhood_manager():
    manager = pipeline_container.get("neighborhood_manager")
    if not manager:
        raise HTTPException(status_code=503, detail="Neighborhood Manager not initialized")
    return manager


@router.post("/documents/update", response_model=DocumentIngestResponse)
async def update_document(
    payload: DocumentIngestRequest,
    engine=Depends(get_incremental_engine),
):
    """
    Incrementally updates the knowledge graph with document changes.
    Performs spaCy preprocessing, GraphRAG extraction, Neo4j update,
    k-hop ROLAND GRU re-embedding, Leiden clustering, and Redis cache invalidation.
    """
    try:
        res = engine.process_document_update(
            document_id=payload.document_id,
            title=payload.title,
            content=payload.content,
            k_hops=payload.k_hops,
            trigger_leiden=payload.trigger_leiden,
            invalidate_cache=payload.invalidate_cache,
        )
        return DocumentIngestResponse(**res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=QueryResponseModel)
async def answer_query(
    payload: QueryRequestModel,
    engine=Depends(get_query_engine),
):
    """
    Answers user queries via PCST semantic subgraph retrieval and grounded LLM generation.
    Checks Redis semantic cache first.
    """
    try:
        res = engine.execute_query(
            query=payload.query,
            query_id=payload.query_id,
            bypass_cache=payload.bypass_cache,
            cost_weight=payload.pcst_cost_weight,
            similarity_threshold=payload.similarity_threshold,
            use_gnn=payload.use_gnn,
        )
        return QueryResponseModel(**res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/invalidate", response_model=CacheInvalidateResponse)
async def invalidate_cache(
    payload: CacheInvalidateRequest,
    engine=Depends(get_incremental_engine),
):
    """
    Explicitly evicts semantic cache entries referencing the specified entities.
    """
    try:
        evicted = engine.semantic_cache.invalidate_for_entities(payload.entity_names)
        return CacheInvalidateResponse(
            evicted_keys_count=len(evicted),
            evicted_keys=evicted,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/benchmark", response_model=BenchmarkResponseModel)
async def benchmark_latency(
    payload: BenchmarkRequestModel,
    manager=Depends(get_neighborhood_manager),
):
    """
    Benchmarks k-hop bounded re-embedding against full graph recomputation.
    Demonstrates the latency properties required for Section 7 evaluation.
    """
    try:
        res = manager.benchmark_comparison(
            num_total_nodes=payload.num_synthetic_nodes,
            num_total_edges=payload.num_synthetic_edges,
            k=payload.k_hops,
        )
        return BenchmarkResponseModel(**res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Returns service health status and connected subsystems."""
    inc_engine = pipeline_container.get("incremental_engine")
    subsystems = {
        "neo4j": inc_engine.graph_store.client.is_connected if inc_engine else False,
        "redis": inc_engine.semantic_cache._connected if inc_engine else False,
        "spacy": inc_engine.text_processor.nlp is not None if inc_engine else False,
        "embeddings": inc_engine.embedder.model is not None if inc_engine else False,
        "roland_gru": True,
    }
    return HealthResponse(
        status="SERVING",
        service_name="konnect-intelligence-service",
        version="1.0.0",
        subsystems=subsystems,
    )
