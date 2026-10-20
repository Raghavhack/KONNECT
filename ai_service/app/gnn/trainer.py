"""
Truncated-BPTT training for the ROLAND GRU (project core contribution, written by us).

Task: temporal link prediction. After the model has consumed snapshot t (message passing
over t's edges and a GRU state update), its embeddings must predict which edges exist in
snapshot t+1. This is what gives the recurrent state something to learn: the targets are
in the *future* relative to the edges the model saw.

Truncated BPTT: inside a window of `window_size` snapshots the cache keeps autograd graphs
(see RolandHierarchicalGRU), the summed loss is back-propagated once, then
`state_cache.detach_all()` cuts the graph at the window boundary.

The stream is split in time (train | val | test), never at random, and training stops early
when validation AUC stops improving. Use `evaluate()` for held-out numbers.
"""

import logging
import random
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from .roland_gru import RolandHierarchicalGRU

logger = logging.getLogger(__name__)


class DynamicGraphSnapshot:
    """Graph state at time t. `edges` are the undirected edges present at t, as [2, E]
    index pairs into `node_ids` (each undirected edge listed once; both directions are
    added when used for message passing)."""

    def __init__(self, timestamp: float, node_ids: List[str], features: np.ndarray, edges: np.ndarray):
        self.timestamp = timestamp
        self.node_ids = node_ids
        self.features = features
        self.edges = edges


def split_stream(snapshots: List[DynamicGraphSnapshot], train_frac: float = 0.7, val_frac: float = 0.15):
    """Chronological split. Returns (train, val, test) as index ranges over the full stream."""
    n = len(snapshots)
    a = int(n * train_frac)
    b = int(n * (train_frac + val_frac))
    return range(0, a), range(a, b), range(b, n)


def _undirected(edges: np.ndarray) -> np.ndarray:
    if edges.size == 0:
        return np.empty((2, 0), dtype=np.int64)
    return np.concatenate([edges, edges[::-1]], axis=1)


def _edge_set_by_name(snap: DynamicGraphSnapshot) -> set:
    names = snap.node_ids
    return {frozenset((names[int(s)], names[int(d)])) for s, d in zip(snap.edges[0], snap.edges[1]) if s != d}


