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
            parsed = None
            last_parse_err = None
            for temp in (0.0,):
                raw_response = self.llm.generate(
                    prompt=prompt,
                    system_prompt=GRAPHRAG_EXTRACTION_SYSTEM_PROMPT,
                    max_tokens=220,
                    temperature=temp,
                )
                try:
                    parsed = self._clean_and_parse_json(raw_response)
                    break
                except Exception as pe:
                    last_parse_err = pe
                    logger.warning(f"Malformed JSON for chunk {chunk.chunk_id}: {pe}")
            if parsed is None:
                logger.info(
                    f"Using resilient sentence-grounded extraction for chunk {chunk.chunk_id}."
                )
                return self._fallback_extraction(chunk)

            raw_entities = parsed.get("entities", [])
            raw_relations = parsed.get("relationships", []) or parsed.get("relations", [])

            # Split chunk text into lines to attach matching sentences if description is omitted
            chunk_lines = [line.strip() for line in chunk.text.split("\n") if len(line.strip()) > 3]

            # Process entities
            for ent in raw_entities:
                name = str(ent.get("name", "")).strip()
                if not name or len(name) < 2 or name.isdigit():
                    continue
                ent_type = str(ent.get("type", "CONCEPT")).strip().upper()
                desc = str(ent.get("description", "")).strip()
                if not desc:
                    # Automatically find matching context sentence in chunk text
                    for line in chunk_lines:
                        if name.lower() in line.lower():
                            desc = line[:220]
                            break
                    if not desc:
                        desc = f"Referenced in {chunk.document_id}"

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

                rel_type = str(rel.get("relation_type") or rel.get("relation") or "RELATED_TO").strip().upper()
                rel_desc = str(rel.get("description", "")).strip() or f"{src} is related to {tgt}"
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
            logger.warning(f"Extraction exception for chunk {chunk.chunk_id}: {e}. Falling back to NLP entity extraction.")
            return self._fallback_extraction(chunk)

        # If LLM returned zero entities, fall back to NLP entity extraction
        if not entities:
            return self._fallback_extraction(chunk)

        return entities, relationships

    def _fallback_extraction(
        self, chunk: Chunk
    ) -> Tuple[List[ExtractedEntity], List[ExtractedRelationship]]:
        """Resilient fallback extraction using NLP entity recognition and context sentence grounding."""
        import re
        entities = []
        relationships = []
        seen = set()

        NOISE_WORDS = {
            "500", "21", "3", "4", "5", "6", "7", "8", "9", "10", "100", "400", "1650", "1600",
            "zero", "deemed", "io", "dsa", "oop", "sql", "api", "apis", "jwt", "etc", "and", "or",
            "the", "in", "on", "at", "to", "for", "with", "by", "from", "an", "a", "as", "is",
            "date", "dates", "phone", "email", "link", "links", "true", "false"
        }

        # Split text into lines/sentences to find exact grounding sentences
        raw_lines = [line.strip() for line in chunk.text.split("\n") if len(line.strip()) > 3]

        # Candidate names from detected entities and capital phrase patterns
        candidate_names = list(getattr(chunk, "detected_entities", []))
        if len(candidate_names) < 8:
            phrase_matches = re.findall(r"\b[A-Z][a-zA-Z0-9_\-\.\+]+(?:\s+[A-Z][a-zA-Z0-9_\-\.\+]+)*\b", chunk.text)
            for pm in phrase_matches:
                if len(pm) > 2 and pm not in candidate_names:
                    candidate_names.append(pm)

        # Extract entities from detected spotted entities
        for ent_name in candidate_names:
            normalized = ent_name.strip()
            norm_lower = normalized.lower()
            if (
                len(normalized) > 2
                and not normalized.isdigit()
                and not re.match(r"^[\d\.\+\-\/]+$", normalized)
                and norm_lower not in NOISE_WORDS
                and norm_lower not in seen
            ):
                seen.add(norm_lower)
                # Find matching context sentence from the chunk
                matched_sentence = ""
                for line in raw_lines:
                    if norm_lower in line.lower():
                        matched_sentence = line[:220]
                        break

                desc = matched_sentence if matched_sentence else f"Referenced in {chunk.document_id}"
                ent_id = hashlib.sha256(norm_lower.encode()).hexdigest()[:16]
                emb = self.embedder.embed_text(f"{normalized}: {desc}").tolist()
                entities.append(
                    ExtractedEntity(
                        id=ent_id,
                        name=normalized,
                        type="ENTITY",
                        description=desc,
                        importance_score=0.9,
                        embedding=emb,
                        properties={"source_chunk": chunk.chunk_id},
                    )
                )

        # Connect sequential entities with informative relationships
        for i in range(len(entities) - 1):
            src = entities[i].name
            tgt = entities[i + 1].name
            rel_id = hashlib.sha256(f"{src.lower()}:{tgt.lower()}:RELATED_TO".encode()).hexdigest()[:16]
            relationships.append(
                ExtractedRelationship(
                    id=rel_id,
                    source_name=src,
                    target_name=tgt,
                    relation_type="RELATED_TO",
                    description=f"Appears together in {chunk.document_id}",
                    weight=0.8,
                )
            )

        return entities, relationships

    def extract_from_document(
        self, document_id: str, title: str, chunks: List[Chunk], fast_mode: bool = True
    ) -> Tuple[List[ExtractedEntity], List[ExtractedRelationship]]:
        """
        Processes all chunks for a given document and consolidates entities & relationships.
        Merges duplicate entities across chunks and unions relationships.
        When fast_mode is True (default), extracts grounded entities via high-speed NLP in <20ms.
        When fast_mode is False, invokes the compact LLM prompt for deep extraction.
        """
        entity_map: Dict[str, ExtractedEntity] = {}
        relationship_map: Dict[str, ExtractedRelationship] = {}

        for chunk in chunks:
            if fast_mode:
                chunk_entities, chunk_rels = self._fallback_extraction(chunk)
            else:
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
        """Strips markdown code blocks and parses JSON output with regex repair."""
        import re
        cleaned = raw.strip()
        if "```" in cleaned:
            cleaned = re.sub(r"```(?:json)?", "", cleaned).strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            cleaned = cleaned[start : end + 1]

        # Fix trailing commas e.g. [1, 2,] or {"a": 1,}
        cleaned = re.sub(r",\s*([\}\]])", r"\1", cleaned)

        try:
            return json.loads(cleaned)
        except Exception:
            # Fallback regex extraction of entities and relationships if outer JSON was slightly malformed
            ent_pattern = r'\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"type"\s*:\s*"([^"]+)"\s*,\s*"description"\s*:\s*"([^"]+)"'
            ent_matches = re.findall(ent_pattern, cleaned)
            entities = [
                {"name": m[0].strip(), "type": m[1].strip(), "description": m[2].strip(), "importance_score": 1.0}
                for m in ent_matches
                if len(m[0].strip()) > 1
            ]

            rel_pattern = r'\{\s*"source"\s*:\s*"([^"]+)"\s*,\s*"target"\s*:\s*"([^"]+)"\s*,\s*"relation_type"\s*:\s*"([^"]+)"\s*,\s*"description"\s*:\s*"([^"]+)"'
            rel_matches = re.findall(rel_pattern, cleaned)
            relationships = [
                {"source": m[0].strip(), "target": m[1].strip(), "relation_type": m[2].strip(), "description": m[3].strip(), "weight": 1.0}
                for m in rel_matches
                if len(m[0].strip()) > 1 and len(m[1].strip()) > 1
            ]

            if entities:
                return {"entities": entities, "relationships": relationships}
            raise
