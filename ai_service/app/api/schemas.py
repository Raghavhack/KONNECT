"""
Pydantic Request and Response Schemas for FastAPI REST API.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class DocumentIngestRequest(BaseModel):
    document_id: str = Field(..., description="Unique document ID (e.g., from Drive/OneDrive)")
    title: str = Field(default="", description="Document title")
    content: str = Field(..., description="Raw text content of the document")
    k_hops: int = Field(default=2, ge=1, le=5, description="Bounded-neighborhood radius for ROLAND GRU")
    trigger_leiden: bool = Field(default=True, description="Whether to trigger local Leiden community updates")
    invalidate_cache: bool = Field(default=True, description="Whether to evict semantic cache for affected nodes")


class DocumentIngestResponse(BaseModel):
    success: bool
    document_id: str
    affected_nodes_count: int
    new_entities_count: int
    new_relationships_count: int
    updated_embeddings_count: int
    communities_updated_count: int
    invalidated_cache_keys: List[str]
    k_hops_applied: int
    preprocessing_time_ms: float
    extraction_time_ms: float
    roland_gru_time_ms: float
    total_time_ms: float


class QueryRequestModel(BaseModel):
    query: str = Field(..., description="User search or question text")
    query_id: Optional[str] = Field(default=None, description="Optional tracking ID")
    max_subgraph_nodes: int = Field(default=25, ge=1, le=100)
    pcst_cost_weight: Optional[float] = Field(default=0.20, ge=0.01, le=1.0)
    similarity_threshold: Optional[float] = Field(default=0.35, ge=0.0, le=1.0)
    bypass_cache: bool = Field(default=False, description="Bypass Redis semantic cache")
    use_gnn: bool = Field(default=True, description="Use GNN representations or base text embeddings (Arm D ablation)")


class CitationModel(BaseModel):
    entity_id: str
    entity_name: str
    document_id: str
    quote: str
    relevance_score: float


class SubgraphResponseModel(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    total_prize: float
    total_cost: float
    prizes: Dict[str, float] = Field(default_factory=dict)


class QueryResponseModel(BaseModel):
    query_id: str
    query: str
    answer: str
    citations: List[CitationModel]
    subgraph: SubgraphResponseModel
    cache_hit: bool
    retrieval_time_ms: float
    generation_time_ms: float
    total_latency_ms: float


class CacheInvalidateRequest(BaseModel):
    entity_names: List[str] = Field(..., description="List of entity names to evict from semantic cache")


class CacheInvalidateResponse(BaseModel):
    evicted_keys_count: int
    evicted_keys: List[str]


class BenchmarkRequestModel(BaseModel):
    k_hops: int = Field(default=2, ge=1, le=5)
    num_synthetic_nodes: int = Field(default=10000, ge=100)
    num_synthetic_edges: int = Field(default=50000, ge=100)


class BenchmarkResponseModel(BaseModel):
    k_hops: int
    bounded_nodes_evaluated: int
    full_graph_nodes: int
    bounded_latency_ms: float
    full_graph_latency_ms: float
    speedup_factor: float


class HealthResponse(BaseModel):
    status: str
    service_name: str
    version: str
    subsystems: Dict[str, bool]