def roc_auc(scores: torch.Tensor, labels: torch.Tensor) -> float:
    """Rank-based AUC (Mann-Whitney U). Returns 0.5 if only one class is present."""
    pos = labels > 0.5
    n_pos, n_neg = int(pos.sum()), int((~pos).sum())
    if n_pos == 0 or n_neg == 0:
        return 0.5
    order = torch.argsort(scores)
    ranks = torch.empty_like(order, dtype=torch.float32)
    ranks[order] = torch.arange(1, len(scores) + 1, dtype=torch.float32)
    return float((ranks[pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


class TruncatedBPTTTrainer:
    def __init__(self, model: RolandHierarchicalGRU, lr: float = 0.005, window_size: int = 3,
                 weight_decay: float = 1e-4, grad_clip: float = 1.0, seed: int = 0):
        self.model = model
        self.window_size = window_size
        self.grad_clip = grad_clip
        self.optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
        self.criterion = nn.BCEWithLogitsLoss()
        self.rng = random.Random(seed)

    # ---- targets -------------------------------------------------------------------
    def _targets(self, cur: DynamicGraphSnapshot, nxt: DynamicGraphSnapshot, device) -> Optional[Tuple[torch.Tensor, torch.Tensor]]:
        """Positives: edges of t+1 between nodes already present at t. Negatives: sampled
        node pairs (both present at t) that are NOT edges at t+1. Returns (pairs[2,M], labels[M])."""
        idx = {n: i for i, n in enumerate(cur.node_ids)}
        nxt_edges = _edge_set_by_name(nxt)
        pos = [(idx[a], idx[b]) for e in nxt_edges for a, b in [tuple(e)] if a in idx and b in idx]
        if not pos:
            return None
        n = len(cur.node_ids)
        neg, tries = [], 0
        while len(neg) < len(pos) and tries < 20 * len(pos):
            tries += 1
            u, v = self.rng.randrange(n), self.rng.randrange(n)
            if u != v and frozenset((cur.node_ids[u], cur.node_ids[v])) not in nxt_edges:
                neg.append((u, v))
        pairs = torch.tensor(pos + neg, dtype=torch.long, device=device).t()
        labels = torch.cat([torch.ones(len(pos)), torch.zeros(len(neg))]).to(device)
        return pairs, labels

    def _step(self, cur: DynamicGraphSnapshot, nxt: DynamicGraphSnapshot, device):
        x = torch.tensor(cur.features, dtype=torch.float32, device=device)
        ei = torch.tensor(_undirected(cur.edges), dtype=torch.long, device=device)
        emb = self.model(x=x, edge_index=ei, node_ids=cur.node_ids, update_cache=True)
        tgt = self._targets(cur, nxt, device)
        if tgt is None:
            return None, None, None
        pairs, labels = tgt
        scores = (emb[pairs[0]] * emb[pairs[1]]).sum(dim=-1)
        return self.criterion(scores, labels), scores.detach(), labels

    # ---- training ------------------------------------------------------------------
    def train(self, snapshots: List[DynamicGraphSnapshot], epochs: int = 30, patience: int = 5,
              train_frac: float = 0.7, val_frac: float = 0.15) -> Dict[str, List[float]]:
        """Trains on the chronological train split, early-stops on validation AUC and restores
        the best weights. Returns {'train_loss': [...], 'val_auc': [...]}."""
        device = next(self.model.parameters()).device
        tr, va, _ = split_stream(snapshots, train_frac, val_frac)
        history = {"train_loss": [], "val_auc": []}
        best_auc, best_state, bad = -1.0, None, 0

        for epoch in range(epochs):
            self.model.train()
            self.model.state_cache.clear()
            total, windows = 0.0, 0
            steps = [t for t in tr if t + 1 < len(snapshots)]
            for w in range(0, len(steps), self.window_size):
                self.optimizer.zero_grad()
                losses = []
                for t in steps[w:w + self.window_size]:
                    loss, _, _ = self._step(snapshots[t], snapshots[t + 1], device)
                    if loss is not None:
                        losses.append(loss)
                if losses:
                    window_loss = torch.stack(losses).sum()
                    window_loss.backward()
                    nn.utils.clip_grad_norm_(self.model.parameters(), self.grad_clip)
                    self.optimizer.step()
                    total += window_loss.item() / len(losses)
                    windows += 1
                self.model.state_cache.detach_all()      # truncation point
            history["train_loss"].append(total / max(1, windows))

            val_auc = self.evaluate(snapshots, va)["auc"] if len(va) else float("nan")
            history["val_auc"].append(val_auc)
            logger.info("epoch %d  train_loss=%.4f  val_auc=%.4f", epoch + 1, history["train_loss"][-1], val_auc)

            if len(va):
                if val_auc > best_auc + 1e-4:
                    best_auc, bad = val_auc, 0
                    best_state = {k: v.detach().clone() for k, v in self.model.state_dict().items()}
                else:
                    bad += 1
                    if bad >= patience:
                        logger.info("early stop at epoch %d (best val_auc=%.4f)", epoch + 1, best_auc)
                        break
        if best_state is not None:
            self.model.load_state_dict(best_state)
        return history

    # ---- evaluation ----------------------------------------------------------------
    @torch.no_grad()
    def evaluate(self, snapshots: List[DynamicGraphSnapshot], eval_range: range) -> Dict[str, float]:
        """Replays the stream from t=0 in eval mode (so GRU state is built from the past) and
        scores next-snapshot link prediction on the snapshots in eval_range."""
        device = next(self.model.parameters()).device
        self.model.eval()
        self.model.state_cache.clear()
        all_s, all_l = [], []
        for t in range(len(snapshots) - 1):
            if t > max(eval_range, default=-1):
                break
            _, scores, labels = self._step(snapshots[t], snapshots[t + 1], device)
            if t in eval_range and scores is not None:
                all_s.append(scores.cpu()); all_l.append(labels.cpu())
        if not all_s:
            return {"auc": float("nan"), "n": 0}
        s, l = torch.cat(all_s), torch.cat(all_l)
        return {"auc": roc_auc(s, l), "n": int(len(s))}
