"""
Neo4j Graph Database Connection & Schema Management.
Handles connection pooling, schema constraints, and colocated vector index initialization.
Includes an in-memory graph fallback for standalone testing.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase, Driver
    NEO4J_AVAILABLE = True
except ImportError:
    GraphDatabase = None
    Driver = None
    NEO4J_AVAILABLE = False


class InMemoryGraphFallback:
    """
    In-memory graph database fallback for testing and offline environments.
    Implements core graph operations without requiring an active Neo4j daemon.
    """

    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self.documents: Dict[str, Dict[str, Any]] = {}

    def upsert_node(self, label: str, name: str, properties: Dict[str, Any]) -> None:
        key = f"{label}:{name.lower()}"
        doc_id = properties.get("document_id")
        if key in self.nodes:
            self.nodes[key].update(properties)
            if doc_id:
                self.nodes[key].setdefault("mentioned_in_docs", set()).add(doc_id)
        else:
            mentioned = {doc_id} if doc_id else set()
            self.nodes[key] = {
                "label": label,
                "name": name,
                "mentioned_in_docs": mentioned,
                **properties,
            }

    def delete_document_contributions(self, document_id: str) -> Dict[str, Any]:
        """
        Removes a document's contributions and deletes entities mentioned exclusively
        by this document (Section 6.4 partial invalidation).
        """
        if document_id in self.documents:
            del self.documents[document_id]

        orphaned_entities = []
        for key, node in list(self.nodes.items()):
            docs = node.get("mentioned_in_docs", set())
            if document_id in docs:
                docs.discard(document_id)
            # If the entity was only referenced by this document and has no remaining docs
            if not docs and node.get("document_id") == document_id:
                orphaned_entities.append(node.get("name"))
                del self.nodes[key]

        orphaned_set = {n.lower() for n in orphaned_entities if n}
        if orphaned_set:
            self.edges = [
                e for e in self.edges
                if e.get("src", "").lower() not in orphaned_set
                and e.get("tgt", "").lower() not in orphaned_set
            ]

        return {
            "document_id": document_id,
            "deleted_entities": orphaned_entities,
        }

    def upsert_edge(
        self,
        src: str,
        tgt: str,
        relation_type: str,
        properties: Dict[str, Any],
    ) -> None:
        for e in self.edges:
            if (
                e["src"].lower() == src.lower()
                and e["tgt"].lower() == tgt.lower()
                and e["type"] == relation_type
            ):
                e.update(properties)
                return
        self.edges.append(
            {"src": src, "tgt": tgt, "type": relation_type, **properties}
        )

    def get_k_hop_subgraph(
        self, seed_names: List[str], k: int
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        seed_set = {s.lower() for s in seed_names}
        visited = set(seed_set)
        current_frontier = set(seed_set)

        for _ in range(k):
            next_frontier = set()
            for edge in self.edges:
                src_low = edge["src"].lower()
                tgt_low = edge["tgt"].lower()
                if src_low in current_frontier and tgt_low not in visited:
                    next_frontier.add(tgt_low)
                    visited.add(tgt_low)
                elif tgt_low in current_frontier and src_low not in visited:
                    next_frontier.add(src_low)
                    visited.add(src_low)
            current_frontier = next_frontier
            if not current_frontier:
                break

        subgraph_nodes = [
            n for n in self.nodes.values() if n.get("name", "").lower() in visited
        ]
        subgraph_edges = [
            e
            for e in self.edges
            if e["src"].lower() in visited and e["tgt"].lower() in visited
        ]
        return subgraph_nodes, subgraph_edges

    def vector_search(
        self, query_vector: List[float], top_k: int = 10, use_gnn: bool = True
    ) -> List[Dict[str, Any]]:
        results = []
        q = np.array(query_vector, dtype=np.float32)
        norm_q = np.linalg.norm(q) + 1e-9

        for n in self.nodes.values():
            emb = None
            if use_gnn:
                emb = n.get("gnn_embedding") or n.get("embedding")
            else:
                emb = n.get("embedding")

            if emb:
                v = np.array(emb, dtype=np.float32)
                sim = float(np.dot(q, v) / (norm_q * (np.linalg.norm(v) + 1e-9)))
                results.append({
                    "name": n.get("name"),
                    "type": n.get("type", "CONCEPT"),
                    "description": n.get("description", ""),
                    "importance_score": n.get("importance_score", 1.0),
                    "embedding": n.get("embedding"),
                    "gnn_embedding": n.get("gnn_embedding"),
                    "score": sim,
                    "node": n,
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]




class Neo4jClient:
    """
    Manages Neo4j driver lifecycle, constraints, indexes, and session execution.
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "password",
        database: str = "neo4j",
        vector_index_name: str = "entity_embeddings_index",
        embedding_dim: int = 384,
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.vector_index_name = vector_index_name
        self.gnn_vector_index_name = f"{vector_index_name}_gnn"
        self.embedding_dim = embedding_dim
        self.driver: Optional[Driver] = None
        self.in_memory_fallback = InMemoryGraphFallback()
        self._connected = False
        self.connect()

    def connect(self) -> bool:
        """Establishes driver connection to Neo4j if available."""
        if not NEO4J_AVAILABLE:
            logger.warning("neo4j python package not available. Using in-memory graph fallback.")
            self._connected = False
            return False

        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
            )
            # Verify connectivity
            self.driver.verify_connectivity()
            self._connected = True
            logger.info(f"Connected successfully to Neo4j at {self.uri}")
            self.setup_schema_and_indexes()
            return True
        except Exception as e:
            logger.warning(
                f"Could not connect to Neo4j at {self.uri} ({e}). "
                "Operating in in-memory simulation mode."
            )
            self._connected = False
            self.driver = None
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected and self.driver is not None

    def setup_schema_and_indexes(self) -> None:
        """Ensures uniqueness constraints and colocated vector index exist."""
        if not self.is_connected:
            return

        constraints = [
            "CREATE CONSTRAINT entity_name_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
            "CREATE CONSTRAINT doc_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT community_id_unique IF NOT EXISTS FOR (cm:Community) REQUIRE cm.id IS UNIQUE",
        ]

        with self.driver.session(database=self.database) as session:
            for stmt in constraints:
                try:
                    session.run(stmt)
                except Exception as e:
                    logger.debug(f"Constraint creation note: {e}")

            # Create Neo4j Vector Indexes for fast PCST prize calculation
            for idx_name, prop_name in [(self.vector_index_name, "embedding"), (self.gnn_vector_index_name, "gnn_embedding")]:
                try:
                    vector_idx_stmt = f"""
                    CREATE VECTOR INDEX {idx_name} IF NOT EXISTS
                    FOR (e:Entity) ON (e.{prop_name})
                    OPTIONS {{
                      indexConfig: {{
                        `vector.dimensions`: {self.embedding_dim},
                        `vector.similarity_function`: 'cosine'
                      }}
                    }}
                    """
                    session.run(vector_idx_stmt)
                    logger.info(f"Verified Neo4j vector index '{idx_name}' for property '{prop_name}'.")
                except Exception as e:
                    logger.debug(f"Vector index creation note (requires Neo4j 5.11+): {e}")

    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executes a Cypher query with parameters against Neo4j."""
        if not self.is_connected:
            return []

        with self.driver.session(database=self.database) as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def close(self) -> None:
        if self.driver:
            self.driver.close()
            logger.info("Closed Neo4j driver connection.")