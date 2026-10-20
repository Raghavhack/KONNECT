"""
KONNECT mid-sem benchmark (one script, fixed seeds).

  Metric 1  update latency: incremental edit vs full rebuild, per corpus size
  Metric 2  answer quality: Arms A-D on 2WikiMultihopQA eval questions
              A naive chunk RAG | B top-k nodes | C PCST + GNN embeddings | D PCST + text embeddings

Run from ai_service/ :
    python -m scripts.run_benchmark --stage extract      # optional: fill the extraction cache first
    python -m scripts.run_benchmark --stage efficiency
    python -m scripts.run_benchmark --stage quality
    python -m scripts.run_benchmark --stage all

Reads  : <repo>/data/splits/eval_questions.json, eval_docs/*.txt   (made by make_eval_data.py)
Writes : <repo>/results/*.csv|json|jsonl
Extraction results are cached in ai_service/.bench_cache (keyed by model + prompt + text), together with
the wall time of the REAL LLM call that produced them, so reruns are cheap and latency stays honest.

What is measured / what is not (state this in the report):
  * Graph backend is the in-memory graph (no Neo4j), so latency measures compute, not DB round trips.
  * Leiden community update/summarisation is excluded from both paths (trigger_leiden=False).
  * "LLM ms" is the recorded wall time of the real extraction call (includes entity embedding);
    "non-LLM ms" is measured live (chunking, graph upsert, k-hop, GRU re-embedding, cache invalidation).
"""

import argparse
import csv
import hashlib
import json
import logging
import os
import pickle
import random
import re
import statistics
import string
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

AI_DIR = Path(__file__).resolve().parents[1]
ROOT = AI_DIR.parent
sys.path.insert(0, str(AI_DIR))

