"""
ROLAND Dynamic Graph GRU - Truncated-BPTT Training Script.
Builds temporal graph snapshots from an edit stream (held out from evaluation)
and trains RolandHierarchicalGRU using the link prediction objective.
"""

import os
import sys
import json
import random
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
import numpy as np

# Ensure ai_service and repo root are in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.config import settings
from app.embeddings.embedder import SentenceTransformerEmbedder
from app.preprocessing.text_processor import TextProcessor
from app.preprocessing.chunker import SemanticChunker
from app.llm.client import LLMClient
from app.extraction.graphrag_extractor import GraphRAGIncrementalExtractor
from app.gnn.roland_gru import RolandHierarchicalGRU
from app.gnn.trainer import TruncatedBPTTTrainer, DynamicGraphSnapshot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_roland")

try:
    import torch
    torch.manual_seed(42)
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

random.seed(42)
np.random.seed(42)


def sample_negative_edges(
    num_nodes: int,
    pos_edges: np.ndarray,
    num_neg_samples: int,
) -> np.ndarray:
    """
    Samples negative edges (non-existing edges) uniformly at random.
    pos_edges: [2, E]
    """
    if num_nodes <= 1:
        return np.empty((2, 0), dtype=np.int64)

    existing_set = set()
    if pos_edges is not None and pos_edges.size > 0:
        for s, d in zip(pos_edges[0], pos_edges[1]):
            existing_set.add((int(s), int(d)))
            existing_set.add((int(d), int(s)))

    neg_pairs = set()
    max_attempts = num_neg_samples * 10
    attempts = 0

    while len(neg_pairs) < num_neg_samples and attempts < max_attempts:
        attempts += 1
        u = random.randint(0, num_nodes - 1)
        v = random.randint(0, num_nodes - 1)
        if u != v and (u, v) not in existing_set and (u, v) not in neg_pairs:
            neg_pairs.add((u, v))

    if not neg_pairs:
        return np.empty((2, 0), dtype=np.int64)

    srcs, dsts = zip(*neg_pairs)
    return np.array([srcs, dsts], dtype=np.int64)


