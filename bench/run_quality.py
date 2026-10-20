"""
Headline Metric 2: Answer Quality Benchmark CLI.
Executes the four retrieval arms (A: Naive Chunk RAG, B: Top-k Entities, C: PCST + GNN, D: PCST + Text)
over 50 2WikiMultihopQA eval questions with frozen retrieval parameters and context budgets.
"""

import os
import sys
import json
import time
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_DIR = REPO_ROOT / "ai_service"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(AI_SERVICE_DIR))

from bench.common import (
    init_pipeline,
    reset_all,
    install_extraction_cache,
    bootstrap_corpus,
    map_nodes_to_documents,
    log_jsonl,
    write_metadata,
)
from app.preprocessing.chunker import SemanticChunker, Chunk
from app.retrieval.context_builder import ContextBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_quality")


def build_chunk_index(
    docs_dir: Path,
    slugs: List[str],
    chunker: SemanticChunker,
    embedder: Any,
) -> Tuple[List[Chunk], np.ndarray]:
    """
    Builds the Naive RAG chunk index for Arm A.
    Chunks all documents and batches embeddings into a single dense matrix.
    """
    all_chunks: List[Chunk] = []
    logger.info(f"Chunking {len(slugs)} documents for Arm A Naive RAG...")

    for slug in slugs:
        p = docs_dir / f"{slug}.txt"
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        chunks = chunker.chunk_document(document_id=slug, text=text)
        all_chunks.extend(chunks)

    logger.info(f"Created {len(all_chunks)} chunks. Embedding chunks in batches...")
    chunk_texts = [c.text for c in all_chunks]
    batch_size = 64
    emb_list = []
    for i in range(0, len(chunk_texts), batch_size):
        batch = chunk_texts[i:i + batch_size]
        embs = embedder.embed_batch(batch)
        emb_list.append(embs)

    chunk_embeddings = np.vstack(emb_list).astype(np.float32)
    # Unit-normalize chunk embeddings
    norms = np.linalg.norm(chunk_embeddings, axis=1, keepdims=True) + 1e-9
    chunk_embeddings = chunk_embeddings / norms

    logger.info(f"Arm A index ready: {len(all_chunks)} chunks, embedding shape {chunk_embeddings.shape}")
    return all_chunks, chunk_embeddings


def retrieve_arm_a(
    query_text: str,
    all_chunks: List[Chunk],
    chunk_embeddings: np.ndarray,
    embedder: Any,
    top_k: int = 10,
    max_context_words: int = 1100,
) -> Tuple[str, List[Dict[str, Any]], List[str], int, int]:
    """
    Arm A: Naive chunk RAG retrieval.
    Ranks chunks by cosine similarity, joins texts, and wraps retrieved nodes for citation parsing.
    """
    q_emb = embedder.embed_text(query_text).astype(np.float32)
    q_norm = q_emb / (np.linalg.norm(q_emb) + 1e-9)

    scores = np.dot(chunk_embeddings, q_norm)
    top_indices = np.argsort(scores)[::-1][:top_k]
    top_chunks = [all_chunks[idx] for idx in top_indices]

    context_parts = []
    retrieved_nodes = []
    retrieved_docs_set = []

    for c in top_chunks:
        context_parts.append(f"[{c.document_id}] {c.text}")
        retrieved_nodes.append({
            "name": c.document_id,
            "id": c.chunk_id,
            "description": c.text[:120],
            "importance_score": 1.0,
            "document_id": c.document_id,
        })
        if c.document_id not in retrieved_docs_set:
            retrieved_docs_set.append(c.document_id)

    raw_context = "\n\n".join(context_parts)
    words = raw_context.split()
    context = " ".join(words[:max_context_words])

    return context, retrieved_nodes, retrieved_docs_set, len(top_chunks), 0


def retrieve_arm_b(
    query_text: str,
    graph_store: Any,
    embedder: Any,
    top_k: int = 10,
    max_context_words: int = 1100,
) -> Tuple[str, List[Dict[str, Any]], List[str], int, int]:
    """
    Arm B: Top-k entity nodes (no graph structure).
    Queries vector index for top entities and builds context without graph edges.
    """
    q_emb = embedder.embed_text(query_text).tolist()
    vector_candidates = graph_store.search_vector_index(q_emb, top_k=top_k, use_gnn=False)

    nodes = []
    prizes = {}
    for c in vector_candidates:
        n = c.get("node") if isinstance(c.get("node"), dict) else c
        nodes.append(n)
        name = n.get("name", "")
        prizes[name] = float(c.get("score", 1.0))

    subgraph = {"nodes": nodes, "edges": [], "prizes": prizes}
    raw_context = ContextBuilder.build_llm_context(subgraph)
    context = " ".join(raw_context.split()[:max_context_words])

    node_names = [n.get("name") for n in nodes if n.get("name")]
    node_to_docs = map_nodes_to_documents(graph_store, node_names)
    retrieved_docs = list(dict.fromkeys(d for docs in node_to_docs.values() for d in docs))

    return context, nodes, retrieved_docs, len(nodes), 0


