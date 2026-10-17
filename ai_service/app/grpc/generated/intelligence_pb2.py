"""
Python Protobuf Definitions for konnect.intelligence.v1.
Provides typed message dataclasses matching shared/proto/intelligence.proto.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class ParseDocumentRequest:
    document_id: str = ""
    title: str = ""
    content: str = ""
    source_url: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class DocumentChunk:
    chunk_id: str = ""
    text: str = ""
    chunk_index: int = 0
    start_char: int = 0
    end_char: int = 0
    detected_entities: List[str] = field(default_factory=list)


@dataclass
class ExtractedEntity:
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    aliases: List[str] = field(default_factory=list)
    importance_score: float = 1.0
    embedding: List[float] = field(default_factory=list)
    properties: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExtractedRelationship:
    id: str = ""
    source_name: str = ""
    target_name: str = ""
    relation_type: str = ""
    description: str = ""
    weight: float = 1.0
    properties: Dict[str, str] = field(default_factory=dict)


@dataclass
class ParseDocumentResponse:
    document_id: str = ""
    chunks: List[DocumentChunk] = field(default_factory=list)
    entities: List[ExtractedEntity] = field(default_factory=list)
    relationships: List[ExtractedRelationship] = field(default_factory=list)
    processing_time_ms: float = 0.0


@dataclass
class UpdateKnowledgeGraphRequest:
    document_id: str = ""
    title: str = ""
    content: str = ""
    k_hops: int = 2
    trigger_leiden: bool = True
    invalidate_cache: bool = True
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class UpdateKnowledgeGraphResponse:
    success: bool = True
    document_id: str = ""
    affected_nodes_count: int = 0
    new_entities_count: int = 0
    new_relationships_count: int = 0
    updated_embeddings_count: int = 0
    k_hops_applied: int = 2
    roland_gru_time_ms: float = 0.0
    total_time_ms: float = 0.0
    invalidated_cache_keys: List[str] = field(default_factory=list)
    message: str = ""


@dataclass
class StreamGraphUpdatesRequest:
    client_id: str = ""
    document_ids: List[str] = field(default_factory=list)


@dataclass
class GraphDeltaEvent:
    event_id: str = ""
    timestamp: int = 0
    action: int = 0
    document_id: str = ""
    entity: Optional[ExtractedEntity] = None
    relationship: Optional[ExtractedRelationship] = None
    community_id: str = ""
    new_embedding: List[float] = field(default_factory=list)


@dataclass
class QueryRequest:
    query_id: str = ""
    query: str = ""
    max_subgraph_nodes: int = 25
    pcst_cost_weight: float = 0.15
    similarity_threshold: float = 0.35
    bypass_cache: bool = False
    llm_provider: str = "default"
    model_name: str = ""


@dataclass
class Citation:
    entity_id: str = ""
    entity_name: str = ""
    document_id: str = ""
    quote: str = ""
    relevance_score: float = 1.0


@dataclass
class CommunitySummary:
    community_id: str = ""
    title: str = ""
    summary: str = ""
    member_entity_names: List[str] = field(default_factory=list)


@dataclass
class SubgraphData:
    nodes: List[ExtractedEntity] = field(default_factory=list)
    edges: List[ExtractedRelationship] = field(default_factory=list)
    communities: List[CommunitySummary] = field(default_factory=list)
    total_prize_collected: float = 0.0
    total_cost_incurred: float = 0.0


@dataclass
class QueryResponse:
    query_id: str = ""
    answer: str = ""
    citations: List[Citation] = field(default_factory=list)
    subgraph: Optional[SubgraphData] = None
    cache_hit: bool = False
    retrieval_time_ms: float = 0.0
    generation_time_ms: float = 0.0
    total_latency_ms: float = 0.0


@dataclass
class InvalidateCacheRequest:
    entity_ids: List[str] = field(default_factory=list)
    document_ids: List[str] = field(default_factory=list)


@dataclass
class InvalidateCacheResponse:
    evicted_keys_count: int = 0
    evicted_keys: List[str] = field(default_factory=list)


@dataclass
class BenchmarkRequest:
    k_hops: int = 2
    num_synthetic_nodes: int = 1000
    num_synthetic_edges: int = 5000


@dataclass
class BenchmarkResponse:
    k_hops: int = 2
    affected_nodes: int = 0
    preprocessing_time_ms: float = 0.0
    roland_gru_time_ms: float = 0.0
    full_graph_equivalent_time_ms: float = 0.0
    speedup_factor: float = 1.0
    total_latency_ms: float = 0.0


@dataclass
class HealthCheckRequest:
    client_id: str = ""


@dataclass
class HealthCheckResponse:
    status: str = "SERVING"
    service_name: str = "konnect-intelligence-service"
    version: str = "1.0.0"
    subsystems: Dict[str, bool] = field(default_factory=dict)
