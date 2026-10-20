"""
Train the ROLAND GRU on a REAL edit stream (no synthetic fallback).

Input: a JSONL file, one edit per line, in chronological order:
    {"doc_id": "docs/setup.md", "text": "<full new content of that document>"}
The graph at time t is the union of the entities/relations of the *latest version* of every
document after edit t. Each edit is one snapshot (= the project's definition of a time step).

Entity extraction needs the LLM, so results are cached on disk by content hash; re-running
training does not repeat LLM calls.

    python -m scripts.train_roland --stream data/edit_stream.jsonl --epochs 30

The stream is split chronologically (train 70% / val 15% / test 15%). Weights with the best
validation AUC are saved; test AUC is reported once at the end.
"""

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.gnn.roland_gru import RolandHierarchicalGRU
from app.gnn.trainer import DynamicGraphSnapshot, TruncatedBPTTTrainer, split_stream

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_roland")


def _extract_cached(text: str, doc_id: str, cache_dir: Path, chunker, extractor):
    key = hashlib.sha1(text.encode("utf-8")).hexdigest()
    path = cache_dir / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    chunks = chunker.chunk_document(document_id=doc_id, text=text)
    entities, relationships = extractor.extract_from_document(document_id=doc_id, title=doc_id, chunks=chunks)
    result = {
        "entities": [{"name": e.name, "embedding": list(map(float, e.embedding))} for e in entities if e.embedding is not None],
        "edges": [[r.source_name, r.target_name] for r in relationships],
    }
    path.write_text(json.dumps(result))
    return result


def build_snapshots(edits: List[dict], cache_dir: Path, chunker, extractor) -> List[DynamicGraphSnapshot]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    doc_entities: Dict[str, Dict[str, List[float]]] = {}
    doc_edges: Dict[str, Set[Tuple[str, str]]] = {}
    snapshots: List[DynamicGraphSnapshot] = []

    for t, edit in enumerate(edits):
        res = _extract_cached(edit["text"], edit["doc_id"], cache_dir, chunker, extractor)
        doc_entities[edit["doc_id"]] = {e["name"]: e["embedding"] for e in res["entities"]}
        doc_edges[edit["doc_id"]] = {tuple(sorted(e)) for e in res["edges"] if e[0] != e[1]}

        emb: Dict[str, List[float]] = {}
        for ents in doc_entities.values():
            emb.update(ents)
        names = sorted(emb)
        if not names:
            continue
        idx = {n: i for i, n in enumerate(names)}
        edges = sorted({e for es in doc_edges.values() for e in es if e[0] in idx and e[1] in idx})
        edge_arr = (np.array([[idx[a] for a, _ in edges], [idx[b] for _, b in edges]], dtype=np.int64)
                    if edges else np.empty((2, 0), dtype=np.int64))
        feats = np.array([emb[n] for n in names], dtype=np.float32)
        snapshots.append(DynamicGraphSnapshot(float(t), names, feats, edge_arr))
        logger.info("snapshot %d/%d: %d nodes, %d edges", t + 1, len(edits), len(names), edge_arr.shape[1])
    return snapshots


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stream", required=True, help="JSONL edit stream (chronological)")
    ap.add_argument("--cache-dir", default=".extraction_cache")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--patience", type=int, default=5)
    ap.add_argument("--lr", type=float, default=settings.ROLAND_LEARNING_RATE)
    ap.add_argument("--window-size", type=int, default=settings.ROLAND_TRUNCATED_BPTT_STEPS)
    ap.add_argument("--save-path", default=settings.ROLAND_MODEL_PATH)
    args = ap.parse_args()

    from app.embeddings.embedder import SentenceTransformerEmbedder
    from app.extraction.graphrag_extractor import GraphRAGIncrementalExtractor
    from app.llm.client import LLMClient
    from app.preprocessing.chunker import SemanticChunker
    from app.preprocessing.text_processor import TextProcessor

    edits = [json.loads(l) for l in Path(args.stream).read_text().splitlines() if l.strip()]
    embedder = SentenceTransformerEmbedder(model_name=settings.EMBEDDING_MODEL_NAME, embedding_dim=settings.NEO4J_EMBEDDING_DIM)
    llm = LLMClient(provider=settings.LLM_PROVIDER, openai_api_key=settings.OPENAI_API_KEY)
    extractor = GraphRAGIncrementalExtractor(llm_client=llm, embedder=embedder)
    chunker = SemanticChunker(processor=TextProcessor(model_name=settings.SPACY_MODEL))

    snapshots = build_snapshots(edits, Path(args.cache_dir), chunker, extractor)
    if len(snapshots) < 10:
        raise SystemExit(f"Only {len(snapshots)} snapshots: too few to train/validate/test. Use a longer edit stream.")

    model = RolandHierarchicalGRU(
        in_dim=settings.NEO4J_EMBEDDING_DIM, hidden_dim=settings.GNN_HIDDEN_DIM, out_dim=settings.NEO4J_EMBEDDING_DIM,
        num_layers=settings.GNN_NUM_LAYERS, gnn_type=settings.GNN_TYPE, dropout=settings.GNN_DROPOUT, residual=True,
    )
    trainer = TruncatedBPTTTrainer(model, lr=args.lr, window_size=args.window_size)
    history = trainer.train(snapshots, epochs=args.epochs, patience=args.patience)

    _, _, te = split_stream(snapshots)
    test = trainer.evaluate(snapshots, te)
    logger.info("FINAL  best_val_auc=%.4f  test_auc=%.4f (n=%d)", max(history["val_auc"]), test["auc"], test["n"])

    save_path = args.save_path if os.path.isabs(args.save_path) else os.path.abspath(os.path.join(os.path.dirname(__file__), "..", args.save_path))
    model.save_checkpoint(save_path)


if __name__ == "__main__":
    main()