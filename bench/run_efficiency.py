"""
Headline Metric 1: Update Efficiency Benchmark CLI.
Compares incremental updates (bounded k-hop ROLAND GRU) against full corpus rebuilds
across corpus sizes N in {50, 150, 300, 500} and k sweep in {1, 2, 3}.
Calculates speedup, node re-embedding shares, and parity metrics.
"""

import os
import sys
import json
import time
import argparse
import logging
import statistics
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "ai_service"))

from bench.common import (
    init_pipeline,
    reset_all,
    install_extraction_cache,
    bootstrap_corpus,
    log_jsonl,
    write_metadata,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_efficiency")


def export_graph_state(graph_store: Any) -> Dict[str, Any]:
    """Exports current graph nodes, edges, and embeddings for parity verification."""
    client = graph_store.client
    nodes = {}
    edges = set()

    if getattr(client, "is_connected", False):
        # Fetch nodes
        c_nodes = "MATCH (n:Entity) RETURN n.name AS name, n.embedding AS emb, n.gnn_embedding AS gnn_emb"
        records = client.execute_query(c_nodes)
        for r in records:
            nodes[r["name"]] = {
                "embedding": r.get("emb"),
                "gnn_embedding": r.get("gnn_emb") or r.get("emb"),
            }
        # Fetch edges
        c_edges = "MATCH (s:Entity)-[r]->(t:Entity) RETURN s.name AS src, t.name AS tgt, type(r) AS type"
        r_edges = client.execute_query(c_edges)
        for r in r_edges:
            edges.add((r["src"].lower(), r["tgt"].lower(), r["type"].upper()))
    else:
        # In-memory store
        fallback = getattr(client, "in_memory_fallback", None)
        if fallback:
            for key, data in fallback.nodes.items():
                node_name = data.get("name", key.replace("Entity:", ""))
                emb = data.get("embedding")
                gnn_emb = data.get("gnn_embedding") or emb
                nodes[node_name] = {"embedding": emb, "gnn_embedding": gnn_emb}
            for e in fallback.edges:
                edges.add((e.get("src", "").lower(), e.get("tgt", "").lower(), e.get("type", "").upper()))

    return {"nodes": nodes, "edges": list(edges)}


def calculate_parity(graph_inc: Dict[str, Any], graph_reb: Dict[str, Any]) -> Dict[str, float]:
    """Calculates node Jaccard, edge Jaccard, and mean GNN embedding cosine similarity."""
    nodes_inc = set(graph_inc["nodes"].keys())
    nodes_reb = set(graph_reb["nodes"].keys())

    node_union = len(nodes_inc | nodes_reb)
    node_jaccard = len(nodes_inc & nodes_reb) / max(1, node_union)

    edges_inc = set(tuple(e) for e in graph_inc["edges"])
    edges_reb = set(tuple(e) for e in graph_reb["edges"])

    edge_union = len(edges_inc | edges_reb)
    edge_jaccard = len(edges_inc & edges_reb) / max(1, edge_union)

    # Embedding cosine over shared nodes
    shared_nodes = nodes_inc & nodes_reb
    cos_sims = []
    for n in shared_nodes:
        e1 = graph_inc["nodes"][n].get("gnn_embedding")
        e2 = graph_reb["nodes"][n].get("gnn_embedding")
        if e1 is not None and e2 is not None and len(e1) > 0 and len(e2) > 0:
            v1 = np.array(e1, dtype=np.float32)
            v2 = np.array(e2, dtype=np.float32)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            if norm1 > 1e-6 and norm2 > 1e-6:
                cos_sims.append(float(np.dot(v1, v2) / (norm1 * norm2)))

    mean_cos = float(np.mean(cos_sims)) if cos_sims else 1.0

    return {
        "node_jaccard": round(node_jaccard, 4),
        "edge_jaccard": round(edge_jaccard, 4),
        "mean_gnn_cosine": round(mean_cos, 4),
        "shared_nodes_count": len(shared_nodes),
    }


def run_size_experiment(
    container: Dict[str, Any],
    N: int,
    eval_docs_dir: Path,
    corpus_order: List[str],
    edits: List[Dict[str, Any]],
    k_hops: int = 2,
    repeats: int = 3,
) -> Dict[str, Any]:
    """Executes the efficiency benchmark for a specific corpus size N."""
    logger.info(f"=== Running Efficiency Benchmark for N = {N} (k={k_hops}) ===")

    selected_slugs = corpus_order[:N]
    prefix_docs = [eval_docs_dir / f"{s}.txt" for s in selected_slugs]

    # 1. Reset and initial bootstrap build
    reset_all(container)
    init_timings = bootstrap_corpus(container, prefix_docs, k_hops=k_hops)
    logger.info(f"Initial bootstrap build (N={N}): {init_timings['total_ms']:.1f}ms")

    # 2. Warm-up edits (3 edits re-ingesting unchanged text)
    engine = container["incremental_engine"]
    for i in range(min(3, len(selected_slugs))):
        warmup_slug = selected_slugs[i]
        p = eval_docs_dir / f"{warmup_slug}.txt"
        text = p.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        title = lines[0].strip() if lines else warmup_slug
        engine.process_document_update(
            document_id=warmup_slug,
            title=title,
            content=text,
            k_hops=k_hops,
            trigger_leiden=True,
            invalidate_cache=True,
        )

    # 3. Apply 20 edits incrementally
    inc_latencies_total = []
    inc_latencies_with_extraction = []
    inc_latencies_no_extraction = []
    reembedded_counts = []
    edit_stage_splits = {"preprocessing": [], "extraction": [], "upsert": [], "roland_gru": []}

    edited_corpus_docs: Dict[str, Tuple[str, str]] = {}
    for s in selected_slugs:
        p = eval_docs_dir / f"{s}.txt"
        t = p.read_text(encoding="utf-8", errors="ignore")
        lines = t.splitlines()
        title = lines[0].strip() if lines else s
        edited_corpus_docs[s] = (title, t)

    for edit_idx, edit in enumerate(edits):
        doc_id = edit["doc_id"]
        title = edit["title"]
        new_text = edit["new_text"]

        # Track edited content for full rebuild comparison
        if doc_id in edited_corpus_docs:
            edited_corpus_docs[doc_id] = (title, new_text)

        # Before call, record node count
        total_nodes = len(container["graph_store"].client.in_memory_fallback.nodes) if not container["graph_store"].client.is_connected else len(export_graph_state(container["graph_store"])["nodes"])

        res = engine.process_document_update(
            document_id=doc_id,
            title=title,
            content=new_text,
            k_hops=k_hops,
            trigger_leiden=True,
            invalidate_cache=True,
        )

        prep_ms = res.get("preprocessing_time_ms", 0.0)
        wall_ext_ms = res.get("extraction_time_ms", 0.0)
        rec_ext_ms = getattr(engine.extractor, "last_recorded_ms", wall_ext_ms)
        roland_ms = res.get("roland_gru_time_ms", 0.0)
        tot_ms = res.get("total_time_ms", 0.0)

        tot_with_ext = tot_ms - wall_ext_ms + rec_ext_ms
        tot_no_ext = tot_ms - wall_ext_ms

        inc_latencies_total.append(tot_ms)
        inc_latencies_with_extraction.append(tot_with_ext)
        inc_latencies_no_extraction.append(tot_no_ext)
        reembedded_counts.append(res.get("updated_embeddings_count", 0))

        edit_stage_splits["preprocessing"].append(prep_ms)
        edit_stage_splits["extraction"].append(rec_ext_ms)
        edit_stage_splits["roland_gru"].append(roland_ms)

    # Export incremental graph state
    graph_inc = export_graph_state(container["graph_store"])

    # 4. Full rebuild of edited corpus (repeats)
    rebuild_docs = [(s, edited_corpus_docs[s][0], edited_corpus_docs[s][1]) for s in selected_slugs]
    rebuild_latencies_total = []
    rebuild_latencies_with_ext = []
    rebuild_latencies_no_ext = []
    last_rebuild_graph = None

    for rep in range(repeats):
        reset_all(container)
        timings = bootstrap_corpus(container, rebuild_docs, k_hops=k_hops)
        rebuild_latencies_total.append(timings["total_ms"])
        rebuild_latencies_with_ext.append(timings["total_with_extraction_ms"])
        rebuild_latencies_no_ext.append(timings["total_ms"] - timings["wall_extraction_ms"])
        if rep == repeats - 1:
            last_rebuild_graph = export_graph_state(container["graph_store"])

    # 5. Compute metrics
    inc_median_with_ext = statistics.median(inc_latencies_with_extraction)
    inc_p95_with_ext = np.percentile(inc_latencies_with_extraction, 95)
    inc_median_no_ext = statistics.median(inc_latencies_no_extraction)
    inc_p95_no_ext = np.percentile(inc_latencies_no_extraction, 95)

    reb_mean_with_ext = statistics.mean(rebuild_latencies_with_ext)
    reb_std_with_ext = statistics.stdev(rebuild_latencies_with_ext) if len(rebuild_latencies_with_ext) > 1 else 0.0
    reb_mean_no_ext = statistics.mean(rebuild_latencies_no_ext)
    reb_std_no_ext = statistics.stdev(rebuild_latencies_no_ext) if len(rebuild_latencies_no_ext) > 1 else 0.0

    speedup_with_ext = reb_mean_with_ext / max(0.01, inc_median_with_ext)
    speedup_no_ext = reb_mean_no_ext / max(0.01, inc_median_no_ext)

    med_reembedded = statistics.median(reembedded_counts)
    total_graph_nodes = len(graph_inc["nodes"])
    reembedded_share = med_reembedded / max(1, total_graph_nodes)

    parity = calculate_parity(graph_inc, last_rebuild_graph) if last_rebuild_graph else {}

    return {
        "N": N,
        "k_hops": k_hops,
        "repeats": repeats,
        "total_graph_nodes": total_graph_nodes,
        "incremental": {
            "median_with_extraction_ms": round(inc_median_with_ext, 2),
            "p95_with_extraction_ms": round(float(inc_p95_with_ext), 2),
            "median_no_extraction_ms": round(inc_median_no_ext, 2),
            "p95_no_extraction_ms": round(float(inc_p95_no_ext), 2),
            "median_nodes_reembedded": med_reembedded,
            "reembedded_share": round(reembedded_share, 4),
        },
        "full_rebuild": {
            "mean_with_extraction_ms": round(reb_mean_with_ext, 2),
            "std_with_extraction_ms": round(reb_std_with_ext, 2),
            "mean_no_extraction_ms": round(reb_mean_no_ext, 2),
            "std_no_extraction_ms": round(reb_std_no_ext, 2),
        },
        "speedup": {
            "speedup_with_extraction": round(speedup_with_ext, 2),
            "speedup_no_extraction": round(speedup_no_ext, 2),
        },
        "parity": parity,
    }


def main():
    parser = argparse.ArgumentParser(description="Run KONNECT Headline Metric 1 Efficiency Experiments")
    parser.add_argument("--sizes", type=int, nargs="+", default=[50, 150, 300, 500], help="Corpus sizes")
    parser.add_argument("--edits", type=int, default=20, help="Number of edits to apply")
    parser.add_argument("--k", type=int, default=2, help="Neighborhood k-hops")
    parser.add_argument("--repeats", type=int, default=3, help="Rebuild repetitions per size")
    parser.add_argument("--out", type=str, default="results/efficiency_midsem.jsonl", help="Output JSONL path")
    parser.add_argument("--config", type=str, default="bench/config.json", help="Path to config.json")
    args = parser.parse_args()

    config_path = REPO_ROOT / args.config
    config = json.load(open(config_path, encoding="utf-8"))

    cache_dir = REPO_ROOT / config.get("cache_dir", "data/cache/extraction_cache")
    corpus_order_path = REPO_ROOT / "data" / "splits" / "corpus_order.json"
    eval_docs_dir = REPO_ROOT / "data" / "splits" / "eval_docs"
    edits_path = REPO_ROOT / "data" / "splits" / "edits.json"

    corpus_order = json.load(open(corpus_order_path, encoding="utf-8"))
    all_edits = json.load(open(edits_path, encoding="utf-8"))[:args.edits]

    logger.info("Initializing pipeline with strict LLM mode...")
    container = init_pipeline(strict=True)

    # Install extraction cache
    extractor = container["incremental_engine"].extractor
    install_extraction_cache(extractor, str(cache_dir), config.get("llm_model", "gpt-4o"))

    out_file = REPO_ROOT / args.out
    if out_file.exists():
        out_file.unlink()

    results_per_size = []

    # Run for each corpus size
    for size in args.sizes:
        res = run_size_experiment(
            container=container,
            N=size,
            eval_docs_dir=eval_docs_dir,
            corpus_order=corpus_order,
            edits=all_edits,
            k_hops=args.k,
            repeats=args.repeats,
        )
        results_per_size.append(res)
        log_jsonl(str(out_file), res)
        logger.info(
            f"Size N={size}: Speedup={res['speedup']['speedup_with_extraction']}x (with ext), "
            f"{res['speedup']['speedup_no_extraction']}x (no ext), "
            f"Re-embedded share={res['incremental']['reembedded_share']*100:.1f}%, "
            f"Parity node={res['parity'].get('node_jaccard')}, cos={res['parity'].get('mean_gnn_cosine')}"
        )

    # k-hop sweep at N=500 for k in [1, 2, 3]
    if 500 in args.sizes:
        logger.info("=== Running k-Hop Neighborhood Sweep at N=500 (k=1, 2, 3) ===")
        for k_val in [1, 2, 3]:
            res_k = run_size_experiment(
                container=container,
                N=500,
                eval_docs_dir=eval_docs_dir,
                corpus_order=corpus_order,
                edits=all_edits,
                k_hops=k_val,
                repeats=1,
            )
            res_k["experiment_type"] = "k_sweep"
            log_jsonl(str(out_file), res_k)
            logger.info(
                f"k-Sweep k={k_val}: Inc Latency={res_k['incremental']['median_with_extraction_ms']}ms, "
                f"Re-embedded={res_k['incremental']['median_nodes_reembedded']} nodes"
            )

    # Record metadata
    meta_path = REPO_ROOT / "results" / "metadata.json"
    ckpt_path = REPO_ROOT / "ai_service" / "models" / "roland_midsem.pt"
    write_metadata(
        output_path=str(meta_path),
        container=container,
        config_path=str(config_path),
        checkpoint_path=str(ckpt_path) if ckpt_path.exists() else None,
        extra={"efficiency_runs": len(args.sizes)},
    )

    logger.info(f"Efficiency benchmark complete! Output saved to {out_file}")


if __name__ == "__main__":
    main()