DATA = ROOT / "data" / "splits"
RESULTS = ROOT / "results"
CACHE_DIR = AI_DIR / ".bench_cache"
SEED = 42

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bench")
for noisy in ("httpx", "sentence_transformers", "urllib3", "huggingface_hub"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

BENCH_SYSTEM_PROMPT = (
    "Answer the question using ONLY the provided context. "
    "Reply with the shortest possible answer: a name, date, place, or yes/no. No explanation."
)


# ----------------------------------------------------------------------------- data

def slug(t: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", t.strip()).strip("_").lower()
    return s or "doc"


def load_corpus(n_questions: int):
    """Seeded shuffle of the eval questions (so question types are mixed), take the first n.
    Corpus = union of those questions' paragraphs, in a fixed order."""
    qf = DATA / "eval_questions.json"
    if not qf.exists():
        raise SystemExit(f"{qf} not found. Run scripts/make_eval_data.py first.")
    qs = json.load(open(qf, encoding="utf-8"))
    random.Random(SEED).shuffle(qs)
    qs = qs[:n_questions]

    order, texts = [], {}
    for q in qs:
        for title, _ in q["context"]:
            s = slug(title)
            if s in texts:
                continue
            p = DATA / "eval_docs" / f"{s}.txt"
            if not p.exists():
                raise SystemExit(f"Missing eval doc {p}. eval_docs and eval_questions.json are out of sync.")
            texts[s] = p.read_text(encoding="utf-8")
            order.append(s)
    for q in qs:
        q["_gold_docs"] = sorted({slug(t) for t, _ in q["supporting_facts"]})
        missing = [d for d in q["_gold_docs"] if d not in texts]
        if missing:
            raise SystemExit(f"Gold docs {missing} of question {q['_id']} are not in the corpus")
    return qs, order, texts


def make_edits(order, texts, n_edits, pool_size):
    """Single-fact edit = first 4-digit year in the paragraph shifted by +3."""
    year = re.compile(r"\b(1[5-9]\d\d|20[0-2]\d)\b")
    edits = []
    for d in order[:pool_size]:
        m = year.search(texts[d])
        if not m:
            continue
        new_year = str(int(m.group(1)) + 3)
        new_text = texts[d][: m.start()] + new_year + texts[d][m.end():]
        edits.append((d, new_text))
        if len(edits) == n_edits:
            break
    if len(edits) < n_edits:
        logger.warning("Only %d edits could be built (wanted %d)", len(edits), n_edits)
    if not edits:
        raise SystemExit("No edit candidates found (no year in the first documents)")
    return edits


# ----------------------------------------------------------------------------- metrics

def normalize_answer(s: str) -> str:
    s = s.lower()
    s = "".join(ch for ch in s if ch not in set(string.punctuation))
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    return " ".join(s.split())


def exact_match(pred: str, gold: str) -> float:
    return float(normalize_answer(pred) == normalize_answer(gold))


def f1_score(pred: str, gold: str) -> float:
    p, g = normalize_answer(pred).split(), normalize_answer(gold).split()
    if not p or not g:
        return float(p == g)
    common = Counter(p) & Counter(g)
    n = sum(common.values())
    if n == 0:
        return 0.0
    prec, rec = n / len(p), n / len(g)
    return 2 * prec * rec / (prec + rec)


def boot_ci(vals, n=2000):
    a = np.asarray(vals, dtype=float)
    if len(a) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(SEED)
    means = [rng.choice(a, len(a)).mean() for _ in range(n)]
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def trim_words(text: str, limit: int) -> str:
    out, n = [], 0
    for line in text.splitlines():
        w = len(line.split())
        if n + w > limit:
            break
        out.append(line)
        n += w
    return "\n".join(out) if out else " ".join(text.split()[:limit])


def med(x):
    return float(statistics.median(x)) if x else float("nan")


# ----------------------------------------------------------------------------- extraction cache

def install_extraction_cache(extractor, model_tag: str):
    from app.extraction.prompts import GRAPHRAG_EXTRACTION_SYSTEM_PROMPT

    salt = hashlib.sha256((model_tag + GRAPHRAG_EXTRACTION_SYSTEM_PROMPT).encode()).hexdigest()[:16]
    CACHE_DIR.mkdir(exist_ok=True)
    orig = extractor.extract_from_document
    stats = {"hits": 0, "misses": 0, "last_ms": 0.0}

    def wrapped(document_id, title, chunks):
        text = "".join(c.text for c in chunks)
        key = hashlib.sha256(f"{salt}|{document_id}|{title}|{text}".encode()).hexdigest()
        path = CACHE_DIR / f"{key}.pkl"
        if path.exists():
            with open(path, "rb") as f:
                ents, rels, ms = pickle.load(f)
            stats["hits"] += 1
        else:
            t0 = time.perf_counter()
            ents, rels = orig(document_id=document_id, title=title, chunks=chunks)
            ms = (time.perf_counter() - t0) * 1000.0
            tmp = path.with_suffix(".tmp")
            with open(tmp, "wb") as f:
                pickle.dump((ents, rels, ms), f)
            os.replace(tmp, path)
            stats["misses"] += 1
        stats["last_ms"] = ms
        return ents, rels

    extractor.extract_from_document = wrapped
    return stats


# ----------------------------------------------------------------------------- pipeline wrapper

class Bench:
    def __init__(self, k: int):
        from app.config import settings
        from app.main import initialize_pipeline

        ckpt = AI_DIR / settings.ROLAND_MODEL_PATH
        if not ckpt.exists():
            raise SystemExit(f"No trained ROLAND checkpoint at {ckpt}. Train first (scripts.train_roland).")
        self.ckpt_path = ckpt
        self.ckpt_sha = hashlib.sha256(ckpt.read_bytes()).hexdigest()

        self.settings = settings
        self.k = k
        c = initialize_pipeline()
        self.inc = c["incremental_engine"]
        self.qe = c["query_engine"]
        self.store = c["graph_store"]
        self.roland = c["roland_model"]
        self.client = self.store.client
        if self.client.is_connected:
            raise SystemExit("Neo4j is connected. This benchmark maps nodes to documents through the in-memory "
                             "graph; stop Neo4j (or point NEO4J_URI at nothing) and rerun.")
        self.fb = self.client.in_memory_fallback
        self.model_name = getattr(settings, f"{settings.LLM_PROVIDER.upper()}_MODEL")
        self.cache_stats = install_extraction_cache(self.inc.extractor, f"{settings.LLM_PROVIDER}/{self.model_name}")
        self.llm = self.qe.answer_generator.llm

    def reset(self):
        self.fb.nodes.clear()
        self.fb.edges.clear()
        self.fb.documents.clear()
        self.roland.state_cache.clear()

    def add_doc(self, doc_id: str, text: str):
        title = text.splitlines()[0].strip() if text.strip() else doc_id
        t0 = time.perf_counter()
        res = self.inc.process_document_update(
            document_id=doc_id, title=title, content=text, k_hops=self.k, trigger_leiden=False
        )
        wall = (time.perf_counter() - t0) * 1000.0
        llm_ms = self.cache_stats["last_ms"]
        non_llm = wall - res["extraction_time_ms"]
        return {**res, "llm_ms": llm_ms, "non_llm_ms": non_llm, "wall_ms": wall}

    def doc_nodes(self, doc_id: str):
        return {(n["name"].lower(), n.get("description", ""))
                for n in self.fb.nodes.values() if doc_id in n.get("mentioned_in_docs", set())}

    def graph_snapshot(self):
        nodes = {n["name"].lower(): n for n in self.fb.nodes.values()}
        edges = {(e["src"].lower(), e["tgt"].lower(), e["type"]) for e in self.fb.edges}
        return nodes, edges


# ----------------------------------------------------------------------------- stage: extract

def stage_extract(b: Bench, order, texts, edits):
    items = [(d, texts[d]) for d in order] + [(d, t) for d, t in edits]
    t_start = time.perf_counter()
    for i, (d, text) in enumerate(items, 1):
        title = text.splitlines()[0].strip()
        chunks = b.inc.chunker.chunk_document(document_id=d, text=text)
        b.inc.extractor.extract_from_document(document_id=d, title=title, chunks=chunks)
        if i % 10 == 0 or i == len(items):
            el = time.perf_counter() - t_start
            logger.info("extract %d/%d  (cache hits %d, new calls %d)  ETA %.0f min",
                        i, len(items), b.cache_stats["hits"], b.cache_stats["misses"],
                        el / i * (len(items) - i) / 60)
    logger.info("Extraction cache is complete for the benchmark corpus and edits.")


# ----------------------------------------------------------------------------- stage: efficiency

def stage_efficiency(b: Bench, order, texts, sizes, n_edits, repeats):
    edits = make_edits(order, texts, n_edits, pool_size=min(min(sizes), len(order)))
    rows, summaries = [], {}
    for N in sizes:
        if N > len(order):
            logger.warning("Size %d > corpus %d: using %d", N, len(order), len(order))
        N = min(N, len(order))
        docs = order[:N]
        logger.info("=== corpus size %d ===", N)

        rebuild_runs = []
        for r in range(repeats):
            b.reset()
            llm = non_llm = 0.0
            for d in docs:
                o = b.add_doc(d, texts[d])
                llm += o["llm_ms"]
                non_llm += o["non_llm_ms"]
            rebuild_runs.append({"llm_ms": llm, "non_llm_ms": non_llm, "total_ms": llm + non_llm})
            logger.info("rebuild %d/%d: non-LLM %.0f ms, recorded LLM %.0f ms", r + 1, repeats, non_llm, llm)

        n_nodes_before = len(b.fb.nodes)
        inc_rows = []
        for d, new_text in edits:
            before = b.doc_nodes(d)
            o = b.add_doc(d, new_text)
            after = b.doc_nodes(d)
            row = {
                "corpus_size": N, "doc_id": d,
                "llm_ms": round(o["llm_ms"], 2), "non_llm_ms": round(o["non_llm_ms"], 2),
                "total_ms": round(o["llm_ms"] + o["non_llm_ms"], 2),
                "roland_gru_ms": o["roland_gru_time_ms"],
                "affected_nodes": o["affected_nodes_count"],
                "reembedded_nodes": o["updated_embeddings_count"],
                "graph_nodes": len(b.fb.nodes),
                "graph_changed": bool(before != after),
            }
            inc_rows.append(row)
        rows += inc_rows

        # parity: rebuild from the edited corpus and compare with the incrementally updated graph
        inc_nodes, inc_edges = b.graph_snapshot()
        edited = dict(texts)
        for d, t in edits:
            edited[d] = t
        b.reset()
        for d in docs:
            b.add_doc(d, edited[d])
        reb_nodes, reb_edges = b.graph_snapshot()

        def jac(a, c):
            a, c = set(a), set(c)
            return len(a & c) / len(a | c) if (a | c) else 1.0

        cos = []
        for name in set(inc_nodes) & set(reb_nodes):
            e1, e2 = inc_nodes[name].get("gnn_embedding"), reb_nodes[name].get("gnn_embedding")
            if e1 is not None and e2 is not None and len(e1) and len(e2):
                v1, v2 = np.asarray(e1, dtype=np.float32), np.asarray(e2, dtype=np.float32)
                cos.append(float(v1 @ v2 / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9)))

        inc_tot, inc_non = [r["total_ms"] for r in inc_rows], [r["non_llm_ms"] for r in inc_rows]
        reb_tot = [r["total_ms"] for r in rebuild_runs]
        reb_non = [r["non_llm_ms"] for r in rebuild_runs]
        summaries[N] = {
            "corpus_size": N, "n_edits": len(inc_rows), "rebuild_repeats": repeats, "k": b.k,
            "incremental_median_total_ms": med(inc_tot),
            "incremental_median_non_llm_ms": med(inc_non),
            "incremental_median_llm_ms": med([r["llm_ms"] for r in inc_rows]),
            "rebuild_median_total_ms": med(reb_tot),
            "rebuild_median_non_llm_ms": med(reb_non),
            "rebuild_median_llm_ms": med([r["llm_ms"] for r in rebuild_runs]),
            "speedup_total": med(reb_tot) / med(inc_tot) if med(inc_tot) else float("nan"),
            "speedup_non_llm": med(reb_non) / med(inc_non) if med(inc_non) else float("nan"),
            "median_reembedded_nodes": med([r["reembedded_nodes"] for r in inc_rows]),
            "graph_nodes": n_nodes_before,
            "reembedded_share_of_graph": med([r["reembedded_nodes"] / max(1, r["graph_nodes"]) for r in inc_rows]),
            "edits_that_changed_graph": sum(r["graph_changed"] for r in inc_rows) / len(inc_rows),
            "parity_node_jaccard": jac(inc_nodes, reb_nodes),
            "parity_edge_jaccard": jac(inc_edges, reb_edges),
            "parity_mean_gnn_cosine": float(np.mean(cos)) if cos else float("nan"),
            "parity_nodes_compared": len(cos),
        }

    RESULTS.mkdir(exist_ok=True)
    with open(RESULTS / "efficiency_edits.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    json.dump(summaries, open(RESULTS / "efficiency_summary.json", "w"), indent=2)

    print("\n=== SLIDE NUMBERS: median update latency, incremental vs full rebuild ===")
    for N, s in summaries.items():
        print(f"N={N:4d}  incremental {s['incremental_median_total_ms']:.0f} ms  vs  rebuild {s['rebuild_median_total_ms']:.0f} ms"
              f"  -> {s['speedup_total']:.1f}x   |  excluding LLM: {s['incremental_median_non_llm_ms']:.0f} ms vs "
              f"{s['rebuild_median_non_llm_ms']:.0f} ms -> {s['speedup_non_llm']:.1f}x   |  "
              f"re-embedded {s['median_reembedded_nodes']:.0f}/{s['graph_nodes']} nodes   |  "
              f"parity node-Jaccard {s['parity_node_jaccard']:.2f}, GNN cosine {s['parity_mean_gnn_cosine']:.3f}")
    return summaries


# ----------------------------------------------------------------------------- stage: quality

def _node_of(r):
    return r["node"] if isinstance(r.get("node"), dict) else r


def _docs_of(nodes):
    seen = []
    for n in nodes:
        for d in sorted(n.get("mentioned_in_docs", set())):
            if d not in seen:
                seen.append(d)
    return seen


def stage_quality(b: Bench, qs, order, texts, topk, budget):
    from app.retrieval.context_builder import ContextBuilder

    out_path = RESULTS / "quality_rows.jsonl"
    RESULTS.mkdir(exist_ok=True)
    done = set()
    if out_path.exists():
        for line in open(out_path, encoding="utf-8"):
            r = json.loads(line)
            done.add((r["qid"], r["arm"]))
        logger.info("Resuming: %d (question, arm) rows already done", len(done))

    logger.info("Building graph for %d docs ...", len(order))
    b.reset()
    for i, d in enumerate(order, 1):
        b.add_doc(d, texts[d])
        if i % 25 == 0:
            logger.info("indexed %d/%d", i, len(order))

    chunks = []
    for d in order:
        chunks += b.inc.chunker.chunk_document(document_id=d, text=texts[d])
    cvec = b.inc.embedder.embed_batch([c.text for c in chunks])
    cvec = cvec / (np.linalg.norm(cvec, axis=1, keepdims=True) + 1e-9)

    def answer(q, ctx):
        prompt = f"Context:\n{ctx}\n\nQuestion: {q}\nAnswer:"
        return b.llm.generate(prompt=prompt, system_prompt=BENCH_SYSTEM_PROMPT, temperature=0.0, max_tokens=256).strip()

    with open(out_path, "a", encoding="utf-8") as fout:
        for qi, q in enumerate(qs, 1):
            question, gold, qid = q["question"], q["answer"], q["_id"]
            gold_docs = set(q["_gold_docs"])
            qv = b.inc.embedder.embed_text(question)

            arms = {}
            sims = cvec @ (qv / (np.linalg.norm(qv) + 1e-9))
            top = np.argsort(-sims)[:topk]
            arms["A"] = ("\n\n".join(chunks[i].text for i in top), list(dict.fromkeys(chunks[i].document_id for i in top)))

            cands = [_node_of(r) for r in b.store.search_vector_index(qv.tolist(), top_k=topk, use_gnn=False)]
            arms["B"] = ("\n".join(f"- {n['name']}: {n.get('description', '')}" for n in cands), _docs_of(cands))

            for arm, use_gnn in (("C", True), ("D", False)):
                sub = b.qe.pcst_retriever.retrieve_subgraph(query=question, use_gnn=use_gnn)
                arms[arm] = (ContextBuilder.build_llm_context(subgraph=sub), _docs_of(sub.get("nodes", [])))

            for arm in "ABCD":
                if (qid, arm) in done:
                    continue
                ctx, docs = arms[arm]
                ctx = trim_words(ctx, budget)
                t0 = time.perf_counter()
                pred = answer(question, ctx)
                gen_ms = (time.perf_counter() - t0) * 1000.0
                hit = gold_docs & set(docs)
                row = {
                    "qid": qid, "type": q["type"], "arm": arm, "question": question, "gold": gold, "pred": pred,
                    "em": exact_match(pred, gold), "f1": f1_score(pred, gold),
                    "doc_recall": len(hit) / len(gold_docs), "all_gold_found": float(gold_docs <= set(docs)),
                    "doc_precision": len(hit) / len(docs) if docs else 0.0,
                    "n_docs": len(docs), "ctx_words": len(ctx.split()),
                    "ctx_hash": hashlib.sha256(ctx.encode()).hexdigest()[:12], "gen_ms": round(gen_ms, 1),
                }
                fout.write(json.dumps(row) + "\n")
                fout.flush()
            logger.info("question %d/%d done", qi, len(qs))

    return summarize_quality(out_path)


def summarize_quality(path: Path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    summary = {"by_arm": {}, "by_arm_and_type": {}}
    metrics = ["em", "f1", "doc_recall", "all_gold_found", "doc_precision"]
    for arm in "ABCD":
        rs = [r for r in rows if r["arm"] == arm]
        if not rs:
            continue
        d = {"n": len(rs)}
        for m in metrics:
            vals = [r[m] for r in rs]
            lo, hi = boot_ci(vals)
            d[m] = float(np.mean(vals))
            d[m + "_ci95"] = [lo, hi]
        d["mean_ctx_words"] = float(np.mean([r["ctx_words"] for r in rs]))
        summary["by_arm"][arm] = d
        for t in sorted({r["type"] for r in rs}):
            ts = [r for r in rs if r["type"] == t]
            summary["by_arm_and_type"][f"{arm}/{t}"] = {"n": len(ts), **{m: float(np.mean([r[m] for r in ts])) for m in metrics}}

    by_q = {}
    for r in rows:
        by_q.setdefault(r["qid"], {})[r["arm"]] = r["ctx_hash"]
    full = [h for h in by_q.values() if len(h) == 4]
    summary["sanity"] = {
        "questions": len(by_q),
        "share_all_four_contexts_distinct": float(np.mean([len(set(h.values())) == 4 for h in full])) if full else None,
        "share_C_differs_from_D": float(np.mean([h["C"] != h["D"] for h in full])) if full else None,
    }
    json.dump(summary, open(RESULTS / "quality_summary.json", "w"), indent=2)

    print("\n=== QUALITY (per arm; 95% bootstrap CI in json) ===")
    print(f"{'arm':4}{'n':>4}{'EM':>8}{'F1':>8}{'docRecall':>11}{'allGold':>9}{'docPrec':>9}")
    for arm, d in summary["by_arm"].items():
        print(f"{arm:4}{d['n']:>4}{d['em']:>8.3f}{d['f1']:>8.3f}{d['doc_recall']:>11.3f}{d['all_gold_found']:>9.3f}{d['doc_precision']:>9.3f}")
    print("sanity:", summary["sanity"])
    return summary


# ----------------------------------------------------------------------------- main

def main():
    from app.config import settings

    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["extract", "efficiency", "quality", "all"], default="all")
    ap.add_argument("--questions", type=int, default=35)
    ap.add_argument("--sizes", type=int, nargs="+", default=[50, 150, 300])
    ap.add_argument("--edits", type=int, default=20)
    ap.add_argument("--repeats", type=int, default=2, help="full rebuild repetitions per size")
    ap.add_argument("--k", type=int, default=settings.DEFAULT_K_HOPS)
    ap.add_argument("--topk", type=int, default=10)
    ap.add_argument("--budget-words", type=int, default=1100)
    args = ap.parse_args()

    qs, order, texts = load_corpus(args.questions)
    logger.info("%d questions, %d corpus docs", len(qs), len(order))
    random.seed(SEED)
    np.random.seed(SEED)

    b = Bench(args.k)
    edits = make_edits(order, texts, args.edits, pool_size=min(min(args.sizes), len(order)))

    if args.stage in ("extract", "all"):
        stage_extract(b, order, texts, edits)
    eff = qual = None
    if args.stage in ("efficiency", "all"):
        eff = stage_efficiency(b, order, texts, args.sizes, args.edits, args.repeats)
    if args.stage in ("quality", "all"):
        qual = stage_quality(b, qs, order, texts, args.topk, args.budget_words)

    # sanity + metadata
    train_overlap = None
    ts = ROOT / "data" / "train_stream.jsonl"
    if ts.exists():
        eval_ids = {p.stem for p in (DATA / "eval_docs").glob("*.txt")}
        train_ids = {Path(json.loads(l)["doc_id"]).stem for l in open(ts, encoding="utf-8") if l.strip()}
        train_overlap = len(eval_ids & train_ids)
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = ""
    meta = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "git_commit": commit, "seed": SEED, "args": vars(args),
        "llm_provider": settings.LLM_PROVIDER, "llm_model": b.model_name,
        "embedding_model": settings.EMBEDDING_MODEL_NAME, "gnn_type": settings.GNN_TYPE,
        "gnn_layers": settings.GNN_NUM_LAYERS, "checkpoint": str(b.ckpt_path), "checkpoint_sha256": b.ckpt_sha,
        "corpus_docs": len(order), "n_questions": len(qs), "graph_backend": "in-memory",
        "leiden_excluded": True, "train_eval_doc_overlap": train_overlap,
        "extraction_cache": {"hits": b.cache_stats["hits"], "new_llm_calls": b.cache_stats["misses"]},
        "edits_used": len(edits),
        "edits_changed_graph_share": (eff[max(eff)]["edits_that_changed_graph"] if eff else None),
    }
    RESULTS.mkdir(exist_ok=True)
    json.dump(meta, open(RESULTS / "benchmark_meta.json", "w"), indent=2)
    print("\nMetadata saved to results/benchmark_meta.json. train/eval doc overlap:", train_overlap)


if __name__ == "__main__":
    main()