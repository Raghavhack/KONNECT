"""
Data Models for GraphRAG Knowledge Graph Extraction and Deltas.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    id: str
    name: str
    type: str = "CONCEPT"
    description: str = ""
    aliases: List[str] = Field(default_factory=list)
    importance_score: float = 1.0
    embedding: Optional[List[float]] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class ExtractedRelationship(BaseModel):
    id: str
    source_name: str
    target_name: str
    relation_type: str = "RELATED_TO"
    description: str = ""
    weight: float = 1.0
    properties: Dict[str, Any] = Field(default_factory=dict)


class Community(BaseModel):
    id: str
    title: str
    summary: str
    member_entity_names: List[str] = Field(default_factory=list)
    level: int = 0
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphDelta(BaseModel):
    """
    Represents the incremental delta between graph snapshots after a document update.
    Used for k-hop neighborhood bounding and real-time streaming to the JS orchestration layer.
    """
    document_id: str
    timestamp: float
    added_entities: List[ExtractedEntity] = Field(default_factory=list)
    updated_entities: List[ExtractedEntity] = Field(default_factory=list)
    deleted_entity_names: List[str] = Field(default_factory=list)
    added_relationships: List[ExtractedRelationship] = Field(default_factory=list)
    updated_relationships: List[ExtractedRelationship] = Field(default_factory=list)
    deleted_relationship_ids: List[str] = Field(default_factory=list)
    affected_entity_names: List[str] = Field(default_factory=list)