def build_snapshots_from_docs(
    doc_paths: List[Path],
    chunker: SemanticChunker,
    extractor: GraphRAGIncrementalExtractor,
    embedder: SentenceTransformerEmbedder,
) -> List[DynamicGraphSnapshot]:
    """
    Simulates a dynamic edit stream where documents arrive sequentially as snapshots.
    """
    snapshots: List[DynamicGraphSnapshot] = []
    accumulated_entities: Dict[str, Dict[str, Any]] = {}
    accumulated_edges: List[Tuple[str, str]] = []

    for t, doc_p in enumerate(doc_paths):
        text = doc_p.read_text(encoding="utf-8", errors="ignore")
        doc_id = doc_p.stem
        chunks = chunker.chunk_document(document_id=doc_id, text=text)
        entities, relationships = extractor.extract_from_document(
            document_id=doc_id, title=doc_id, chunks=chunks
        )

        for e in entities:
            if e.name not in accumulated_entities:
                accumulated_entities[e.name] = {
                    "embedding": embedder.embed_text(f"{e.name}: {e.description or e.type}"),
                }

        for r in relationships:
            accumulated_edges.append((r.source_name, r.target_name))

        node_names = list(accumulated_entities.keys())
        if not node_names:
            continue

        name_to_idx = {name: i for i, name in enumerate(node_names)}
        features = np.array([accumulated_entities[n]["embedding"] for n in node_names], dtype=np.float32)

        pos_src = []
        pos_dst = []
        for s, d in accumulated_edges:
            if s in name_to_idx and d in name_to_idx:
                pos_src.append(name_to_idx[s])
                pos_dst.append(name_to_idx[d])
                # Undirected
                pos_src.append(name_to_idx[d])
                pos_dst.append(name_to_idx[s])

        if pos_src:
            pos_edge_index = np.array([pos_src, pos_dst], dtype=np.int64)
        else:
            pos_edge_index = np.empty((2, 0), dtype=np.int64)

        neg_edge_index = sample_negative_edges(
            num_nodes=len(node_names),
            pos_edges=pos_edge_index,
            num_neg_samples=max(1, len(pos_src) // 2),
        )

        snapshot = DynamicGraphSnapshot(
            timestamp=float(t),
            node_ids=node_names,
            features=features,
            pos_edges=pos_edge_index,
            neg_edges=neg_edge_index,
        )
        snapshots.append(snapshot)
        logger.info(f"Snapshot t={t+1}: {len(node_names)} nodes, {pos_edge_index.shape[1]} pos edges.")

    return snapshots


def build_synthetic_snapshots(
    num_snapshots: int = 6,
    nodes_per_snapshot: int = 15,
    embedding_dim: int = 384,
) -> List[DynamicGraphSnapshot]:
    """Generates synthetic dynamic snapshots for offline training when no corpus is specified."""
    snapshots = []
    rng = np.random.RandomState(42)
    all_nodes = [f"entity_{i}" for i in range(nodes_per_snapshot * 3)]

    current_node_count = nodes_per_snapshot
    for t in range(num_snapshots):
        current_node_count = min(len(all_nodes), nodes_per_snapshot + t * 4)
        snapshot_nodes = all_nodes[:current_node_count]
        features = rng.randn(current_node_count, embedding_dim).astype(np.float32)
        norm = np.linalg.norm(features, axis=-1, keepdims=True) + 1e-9
        features = features / norm

        # Generate temporal edges
        srcs, dsts = [], []
        for i in range(current_node_count):
            neighbor = (i + 1 + (t % 3)) % current_node_count
            srcs.extend([i, neighbor])
            dsts.extend([neighbor, i])

        pos_edges = np.array([srcs, dsts], dtype=np.int64)
        neg_edges = sample_negative_edges(current_node_count, pos_edges, len(srcs) // 2)

        snapshots.append(
            DynamicGraphSnapshot(
                timestamp=float(t),
                node_ids=snapshot_nodes,
                features=features,
                pos_edges=pos_edges,
                neg_edges=neg_edges,
            )
        )
    return snapshots


def train_roland(
    docs_dir: str = "",
    epochs: int = 5,
    lr: float = 0.005,
    window_size: int = 3,
    save_path: str = "",
    in_dim: int = 384,
    hidden_dim: int = 128,
    out_dim: int = 384,
):
    save_p = save_path or settings.ROLAND_MODEL_PATH
    # Ensure relative path resolves relative to ai_service
    if not os.path.isabs(save_p):
        save_p = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", save_p))

    logger.info(f"Preparing ROLAND model training (epochs={epochs}, lr={lr}, window_size={window_size})...")

    # 1. Build Snapshots
    doc_path = Path(docs_dir) if docs_dir else None
    if doc_path and doc_path.exists():
        files = sorted(list(doc_path.glob("*.txt")) + list(doc_path.glob("*.md")))
        if files:
            logger.info(f"Extracting edit snapshots from {len(files)} files in {docs_dir}...")
            processor = TextProcessor(model_name=settings.SPACY_MODEL)
            chunker = SemanticChunker(processor=processor)
            embedder = SentenceTransformerEmbedder(
                model_name=settings.EMBEDDING_MODEL_NAME, embedding_dim=in_dim
            )
            llm = LLMClient(provider=settings.LLM_PROVIDER, openai_api_key=settings.OPENAI_API_KEY)
            extractor = GraphRAGIncrementalExtractor(llm_client=llm, embedder=embedder)

            # Check for extraction cache
            for cd in [
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "cache", "extraction_cache")),
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "cache", "extraction_cache")),
            ]:
                if os.path.exists(cd):
                    try:
                        from bench.common import install_extraction_cache
                        install_extraction_cache(extractor, cd, model_name=settings.OPENAI_MODEL)
                        logger.info(f"Loaded extraction cache from {cd}")
                    except Exception as e:
                        logger.debug(f"Could not load extraction cache: {e}")
                    break

            snapshots = build_snapshots_from_docs(files, chunker, extractor, embedder)
        else:
            logger.warning(f"No documents found in {docs_dir}. Generating synthetic snapshots.")
            snapshots = build_synthetic_snapshots(embedding_dim=in_dim)
    else:
        logger.info("Using synthetic dynamic graph snapshots for training.")
        snapshots = build_synthetic_snapshots(embedding_dim=in_dim)

    # 2. Instantiate RolandHierarchicalGRU with residual readout in text space
    model = RolandHierarchicalGRU(
        in_dim=in_dim,
        hidden_dim=hidden_dim,
        out_dim=out_dim,
        num_layers=settings.GNN_NUM_LAYERS,
        gnn_type=settings.GNN_TYPE,
        dropout=settings.GNN_DROPOUT,
        residual=True,
    )

    # 3. Train using Truncated-BPTT on Link Prediction
    trainer = TruncatedBPTTTrainer(
        model=model,
        lr=lr,
        window_size=window_size,
    )

    logger.info(f"Starting Truncated-BPTT training over {len(snapshots)} snapshots...")
    loss_history = trainer.train_dynamic_stream(snapshots=snapshots, epochs=epochs)

    # 4. Save trained weights
    model.save_checkpoint(save_p)

    # 5. Compute mean cosine similarity on final training graph snapshot
    mean_cos = 1.0
    if snapshots and len(snapshots) > 0 and TORCH_AVAILABLE and isinstance(model, torch.nn.Module):
        last_snap = snapshots[-1]
        x_eval = torch.tensor(last_snap.features, dtype=torch.float32)
        edge_eval = torch.tensor(last_snap.pos_edges, dtype=torch.long)
        model.eval()
        with torch.no_grad():
            out_eval = model(x_eval, edge_eval, last_snap.node_ids, update_cache=False)
            x_unit = torch.nn.functional.normalize(x_eval, dim=-1)
            mean_cos = float((out_eval * x_unit).sum(dim=-1).mean().item())
        logger.info(f"Mean cos(out, x) on training graph: {mean_cos:.4f}")

    # 6. Save summary to results/train_summary.json
    import hashlib
    with open(save_p, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()

    num_windows = (len(snapshots) + window_size - 1) // window_size
    total_opt_steps = num_windows * epochs

    results_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results"))
    os.makedirs(results_dir, exist_ok=True)
    summary_path = os.path.join(results_dir, "train_summary.json")

    train_summary = {
        "snapshots": len(snapshots),
        "optimizer_steps": total_opt_steps,
        "loss_per_epoch": loss_history,
        "mean_cosine_similarity": mean_cos,
        "checkpoint_sha256": sha256,
        "checkpoint_path": save_p,
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(train_summary, f, indent=2)
    logger.info(f"Saved training summary to {summary_path}")

    logger.info(f"Training completed successfully. Losses: {loss_history}. Saved to: {save_p}")
    return model, loss_history


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train ROLAND GRU on dynamic graph snapshots via Truncated-BPTT")
    parser.add_argument("--docs-dir", type=str, default="", help="Path to held-out documents")
    parser.add_argument("--epochs", type=int, default=1000, help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=0.005, help="Learning rate")
    parser.add_argument("--window-size", type=int, default=3, help="Truncated-BPTT window size")
    parser.add_argument("--save-path", type=str, default="", help="Path to save trained model weights")
    args = parser.parse_args()

    train_roland(
        docs_dir=args.docs_dir,
        epochs=args.epochs,
        lr=args.lr,
        window_size=args.window_size,
        save_path=args.save_path,
    )
