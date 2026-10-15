"""
Custom GraphRAG Extractor & Incremental Adaptation Wrapper.
Inspired by Microsoft GraphRAG SDK, designed specifically to intercept per-document
extraction for real-time incremental knowledge graph updates.
"""

import json
import logging
import hashlib
import time
from typing import List, Dict, Tuple, Optional, Any

from .models import ExtractedEntity, ExtractedRelationship, GraphDelta
from .prompts import GRAPHRAG_EXTRACTION_SYSTEM_PROMPT
from ..preprocessing.chunker import Chunk
from ..embeddings.embedder import SentenceTransformerEmbedder

logger = logging.getLogger(__name__)


class GraphRAGIncrementalExtractor:
    """
    Custom wrapper class around GraphRAG extraction logic.
    Supports both batch full-corpus bootstrap indexing and per-document incremental extraction.
    """

    def __init__(
        self,
        llm_client: Any,
        embedder: Optional[SentenceTransformerEmbedder] = None,
        similarity_threshold: float = 0.88,
    ):
        self.llm = llm_client
        self.embedder = embedder or SentenceTransformerEmbedder()
        self.similarity_threshold = similarity_threshold

    def extract_from_chunk(self, chunk: Chunk) -> Tuple[List[ExtractedEntity], List[ExtractedRelationship]]:
        """
        Extracts entities and relationships from a single text chunk using the LLM.
        Includes robust JSON parsing, normalization, and fallback entity detection.
        """
        prompt = (
            f"Analyze this document chunk and extract entities and relationships:\n\n"
            f"Document ID: {chunk.document_id}\n"
            f"Chunk Text:\n\"\"\"{chunk.text}\"\"\""
        )

        entities: List[ExtractedEntity] = []
        relationships: List[ExtractedRelationship] = []

        try:
            raw_response = self.llm.generate(
                prompt=prompt,
                system_prompt=GRAPHRAG_EXTRACTION_SYSTEM_PROMPT,
                temperature=0.0,
            )

            parsed = self._clean_and_parse_json(raw_response)
            raw_entities = parsed.get("entities", [])
            raw_relations = parsed.get("relationships", [])

            # Process entities
            for ent in raw_entities:
                name = str(ent.get("name", "")).strip()
                if not name:
                    continue
                ent_type = str(ent.get("type", "CONCEPT")).strip().upper()
                desc = str(ent.get("description", "")).strip()
                importance = float(ent.get("importance_score", 1.0))

                entity_id = hashlib.sha256(name.lower().encode()).hexdigest()[:16]
                emb = self.embedder.embed_text(f"{name}: {desc}").tolist()

                entities.append(
                    ExtractedEntity(
                        id=entity_id,
                        name=name,
                        type=ent_type,
                        description=desc,
                        importance_score=importance,
                        embedding=emb,
                        properties={"source_chunk": chunk.chunk_id},
                    )
                )

            # Process relationships
            for rel in raw_relations:
                src = str(rel.get("source", "")).strip()
                tgt = str(rel.get("target", "")).strip()
                if not src or not tgt or src.lower() == tgt.lower():
                    continue

                rel_type = str(rel.get("relation_type", "RELATED_TO")).strip().upper()
                rel_desc = str(rel.get("description", "")).strip()
                rel_weight = float(rel.get("weight", 1.0))

                rel_id = hashlib.sha256(
                    f"{src.lower()}:{tgt.lower()}:{rel_type}".encode()
                ).hexdigest()[:16]

                relationships.append(
                    ExtractedRelationship(
                        id=rel_id,
                        source_name=src,
                        target_name=tgt,
                        relation_type=rel_type,
                        description=rel_desc,
                        weight=rel_weight,
                        properties={"source_chunk": chunk.chunk_id},
                    )
                )

        except Exception as e:
            logger.warning(
                f"LLM extraction encountered error: {e}. Falling back to candidate entity spotting."
            )
            # Heuristic extraction fallback using detected entities
            entities, relationships = self._fallback_extraction(chunk)

        return entities, relationships

    def _fallback_extraction(
        self, chunk: Chunk
    ) -> Tuple[List[ExtractedEntity], List[ExtractedRelationship]]:
        """Fallback extraction using candidate spotted tokens in chunk when LLM is unavailable."""
        entities = []
        relationships = []
        seen = set()

        for ent_name in chunk.detected_entities:
            normalized = ent_name.strip()
            if len(normalized) > 1 and normalized.lower() not in seen:
                seen.add(normalized.lower())
                ent_id = hashlib.sha256(normalized.lower().encode()).hexdigest()[:16]
                emb = self.embedder.embed_text(normalized).tolist()
                entities.append(
                    ExtractedEntity(
                        id=ent_id,
                        name=normalized,
                        type="ENTITY",
                        description=f"Entity spotted in chunk {chunk.chunk_index}",
                        importance_score=1.0,
                        embedding=emb,
                    )
                )

        # Connect adjacent spotted entities with co-occurrence relationships
        for i in range(len(entities) - 1):
            src = entities[i].name
            tgt = entities[i + 1].name
            rel_id = hashlib.sha256(f"{src.lower()}:{tgt.lower()}:CO_OCCURS".encode()).hexdigest()[:16]
            relationships.append(
                ExtractedRelationship(
                    id=rel_id,
                    source_name=src,
                    target_name=tgt,
                    relation_type="CO_OCCURS_WITH",
                    description=f"Co-occurs within chunk {chunk.chunk_index}",
                    weight=0.8,
                )
            )

        return entities, relationships

    def extract_from_document(
        self, document_id: str, title: str, chunks: List[Chunk]
    ) -> Tuple[List[ExtractedEntity], List[ExtractedRelationship]]:
        """
        Processes all chunks for a given document and consolidates entities & relationships.
        Merges duplicate entities across chunks and unions relationships.
        """
        entity_map: Dict[str, ExtractedEntity] = {}
        relationship_map: Dict[str, ExtractedRelationship] = {}

        for chunk in chunks:
            chunk_entities, chunk_rels = self.extract_from_chunk(chunk)

            for ent in chunk_entities:
                norm_key = ent.name.lower()
                if norm_key in entity_map:
                    # Merge descriptions and retain max importance
                    existing = entity_map[norm_key]
                    if ent.description and ent.description not in existing.description:
                        existing.description = f"{existing.description}; {ent.description}"
                    existing.importance_score = max(existing.importance_score, ent.importance_score)
                else:
                    entity_map[norm_key] = ent

            for rel in chunk_rels:
                rel_key = f"{rel.source_name.lower()}->{rel.target_name.lower()}:{rel.relation_type}"
                if rel_key in relationship_map:
                    existing_rel = relationship_map[rel_key]
                    existing_rel.weight = min(1.0, existing_rel.weight + 0.1)
                else:
                    relationship_map[rel_key] = rel

        return list(entity_map.values()), list(relationship_map.values())

    def compute_graph_delta(
        self,
        document_id: str,
        existing_entity_names: List[str],
        extracted_entities: List[ExtractedEntity],
        extracted_relationships: List[ExtractedRelationship],
    ) -> GraphDelta:
        """
        Computes the incremental delta between existing knowledge graph state
        and newly extracted document content.
        Identifies added vs updated entities and affected entity names.
        """
        existing_set = set(e.lower() for e in existing_entity_names)
        added_entities = []
        updated_entities = []
        affected_names = set()

        for ent in extracted_entities:
            affected_names.add(ent.name)
            if ent.name.lower() in existing_set:
                updated_entities.append(ent)
            else:
                added_entities.append(ent)

        for rel in extracted_relationships:
            affected_names.add(rel.source_name)
            affected_names.add(rel.target_name)

        return GraphDelta(
            document_id=document_id,
            timestamp=time.time(),
            added_entities=added_entities,
            updated_entities=updated_entities,
            added_relationships=extracted_relationships,
            affected_entity_names=list(affected_names),
        )

    def bootstrap_corpus(self, documents: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Batch bootstrap indexer for initial corpus ingestion.
        Mirrors Microsoft's full-corpus GraphRAG indexing pipeline.
        """
        logger.info(f"Starting batch bootstrap indexing on {len(documents)} documents.")
        total_entities = {}
        total_relationships = {}

        for doc in documents:
            doc_id = doc.get("id", "doc_0")
            title = doc.get("title", "")
            content = doc.get("content", "")
            # Mock chunk
            chunk = Chunk(
                chunk_id=f"{doc_id}_0",
                document_id=doc_id,
                chunk_index=0,
                text=content,
                start_char=0,
                end_char=len(content),
                token_count=len(content.split()),
            )
            ents, rels = self.extract_from_chunk(chunk)
            for e in ents:
                total_entities[e.name.lower()] = e
            for r in rels:
                k = f"{r.source_name.lower()}->{r.target_name.lower()}"
                total_relationships[k] = r

        return {
            "num_documents": len(documents),
            "num_entities": len(total_entities),
            "num_relationships": len(total_relationships),
            "entities": list(total_entities.values()),
            "relationships": list(total_relationships.values()),
        }

    def _clean_and_parse_json(self, raw: str) -> Dict[str, Any]:
        """Strips markdown code blocks and parses JSON output."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try finding first { and last }
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                return json.loads(cleaned[start : end + 1])
            raise