def retrieve_arm_c_or_d(
    query_text: str,
    pcst_retriever: Any,
    graph_store: Any,
    use_gnn: bool,
    top_k: int = 10,
    cost_weight: float = 0.15,
    prize_threshold: float = 0.40,
    max_context_words: int = 1100,
) -> Tuple[str, List[Dict[str, Any]], List[str], int, int]:
    """
    Arms C and D: PCST Subgraph Retrieval.
    Arm C: use_gnn=True (full system with GNN dynamic embeddings).
    Arm D: use_gnn=False (PCST over static text embeddings, isolating GNN contribution).
    """
    subgraph = pcst_retriever.retrieve_subgraph(
        query=query_text,
        k_hop_seed_top_k=top_k,
        cost_weight=cost_weight,
        threshold=prize_threshold,
        use_gnn=use_gnn,
    )

    nodes = subgraph.get("nodes", [])
    edges = subgraph.get("edges", [])

    raw_context = ContextBuilder.build_llm_context(subgraph)
    context = " ".join(raw_context.split()[:max_context_words])

    node_names = [n.get("name") for n in nodes if n.get("name")]
    node_to_docs = map_nodes_to_documents(graph_store, node_names)
    retrieved_docs = list(dict.fromkeys(d for docs in node_to_docs.values() for d in docs))

    return context, nodes, retrieved_docs, len(nodes), len(edges)


def run_sensitivity_sweep(
    container: Dict[str, Any],
    questions: List[Dict[str, Any]],
    out_path: Path,
) -> Dict[str, Any]:
    """
    Runbook Step 6.5: Sensitivity sweep, retrieval only (no LLM generation cost).
    Varies cost_weight in {0.05, 0.15, 0.30} and prize_threshold in {0.30, 0.40, 0.50} for Arms C and D.
    Reports document recall and all-gold-found.
    """
    logger.info("=== Running Step 6.5 PCST Sensitivity Sweep (Retrieval-Only) ===")
    pcst_retriever = container["pcst_retriever"]
    graph_store = container["graph_store"]

    cost_weights = [0.05, 0.15, 0.30]
    prize_thresholds = [0.30, 0.40, 0.50]
    sweep_results = []

    for cw in cost_weights:
        for th in prize_thresholds:
            for use_gnn, arm_label in [(True, "Arm_C"), (False, "Arm_D")]:
                recalls = []
                all_found_list = []
                subgraph_sizes = []

                for q in questions:
                    gold_docs = set(q.get("gold_docs", []))
                    subgraph = pcst_retriever.retrieve_subgraph(
                        query=q["question"],
                        k_hop_seed_top_k=10,
                        cost_weight=cw,
                        threshold=th,
                        use_gnn=use_gnn,
                    )
                    nodes = subgraph.get("nodes", [])
                    node_names = [n.get("name") for n in nodes if n.get("name")]
                    node_to_docs = map_nodes_to_documents(graph_store, node_names)
                    retrieved_docs = set(d for docs in node_to_docs.values() for d in docs)

                    recall = len(gold_docs & retrieved_docs) / max(1, len(gold_docs)) if gold_docs else 1.0
                    all_found = 1.0 if gold_docs and gold_docs.issubset(retrieved_docs) else 0.0

                    recalls.append(recall)
                    all_found_list.append(all_found)
                    subgraph_sizes.append(len(nodes))

                mean_recall = float(np.mean(recalls))
                mean_all_found = float(np.mean(all_found_list))
                med_nodes = float(np.median(subgraph_sizes))

                entry = {
                    "arm": arm_label,
                    "cost_weight": cw,
                    "prize_threshold": th,
                    "mean_document_recall": round(mean_recall, 4),
                    "all_gold_found_share": round(mean_all_found, 4),
                    "median_nodes": med_nodes,
                }
                sweep_results.append(entry)
                logger.info(
                    f"Sensitivity [{arm_label}] cost={cw}, th={th} -> "
                    f"Recall: {mean_recall*100:.1f}%, All-Gold: {mean_all_found*100:.1f}%, Median Nodes: {med_nodes}"
                )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sweep_results, f, indent=2)

    logger.info(f"Sensitivity sweep results saved to {out_path}")
    return {"sensitivity_sweep": sweep_results}


