"""
Neo4j Knowledge Graph Store.
Handles transactional entity/relation upserts, k-hop neighborhood queries,
and colocated vector similarity search for PCST retrieval.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
from .neo4j_client import Neo4jClient
from ..extraction.models import ExtractedEntity, ExtractedRelationship
from ..preprocessing.chunker import Chunk

logger = logging.getLogger(__name__)


class Neo4jGraphStore:
    """
    High-level knowledge graph store interfacing with Neo4j.
    Enforces native k-hop traversal, transactional idempotency, and vector indexing.
    """

    def __init__(self, client: Neo4jClient):
        self.client = client

    def upsert_document_and_chunks(
        self, document_id: str, title: str, chunks: List[Chunk]
    ) -> None:
        """Stores document record and connects chunk nodes with sequential NEXT edges."""
        if not self.client.is_connected:
            self.client.in_memory_fallback.documents[document_id] = {
                "id": document_id,
                "title": title,
                "num_chunks": len(chunks),
            }
            return

        cypher_doc = """
        MERGE (d:Document {id: $doc_id})
        SET d.title = $title, d.updated_at = timestamp()
        """
        self.client.execute_query(cypher_doc, {"doc_id": document_id, "title": title})

        # Insert chunks
        cypher_chunk = """
        UNWIND $chunks AS ch
        MERGE (c:Chunk {id: ch.chunk_id})
        SET c.index = ch.chunk_index,
            c.text = ch.text,
            c.start_char = ch.start_char,
            c.end_char = ch.end_char,
            c.document_id = $doc_id
        MERGE (d:Document {id: $doc_id})
        MERGE (c)-[:PART_OF]->(d)
        """
        chunk_data = [
            {
                "chunk_id": c.chunk_id,
                "chunk_index": c.chunk_index,
                "text": c.text,
                "start_char": c.start_char,
                "end_char": c.end_char,
            }
            for c in chunks
        ]
        self.client.execute_query(cypher_chunk, {"doc_id": document_id, "chunks": chunk_data})

    def delete_document_contributions(self, document_id: str) -> Dict[str, Any]:
        """
        Removes a document's contributions before updating:
        1. Deletes all chunk nodes for the document.
        2. Deletes MENTIONED_IN edges from entities to this document.
        3. Deletes entities that are no longer mentioned in ANY other document.
        Enforces Section 6.4 partial invalidation.
        """
        if not self.client.is_connected:
            return self.client.in_memory_fallback.delete_document_contributions(document_id)

        # 1. Delete document chunks
        cypher_chunks = """
        MATCH (c:Chunk)-[:PART_OF]->(d:Document {id: $doc_id})
        DETACH DELETE c
        """
        self.client.execute_query(cypher_chunks, {"doc_id": document_id})

        # 2. Delete MENTIONED_IN edges and prune orphaned entities
        cypher_entities = """
        MATCH (e:Entity)-[r:MENTIONED_IN]->(d:Document {id: $doc_id})
        DELETE r
        WITH e
        WHERE NOT (e)-[:MENTIONED_IN]->(:Document)
        DETACH DELETE e
        RETURN count(e) AS deleted_count
        """
        records = self.client.execute_query(cypher_entities, {"doc_id": document_id})
        deleted_count = records[0]["deleted_count"] if records else 0

        return {
            "document_id": document_id,
            "deleted_entities_count": deleted_count,
        }

    def upsert_entities(
        self, entities: List[ExtractedEntity], document_id: Optional[str] = None
    ) -> None:
        """Upserts entities into graph, setting attributes and embeddings."""
        if not entities:
            return

        if not self.client.is_connected:
            for ent in entities:
                self.client.in_memory_fallback.upsert_node(
                    label="Entity",
                    name=ent.name,
                    properties={
                        "id": ent.id,
                        "type": ent.type,
                        "description": ent.description,
                        "importance_score": ent.importance_score,
                        "embedding": ent.embedding,
                        "document_id": document_id,
                    },
                )
            return

        cypher = """
        UNWIND $entities AS e
        MERGE (n:Entity {name: e.name})
        ON CREATE SET
            n.id = e.id,
            n.type = e.type,
            n.description = e.description,
            n.importance_score = e.importance_score,
            n.embedding = e.embedding,
            n.created_at = timestamp()
        ON MATCH SET
            n.description = e.description,
            n.importance_score = e.importance_score,
            n.embedding = coalesce(e.embedding, n.embedding),
            n.updated_at = timestamp()
        """
        batch = [
            {
                "id": ent.id,
                "name": ent.name,
                "type": ent.type,
                "description": ent.description,
                "importance_score": ent.importance_score,
                "embedding": ent.embedding,
            }
            for ent in entities
        ]
        self.client.execute_query(cypher, {"entities": batch})

        # Link to document if provided
        if document_id:
            cypher_link = """
            MATCH (d:Document {id: $doc_id})
            UNWIND $entity_names AS name
            MATCH (e:Entity {name: name})
            MERGE (e)-[:MENTIONED_IN]->(d)
            """
            self.client.execute_query(
                cypher_link,
                {"doc_id": document_id, "entity_names": [e.name for e in entities]},
            )

    def upsert_relationships(
        self, relationships: List[ExtractedRelationship]
    ) -> None:
        """Upserts relationships between entities with weight and description."""
        if not relationships:
            return

        if not self.client.is_connected:
            for rel in relationships:
                self.client.in_memory_fallback.upsert_edge(
                    src=rel.source_name,
                    tgt=rel.target_name,
                    relation_type=rel.relation_type,
                    properties={
                        "id": rel.id,
                        "description": rel.description,
                        "weight": rel.weight,
                    },
                )
            return

        cypher = """
        UNWIND $rels AS r
        MATCH (s:Entity {name: r.source_name})
        MATCH (t:Entity {name: r.target_name})
        MERGE (s)-[rel:RELATES_TO {type: r.relation_type}]->(t)
        ON CREATE SET
            rel.id = r.id,
            rel.weight = r.weight,
            rel.description = r.description,
            rel.created_at = timestamp()
        ON MATCH SET
            rel.weight = r.weight,
            rel.description = r.description,
            rel.updated_at = timestamp()
        """
        batch = [
            {
                "id": rel.id,
                "source_name": rel.source_name,
                "target_name": rel.target_name,
                "relation_type": rel.relation_type,
                "weight": rel.weight,
                "description": rel.description,
            }
            for rel in relationships
        ]
        self.client.execute_query(cypher, {"rels": batch})

    def get_k_hop_neighborhood(
        self, seed_entity_names: List[str], k: int = 2
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Retrieves the bounded k-hop neighborhood (induced subgraph) around seed entities.
        Critical for the ROLAND bounded-neighborhood re-embedding pass!
        """
        if not seed_entity_names:
            return [], []

        if not self.client.is_connected:
            return self.client.in_memory_fallback.get_k_hop_subgraph(seed_entity_names, k)

        cypher = f"""
        MATCH (seed:Entity) WHERE seed.name IN $seeds
        CALL apoc.path.subgraphAll(seed, {{
            maxLevel: {k},
            relationshipFilter: 'RELATES_TO'
        }})
        YIELD nodes, relationships
        UNWIND nodes AS n
        WITH collect(DISTINCT n) AS all_nodes, collect(DISTINCT relationships) AS all_rels
        RETURN all_nodes, all_rels
        """

        # Native fallback Cypher without requiring APOC plugin:
        native_cypher = f"""
        MATCH (seed:Entity) WHERE seed.name IN $seeds
        OPTIONAL MATCH (seed)-[:RELATES_TO*0..{k}]-(neighbor:Entity)
        WITH collect(DISTINCT neighbor) AS node_list
        UNWIND node_list AS n
        OPTIONAL MATCH (n)-[r:RELATES_TO]-(m:Entity)
        WHERE m IN node_list
        RETURN node_list AS nodes, collect(DISTINCT r) AS rels
        """

        try:
            records = self.client.execute_query(native_cypher, {"seeds": seed_entity_names})
            if records and records[0].get("nodes"):
                nodes = [
                    {
                        "name": n.get("name"),
                        "type": n.get("type", "CONCEPT"),
                        "description": n.get("description", ""),
                        "importance_score": n.get("importance_score", 1.0),
                        "embedding": n.get("embedding"),
                        "gnn_embedding": n.get("gnn_embedding"),
                    }
                    for n in records[0]["nodes"]
                    if n is not None and n.get("name")
                ]
                rels = [
                    {
                        "src": r.nodes[0].get("name"),
                        "tgt": r.nodes[1].get("name"),
                        "type": r.type,
                        "weight": r.get("weight", 1.0),
                        "description": r.get("description", ""),
                    }
                    for r in records[0]["rels"]
                    if r is not None and len(r.nodes) >= 2
                ]
                return nodes, rels
        except Exception as e:
            logger.warning(f"Error querying k-hop neighborhood from Neo4j: {e}")

        # Fallback query
        simple_cypher = """
        MATCH (seed:Entity) WHERE seed.name IN $seeds
        OPTIONAL MATCH (seed)-[r:RELATES_TO]-(neighbor:Entity)
        RETURN seed, r, neighbor
        """
        records = self.client.execute_query(simple_cypher, {"seeds": seed_entity_names})
        nodes_dict = {}
        rels_list = []
        for rec in records:
            s = rec.get("seed")
            if s and s.get("name") not in nodes_dict:
                nodes_dict[s.get("name")] = dict(s)
            nb = rec.get("neighbor")
            if nb and nb.get("name") not in nodes_dict:
                nodes_dict[nb.get("name")] = dict(nb)
            r = rec.get("r")
            if r and s and nb:
                rels_list.append({
                    "src": s.get("name"),
                    "tgt": nb.get("name"),
                    "type": r.type,
                    "weight": r.get("weight", 1.0),
                    "description": r.get("description", ""),
                })
        return list(nodes_dict.values()), rels_list

    def update_node_embeddings(self, embeddings_dict: Dict[str, List[float]]) -> None:
        """Updates node GNN embedding vectors (output from ROLAND GRU) in Neo4j without overwriting text embeddings."""
        if not embeddings_dict:
            return

        if not self.client.is_connected:
            for name, emb in embeddings_dict.items():
                self.client.in_memory_fallback.upsert_node(
                    label="Entity", name=name, properties={"gnn_embedding": emb}
                )
            return

        cypher = """
        UNWIND $updates AS u
        MATCH (e:Entity {name: u.name})
        SET e.gnn_embedding = u.embedding, e.gnn_embedding_updated_at = timestamp()
        """
        batch = [{"name": k, "embedding": v} for k, v in embeddings_dict.items()]
        self.client.execute_query(cypher, {"updates": batch})

    def search_vector_index(
        self, query_embedding: List[float], top_k: int = 15, use_gnn: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Queries the colocated Neo4j vector index for entities closest to the query.
        Used for initial prize seeding in PCST retrieval.
        Supports Arm D (PCST without GNN) when use_gnn=False.
        """
        if not self.client.is_connected:
            return self.client.in_memory_fallback.vector_search(query_embedding, top_k, use_gnn=use_gnn)

        index_name = self.client.gnn_vector_index_name if (use_gnn and hasattr(self.client, "gnn_vector_index_name")) else self.client.vector_index_name

        cypher = f"""
        CALL db.index.vector.queryNodes('{index_name}', $top_k, $query_vector)
        YIELD node, score
        RETURN node.name AS name,
               node.type AS type,
               node.description AS description,
               node.importance_score AS importance_score,
               node.embedding AS embedding,
               node.gnn_embedding AS gnn_embedding,
               score
        """
        try:
            records = self.client.execute_query(
                cypher, {"top_k": top_k, "query_vector": query_embedding}
            )
            if records:
                return records
            # If GNN vector index returns empty or isn't built yet, try standard vector index
            if use_gnn and index_name != self.client.vector_index_name:
                cypher_fallback = f"""
                CALL db.index.vector.queryNodes('{self.client.vector_index_name}', $top_k, $query_vector)
                YIELD node, score
                RETURN node.name AS name,
                       node.type AS type,
                       node.description AS description,
                       node.importance_score AS importance_score,
                       node.embedding AS embedding,
                       node.gnn_embedding AS gnn_embedding,
                       score
                """
                return self.client.execute_query(cypher_fallback, {"top_k": top_k, "query_vector": query_embedding})
            return records
        except Exception as e:
            logger.debug(f"Direct vector index query exception: {e}. Falling back to in-memory cosine.")
            return self.client.in_memory_fallback.vector_search(query_embedding, top_k, use_gnn=use_gnn)
