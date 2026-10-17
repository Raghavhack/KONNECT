"""
Redis Semantic Cache with Incremental Entity-Level Invalidation.
Implements vector similarity matching and exact graph-node invalidation as specified in Section 5.
"""

import json
import logging
import hashlib
from typing import List, Dict, Any, Optional, Set
import numpy as np

logger = logging.getLogger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False


class InMemoryCacheFallback:
    """In-memory dictionary fallback for standalone operation and testing without Redis."""

    def __init__(self):
        self.entries: Dict[str, Dict[str, Any]] = {}
        self.entity_inverted_index: Dict[str, Set[str]] = {}

    def set(self, key: str, data: Dict[str, Any], cited_entities: List[str]) -> None:
        self.entries[key] = data
        for ent in cited_entities:
            norm_ent = ent.lower()
            if norm_ent not in self.entity_inverted_index:
                self.entity_inverted_index[norm_ent] = set()
            self.entity_inverted_index[norm_ent].add(key)

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        return self.entries

    def evict_keys(self, keys: List[str]) -> int:
        count = 0
        for k in keys:
            if k in self.entries:
                del self.entries[k]
                count += 1
        return count


class SemanticCache:
    """
    Semantic Query-Answer Cache backed by Redis.
    Matches queries by vector cosine similarity and supports graph-driven invalidation.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: Optional[str] = None,
        db: int = 0,
        similarity_threshold: float = 0.92,
        ttl_seconds: int = 86400,
    ):
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        self.client: Optional[Any] = None
        self.fallback = InMemoryCacheFallback()
        self._connected = False
        self._initialize_redis()

    def _initialize_redis(self) -> None:
        if not REDIS_AVAILABLE:
            logger.warning("redis python library not installed. Using in-memory cache fallback.")
            return

        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                socket_timeout=2.0,
                decode_responses=False,
            )
            self.client.ping()
            self._connected = True
            logger.info(f"Connected to Redis semantic cache at {self.host}:{self.port}")
        except Exception as e:
            logger.warning(
                f"Could not connect to Redis at {self.host}:{self.port} ({e}). "
                "Operating in in-memory simulation mode."
            )
            self.client = None
            self._connected = False

    def lookup(
        self, query_embedding: np.ndarray, similarity_threshold: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Scans cached queries and computes cosine similarity with incoming query vector.
        Returns matching answer and citations if similarity exceeds threshold.
        """
        th = similarity_threshold if similarity_threshold is not None else self.similarity_threshold
        norm_q = np.linalg.norm(query_embedding) + 1e-9

        # Case 1: In-memory fallback
        if not self._connected or self.client is None:
            best_match = None
            best_score = -1.0
            for key, data in self.fallback.get_all().items():
                cached_emb = np.array(data["embedding"], dtype=np.float32)
                sim = float(np.dot(query_embedding, cached_emb) / (norm_q * (np.linalg.norm(cached_emb) + 1e-9)))
                if sim > best_score:
                    best_score = sim
                    best_match = data

            if best_match and best_score >= th:
                logger.info(f"Semantic Cache Hit! Similarity: {best_score:.4f} >= {th}")
                return best_match
            return None

        # Case 2: Redis cache scanning
        try:
            # Query keys under prefix 'qcache:*'
            keys = self.client.keys("qcache:*")
            best_match = None
            best_score = -1.0

            for k in keys:
                raw = self.client.get(k)
                if raw:
                    entry = json.loads(raw.decode("utf-8"))
                    cached_emb = np.array(entry["embedding"], dtype=np.float32)
                    sim = float(np.dot(query_embedding, cached_emb) / (norm_q * (np.linalg.norm(cached_emb) + 1e-9)))
                    if sim > best_score:
                        best_score = sim
                        best_match = entry

            if best_match and best_score >= th:
                logger.info(f"Semantic Cache Hit! (Redis) Similarity: {best_score:.4f} >= {th}")
                return best_match
            return None
        except Exception as e:
            logger.warning(f"Error querying Redis semantic cache: {e}")
            return None

    def store(
        self,
        query: str,
        query_embedding: np.ndarray,
        answer: str,
        citations: List[Dict[str, Any]],
        subgraph: Dict[str, Any],
        cited_entity_names: List[str],
    ) -> str:
        """
        Stores query-answer pair in cache and updates entity -> cache key inverted index.
        """
        cache_id = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
        key = f"qcache:{cache_id}"

        payload = {
            "cache_id": cache_id,
            "query": query,
            "embedding": query_embedding.tolist(),
            "answer": answer,
            "citations": citations,
            "subgraph": subgraph,
            "cited_entities": cited_entity_names,
        }

        # Save to fallback
        self.fallback.set(key, payload, cited_entity_names)

        if self._connected and self.client is not None:
            try:
                # Store cache entry
                self.client.setex(key, self.ttl_seconds, json.dumps(payload))
                # Store inverted index entries for fast invalidation
                for ent in cited_entity_names:
                    idx_key = f"ent_cache:{ent.lower()}"
                    self.client.sadd(idx_key, key)
                    self.client.expire(idx_key, self.ttl_seconds)
            except Exception as e:
                logger.warning(f"Error storing entry into Redis semantic cache: {e}")

        return key

    def invalidate_for_entities(self, entity_names: List[str]) -> List[str]:
        """
        INCREMENTAL CACHE INVALIDATION (Section 5 Requirement).
        Evicts all cached query answers whose cited subgraph nodes overlap
        with the updated entities.
        """
        if not entity_names:
            return []

        evicted_keys: Set[str] = set()

        # Evict from in-memory fallback
        for ent in entity_names:
            norm_ent = ent.lower()
            if norm_ent in self.fallback.entity_inverted_index:
                keys_to_evict = list(self.fallback.entity_inverted_index[norm_ent])
                self.fallback.evict_keys(keys_to_evict)
                evicted_keys.update(keys_to_evict)
                del self.fallback.entity_inverted_index[norm_ent]

        # Evict from Redis
        if self._connected and self.client is not None:
            try:
                for ent in entity_names:
                    idx_key = f"ent_cache:{ent.lower()}"
                    keys = self.client.smembers(idx_key)
                    if keys:
                        for k in keys:
                            k_str = k.decode("utf-8") if isinstance(k, bytes) else k
                            self.client.delete(k_str)
                            evicted_keys.add(k_str)
                        self.client.delete(idx_key)
            except Exception as e:
                logger.warning(f"Error during Redis cache invalidation: {e}")

        logger.info(
            f"Incremental Cache Invalidation: Evicted {len(evicted_keys)} entries citing updated entities."
        )
        return list(evicted_keys)
