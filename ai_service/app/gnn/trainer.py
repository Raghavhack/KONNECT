"""
Truncated Backpropagation Through Time (Truncated-BPTT) Training Loop for ROLAND.
Core Research Contribution - Implemented From Scratch.

Trains hierarchical GNN + GRU across dynamic snapshot streams while bounding
gradient computation and memory through window-based temporal state truncation.
"""

import logging
import random
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    nn = None
    optim = None
    TORCH_AVAILABLE = False

from .roland_gru import RolandHierarchicalGRU


class DynamicGraphSnapshot:
    """Represents a single temporal snapshot/delta of the dynamic knowledge graph."""

    def __init__(
        self,
        timestamp: float,
        node_ids: List[str],
        features: np.ndarray,
        pos_edges: np.ndarray,  # [2, E_pos]
        neg_edges: Optional[np.ndarray] = None,  # [2, E_neg]
    ):
        self.timestamp = timestamp
        self.node_ids = node_ids
        self.features = features
        self.pos_edges = pos_edges
        self.neg_edges = neg_edges


class TruncatedBPTTTrainer:
    """
    Manages Truncated-BPTT training for ROLAND dynamic graph models.
    Truncates backpropagation horizons every `window_size` snapshots.
    """

    def __init__(
        self,
        model: RolandHierarchicalGRU,
        lr: float = 0.005,
        window_size: int = 3,
        weight_decay: float = 1e-4,
        grad_clip: float = 1.0,
    ):
        self.model = model
        self.window_size = window_size
        self.grad_clip = grad_clip
        self.lr = lr

        if TORCH_AVAILABLE and isinstance(self.model, nn.Module):
            self.optimizer = optim.Adam(
                self.model.parameters(), lr=lr, weight_decay=weight_decay
            )
            self.criterion = nn.BCEWithLogitsLoss()
        else:
            self.optimizer = None
            self.criterion = None

    def train_dynamic_stream(
        self,
        snapshots: List[DynamicGraphSnapshot],
        epochs: int = 5,
    ) -> List[float]:
        """
        Executes Truncated-BPTT over a temporal stream of dynamic graph snapshots.
        """
        if not TORCH_AVAILABLE or not isinstance(self.model, nn.Module):
            logger.info("PyTorch not present. Skipping gradient training loop.")
            return [0.0]

        random.seed(42)
        np.random.seed(42)
        torch.manual_seed(42)

        device = next(self.model.parameters()).device
        self.model.train()
        loss_history = []

        for epoch in range(epochs):
            total_epoch_loss = 0.0
            num_windows = 0

            # Reset cache before starting full stream epoch
            self.model.state_cache.clear()

            # Iterate through snapshots in sliding windows of size self.window_size
            for w_start in range(0, len(snapshots), self.window_size):
                window = snapshots[w_start : w_start + self.window_size]
                self.optimizer.zero_grad()
                window_loss = torch.tensor(0.0, device=device)

                for snapshot in window:
                    x = torch.tensor(snapshot.features, dtype=torch.float32, device=device)
                    pos_edge_index = torch.tensor(snapshot.pos_edges, dtype=torch.long, device=device)

                    # Forward pass through ROLAND
                    embeddings = self.model(
                        x=x,
                        edge_index=pos_edge_index,
                        node_ids=snapshot.node_ids,
                        update_cache=True,
                    )

                    # Compute Link Prediction loss with SCORE_SCALE and anchor loss
                    SCORE_SCALE, ANCHOR_WEIGHT = 10.0, 3.5
                    pos_src, pos_dst = pos_edge_index[0], pos_edge_index[1]
                    pos_scores = SCORE_SCALE * (embeddings[pos_src] * embeddings[pos_dst]).sum(dim=-1)
                    pos_labels = torch.ones_like(pos_scores)

                    loss = self.criterion(pos_scores, pos_labels)

                    # Negative edge sampling
                    if snapshot.neg_edges is not None and snapshot.neg_edges.shape[1] > 0:
                        neg_edge_index = torch.tensor(snapshot.neg_edges, dtype=torch.long, device=device)
                        neg_src, neg_dst = neg_edge_index[0], neg_edge_index[1]
                        neg_scores = SCORE_SCALE * (embeddings[neg_src] * embeddings[neg_dst]).sum(dim=-1)
                        neg_labels = torch.zeros_like(neg_scores)
                        neg_loss = self.criterion(neg_scores, neg_labels)
                        loss = loss + neg_loss

                    x_unit = torch.nn.functional.normalize(x, dim=-1)
                    anchor = (1.0 - (embeddings * x_unit).sum(dim=-1)).mean()
                    loss = loss + ANCHOR_WEIGHT * anchor

                    window_loss = window_loss + loss

                if len(window) > 0 and window_loss.requires_grad:
                    # Truncated backprop for this window
                    window_loss.backward()
                    nn.utils.clip_grad_norm_(self.model.parameters(), self.grad_clip)
                    self.optimizer.step()

                    # DETACH: Crucial step in Truncated-BPTT
                    # Detach all cached tensors across layers to stop gradient graphs from leaking
                    for l in range(self.model.num_layers):
                        layer_cache = self.model.state_cache.get_layer_cache(l)
                        for nid, tensor in layer_cache.items():
                            if isinstance(tensor, torch.Tensor):
                                layer_cache[nid] = tensor.detach()

                    total_epoch_loss += window_loss.item()
                    num_windows += 1

            avg_loss = total_epoch_loss / max(1, num_windows)
            loss_history.append(avg_loss)
            logger.info(f"Epoch {epoch + 1}/{epochs} - Truncated-BPTT Link Prediction Loss: {avg_loss:.4f}")

        return loss_history
