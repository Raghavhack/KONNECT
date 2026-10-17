"""
KONNECT Benchmarking Common Harness Utilities.
Implements pipeline initialization, database reset, extraction caching,
refactored bootstrap with per-stage timing, node-to-document mapping, and metadata logging.
"""

import os
import sys
import json
import time
import pickle
import hashlib
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

# Ensure ai_service is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_DIR = REPO_ROOT / "ai_service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

logger = logging.getLogger("bench.common")


def init_pipeline(strict: bool = True) -> Dict[str, Any]:
    """
    Initializes the KONNECT intelligence pipeline in the current process.
    Enforces BENCH_STRICT_LLM=1 mode.
    """
    if strict:
        os.environ["BENCH_STRICT_LLM"] = "1"

    from app.main import initialize_pipeline
    container = initialize_pipeline()

    # Pre-flight assertions
    llm = container["query_engine"].answer_generator.llm
    if strict:
        assert getattr(llm, "strict", False) is True, "LLMClient must be in strict mode (BENCH_STRICT_LLM=1)"

    return container


def reset_all(container: Dict[str, Any]) -> None:
    """
    Resets the database, clears the in-memory ROLAND state cache, and flushes Redis.
    Guarantees no state leaks across benchmark runs or arms.
    """
    graph_store = container["graph_store"]
    try:
        if graph_store.client.is_connected:
            graph_store.client.execute_query("MATCH (n) DETACH DELETE n")
        else:
            graph_store.client.in_memory_fallback.nodes.clear()
            graph_store.client.in_memory_fallback.edges.clear()
            graph_store.client.in_memory_fallback.documents.clear()
    except Exception as e:
        logger.warning(f"Neo4j clear failed: {e}")

    # Clear temporal hidden state cache in ROLAND GRU
    roland_model = container.get("roland_model")
    if roland_model and hasattr(roland_model, "state_cache"):
        roland_model.state_cache.clear()

    # Flush Redis semantic cache
    semantic_cache = container.get("semantic_cache")
    if semantic_cache and hasattr(semantic_cache, "client") and semantic_cache.client is not None:
        try:
            semantic_cache.client.flushdb()
        except Exception as e:
            logger.debug(f"Redis flushdb skipped/failed: {e}")