def main():
    parser = argparse.ArgumentParser(description="Run KONNECT Headline Metric 2 Quality Benchmark")
    parser.add_argument("--split", type=str, default="eval", choices=["eval", "workspace"], help="Split to run on")
    parser.add_argument("--arms", nargs="+", default=["A", "B", "C", "D"], help="Retrieval arms to execute")
    parser.add_argument("--k", type=int, default=10, help="Top-k retrieval / seed parameter")
    parser.add_argument("--out", type=str, default="results/quality_midsem.jsonl", help="Output JSONL path")
    parser.add_argument("--config", type=str, default="bench/config.json", help="Path to config.json")
    parser.add_argument("--sensitivity", action="store_true", help="Execute Step 6.5 PCST sensitivity sweep")
    args = parser.parse_args()

    config_path = REPO_ROOT / args.config
    config = json.load(open(config_path, encoding="utf-8"))

    cost_weight = float(config.get("pcst_cost_weight", 0.15))
    prize_threshold = float(config.get("pcst_prize_threshold", 0.40))
    max_context_words = int(config.get("max_context_words", 1100))
    cache_dir = REPO_ROOT / config.get("cache_dir", "data/cache/extraction_cache")

    # Select splits
    if args.split == "eval":
        docs_dir = REPO_ROOT / "data" / "splits" / "eval_docs"
        order_path = REPO_ROOT / "data" / "splits" / "corpus_order.json"
        questions_path = REPO_ROOT / "data" / "splits" / "eval_questions.json"
    else:
        docs_dir = REPO_ROOT / "data" / "splits" / "workspace_docs"
        order_path = None
        questions_path = REPO_ROOT / "data" / "splits" / "workspace_questions.json"

    questions = json.load(open(questions_path, encoding="utf-8"))

    if order_path and order_path.exists():
        corpus_slugs = json.load(open(order_path, encoding="utf-8"))
    else:
        corpus_slugs = [p.stem for p in sorted(docs_dir.glob("*.txt"))]

    logger.info(f"Loaded {len(questions)} {args.split} questions and {len(corpus_slugs)} corpus documents.")

    logger.info("Initializing pipeline (enforcing strict LLM mode)...")
    container = init_pipeline(strict=True)

    # Install extraction cache
    extractor = container["incremental_engine"].extractor
    install_extraction_cache(extractor, str(cache_dir), config.get("llm_model", "gpt-4o"))

    # Check if graph index is built; if not, build it once
    graph_store = container["graph_store"]
    num_nodes = len(graph_store.client.in_memory_fallback.nodes) if not graph_store.client.is_connected else 1
    if num_nodes == 0:
        logger.info(f"Graph is empty. Bootstrapping full corpus of {len(corpus_slugs)} documents...")
        doc_files = [docs_dir / f"{s}.txt" for s in corpus_slugs if (docs_dir / f"{s}.txt").exists()]
        bootstrap_corpus(container, doc_files, k_hops=config.get("k_hops", 2))
        logger.info("Corpus bootstrap complete.")

    # Optional Sensitivity Sweep
    if args.sensitivity:
        sweep_out = REPO_ROOT / "results" / "sensitivity_sweep.json"
        run_sensitivity_sweep(container, questions, sweep_out)

    # Build Naive RAG chunk index if Arm A is included
    all_chunks = None
    chunk_embeddings = None
    if "A" in args.arms:
        chunker = SemanticChunker(
            chunk_size=container["settings"].CHUNK_SIZE,
            chunk_overlap=container["settings"].CHUNK_OVERLAP,
        )
        all_chunks, chunk_embeddings = build_chunk_index(
            docs_dir=docs_dir,
            slugs=corpus_slugs,
            chunker=chunker,
            embedder=container["embedder"],
        )

    out_file = REPO_ROOT / args.out
    out_file.parent.mkdir(parents=True, exist_ok=True)
    if out_file.exists():
        out_file.unlink()

    embedder = container["embedder"]
    pcst_retriever = container["pcst_retriever"]
    generator = container["query_engine"].answer_generator

    logger.info(f"Starting Quality Benchmark across arms {args.arms} on {len(questions)} questions...")
    total_runs = len(questions) * len(args.arms)
    run_idx = 0

    for q_item in questions:
        qid = q_item["_id"]
        q_text = q_item["question"]
        gold_answer = q_item.get("answer", "")
        gold_docs = q_item.get("gold_docs", [])
        q_type = q_item.get("type", "unknown")

        for arm in args.arms:
            run_idx += 1
            t_ret0 = time.perf_counter()

            if arm == "A":
                context, retrieved_nodes, retrieved_docs, n_nodes, n_edges = retrieve_arm_a(
                    query_text=q_text,
                    all_chunks=all_chunks,
                    chunk_embeddings=chunk_embeddings,
                    embedder=embedder,
                    top_k=args.k,
                    max_context_words=max_context_words,
                )
            elif arm == "B":
                context, retrieved_nodes, retrieved_docs, n_nodes, n_edges = retrieve_arm_b(
                    query_text=q_text,
                    graph_store=graph_store,
                    embedder=embedder,
                    top_k=args.k,
                    max_context_words=max_context_words,
                )
            elif arm == "C":
                context, retrieved_nodes, retrieved_docs, n_nodes, n_edges = retrieve_arm_c_or_d(
                    query_text=q_text,
                    pcst_retriever=pcst_retriever,
                    graph_store=graph_store,
                    use_gnn=True,
                    top_k=args.k,
                    cost_weight=cost_weight,
                    prize_threshold=prize_threshold,
                    max_context_words=max_context_words,
                )
            elif arm == "D":
                context, retrieved_nodes, retrieved_docs, n_nodes, n_edges = retrieve_arm_c_or_d(
                    query_text=q_text,
                    pcst_retriever=pcst_retriever,
                    graph_store=graph_store,
                    use_gnn=False,
                    top_k=args.k,
                    cost_weight=cost_weight,
                    prize_threshold=prize_threshold,
                    max_context_words=max_context_words,
                )
            else:
                raise ValueError(f"Unknown retrieval arm: {arm}")

            retrieval_ms = (time.perf_counter() - t_ret0) * 1000.0

            # Answer Generation (Shared Tail)
            t_gen0 = time.perf_counter()
            answer, raw_cites = generator.generate_answer_with_citations(
                query=q_text,
                context_str=context,
                retrieved_nodes=retrieved_nodes,
            )
            generation_ms = (time.perf_counter() - t_gen0) * 1000.0

            # Map citations to document IDs
            if arm == "A":
                cited_docs = list(dict.fromkeys(
                    c.get("document_id") for c in raw_cites if c.get("document_id")
                ))
            else:
                cited_entity_names = [c.get("entity_name") for c in raw_cites if c.get("entity_name")]
                cited_doc_map = map_nodes_to_documents(graph_store, cited_entity_names)
                cited_docs = list(dict.fromkeys(
                    d for dlist in cited_doc_map.values() for d in dlist
                ))

            record = {
                "qid": qid,
                "arm": arm,
                "type": q_type,
                "question": q_text,
                "gold_answer": gold_answer,
                "gold_docs": gold_docs,
                "retrieved_docs": retrieved_docs,
                "n_nodes": n_nodes,
                "n_edges": n_edges,
                "context_words": len(context.split()),
                "context_chars": len(context),
                "context": context,
                "answer": answer,
                "cited_docs": cited_docs,
                "retrieval_ms": round(retrieval_ms, 2),
                "generation_ms": round(generation_ms, 2),
            }

            log_jsonl(str(out_file), record)

            if run_idx % 20 == 0 or run_idx == total_runs:
                logger.info(
                    f"Progress [{run_idx}/{total_runs}] QID: {qid[:10]} Arm: {arm} "
                    f"Nodes: {n_nodes} Retrieved Docs: {len(retrieved_docs)} Ret: {retrieval_ms:.1f}ms"
                )

    # Write metadata
    meta_path = REPO_ROOT / "results" / "metadata.json"
    ckpt_path = REPO_ROOT / "ai_service" / "models" / "roland_midsem.pt"
    write_metadata(
        output_path=str(meta_path),
        container=container,
        config_path=str(config_path),
        checkpoint_path=str(ckpt_path) if ckpt_path.exists() else None,
        extra={
            "quality_split": args.split,
            "arms": args.arms,
            "pcst_cost_weight": cost_weight,
            "pcst_prize_threshold": prize_threshold,
            "max_context_words": max_context_words,
            "total_questions": len(questions),
        },
    )

    logger.info(f"Quality benchmark complete! Results logged to {out_file}")


if __name__ == "__main__":
    main()