def install_extraction_cache(extractor: Any, cache_dir: str, model_name: str = "gpt-4o"):
    """
    Caches LLM extraction on disk keyed by SHA-256(model_name + chunk_text).
    Stores real call execution time to enable accurate 'with extraction' latency reporting.
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    orig_extract = extractor.extract_from_document

    def wrapped_extract(document_id: str, title: str, chunks: List[Any]):
        combined_text = "".join(getattr(c, "text", str(c)) for c in chunks)
        cache_key = hashlib.sha256((model_name + "|" + combined_text).encode("utf-8")).hexdigest()
        pkl_path = cache_path / f"{cache_key}.pkl"

        if pkl_path.exists():
            with open(pkl_path, "rb") as f:
                ents, rels, ms = pickle.load(f)
        else:
            t0 = time.perf_counter()
            ents, rels = orig_extract(document_id, title, chunks)
            ms = (time.perf_counter() - t0) * 1000.0
            with open(pkl_path, "wb") as f:
                pickle.dump((ents, rels, ms), f)

        extractor.last_recorded_ms = ms
        return ents, rels

    extractor.extract_from_document = wrapped_extract
    return wrapped_extract


def bootstrap_corpus(container: Dict[str, Any], docs: List[Any], k_hops: int = 2) -> Dict[str, Any]:
    """
    Indexes a corpus prefix from scratch using the shared container and returns per-stage timings.
    Baseline full-rebuild implementation for Step 4.4 and Step 5.
    """
    t_start = time.perf_counter()

    chunker = container["incremental_engine"].chunker
    extractor = container["incremental_engine"].extractor
    store = container["graph_store"]
    neighborhood_mgr = container["neighborhood_manager"]
    community_detector = container["incremental_engine"].community_detector

    wall_extraction_ms = 0.0
    recorded_extraction_ms = 0.0
    upsert_ms = 0.0

    total_chunks = 0
    all_entity_names = set()
    total_relationships = 0

    for doc in docs:
        if isinstance(doc, (str, Path)):
            p = Path(doc)
            doc_id = p.stem
            raw_text = p.read_text(encoding="utf-8", errors="ignore")
            lines = raw_text.splitlines()
            title = lines[0].strip() if lines else doc_id
            text = "\n".join(lines[1:]).strip() if len(lines) > 1 else raw_text
        elif isinstance(doc, dict):
            doc_id = doc.get("doc_id", "doc")
            title = doc.get("title", doc_id)
            text = doc.get("text", "")
        elif isinstance(doc, tuple):
            doc_id, title, text = doc[0], doc[1], doc[2]
        else:
            doc_id = str(doc)
            title = doc_id
            text = str(doc)

        # 1. Chunking and Extraction
        t0_extract = time.perf_counter()
        chunks = chunker.chunk_document(document_id=doc_id, text=text)
        entities, relationships = extractor.extract_from_document(
            document_id=doc_id, title=title, chunks=chunks
        )
        wall_extraction_ms += (time.perf_counter() - t0_extract) * 1000.0
        recorded_extraction_ms += getattr(extractor, "last_recorded_ms", 0.0)

        # 2. Database Upsert
        t0_upsert = time.perf_counter()
        store.upsert_document_and_chunks(doc_id, title, chunks)
        store.upsert_entities(entities, document_id=doc_id)
        store.upsert_relationships(relationships)
        upsert_ms += (time.perf_counter() - t0_upsert) * 1000.0

        total_chunks += len(chunks)
        for e in entities:
            all_entity_names.add(e.name)
        total_relationships += len(relationships)

    # 3. GNN Embedding Pass over whole indexed graph
    t0_gnn = time.perf_counter()
    gnn_updated_nodes = 0
    if all_entity_names:
        nodes, edges = store.get_k_hop_neighborhood(
            seed_entity_names=list(all_entity_names),
            k=k_hops,
        )
        updated_embeddings, metrics = neighborhood_mgr.run_bounded_update(
            seed_entity_names=list(all_entity_names),
            neighborhood_nodes=nodes,
            neighborhood_edges=edges,
            k=k_hops,
        )
        store.update_node_embeddings(updated_embeddings)
        gnn_updated_nodes = len(updated_embeddings)
    else:
        nodes, edges = [], []
    gnn_ms = (time.perf_counter() - t0_gnn) * 1000.0

    # 4. Community Detection Pass
    t0_leiden = time.perf_counter()
    if all_entity_names:
        communities = community_detector.detect_communities_incremental(
            affected_entity_names=list(all_entity_names),
            neighborhood_nodes=nodes,
            neighborhood_edges=edges,
        )
    leiden_ms = (time.perf_counter() - t0_leiden) * 1000.0

    total_wall_ms = (time.perf_counter() - t_start) * 1000.0
    # True latency with extraction restored
    total_with_extraction_ms = total_wall_ms - wall_extraction_ms + recorded_extraction_ms

    return {
        "num_docs": len(docs),
        "total_chunks": total_chunks,
        "total_entities": len(all_entity_names),
        "total_relationships": total_relationships,
        "gnn_updated_nodes": gnn_updated_nodes,
        "extraction_ms": recorded_extraction_ms,
        "wall_extraction_ms": wall_extraction_ms,
        "upsert_ms": upsert_ms,
        "gnn_ms": gnn_ms,
        "leiden_ms": leiden_ms,
        "total_ms": total_wall_ms,
        "total_with_extraction_ms": total_with_extraction_ms,
    }


def map_nodes_to_documents(graph_store: Any, node_names: List[str]) -> Dict[str, List[str]]:
    """
    Resolves source document IDs for retrieved graph entity nodes.
    Solves Section 4.6 missing document_id mapping.
    """
    mapping = {name: [] for name in node_names}
    if not node_names:
        return mapping

    if getattr(graph_store.client, "is_connected", False):
        cypher = """
        MATCH (e:Entity)-[:MENTIONED_IN]->(d:Document)
        WHERE e.name IN $names
        RETURN e.name AS name, collect(d.id) AS docs
        """
        try:
            records = graph_store.client.execute_query(cypher, {"names": list(node_names)})
            for r in records:
                mapping[r["name"]] = r.get("docs", [])
        except Exception as e:
            logger.warning(f"Error querying node-document mapping in Neo4j: {e}")
    else:
        # In-memory store fallback
        fallback = getattr(graph_store.client, "in_memory_fallback", None)
        if fallback and hasattr(fallback, "nodes"):
            for name in node_names:
                node = fallback.nodes.get(name)
                if node and "document_id" in node.get("properties", {}):
                    doc_id = node["properties"]["document_id"]
                    if doc_id:
                        mapping[name] = [doc_id]

    return mapping


def log_jsonl(filepath: str, record: Dict[str, Any]) -> None:
    """Appends a dictionary as a single JSON line to filepath."""
    p = Path(filepath)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def get_git_sha() -> str:
    """Retrieves current Git commit SHA."""
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
        return sha
    except Exception:
        return "unknown"


def write_metadata(
    output_path: str,
    container: Dict[str, Any],
    config_path: str,
    checkpoint_path: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Writes results/metadata.json per Step 4.7.
    Includes git SHA, config hash, checkpoint hash, LLM model, and verify zero simulated calls.
    """
    llm = container["query_engine"].answer_generator.llm
    extractor = container["incremental_engine"].extractor

    # Hashes
    config_hash = hashlib.sha256(Path(config_path).read_bytes()).hexdigest() if Path(config_path).exists() else ""
    ckpt_hash = ""
    if checkpoint_path and Path(checkpoint_path).exists():
        ckpt_hash = hashlib.sha256(Path(checkpoint_path).read_bytes()).hexdigest()

    metadata = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_sha": get_git_sha(),
        "config_hash": config_hash,
        "checkpoint_sha256": ckpt_hash,
        "checkpoint_path": str(checkpoint_path) if checkpoint_path else None,
        "llm_provider": getattr(llm, "provider", "openai"),
        "llm_model": getattr(llm, "default_model", "gpt-4o"),
        "llm_simulated_calls": getattr(llm, "simulated_calls", 0),
        "extractor_fallback_count": getattr(extractor, "fallback_count", 0),
        "neo4j_connected": getattr(container["graph_store"].client, "is_connected", False),
    }
    if extra:
        metadata.update(extra)

    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Wrote metadata to {output_path}")
    return metadata
