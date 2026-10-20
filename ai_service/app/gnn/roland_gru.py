"""
ROLAND hierarchical GRU state update (project core contribution, written by us).

For every GNN layer l, with h~_v^(l,t) the freshly computed message-passing output
and h_v^(l,t-1) the node's cached state from the previous update:

    h~_v^(l,t) = GNN^(l)( h_v^(l-1,t), edges )           (spatial, synopsis Eq. 3)
    h_v^(l,t)  = GRU^(l)( h~_v^(l,t), h_v^(l,t-1) )      (temporal, synopsis Eq. 5)

and h^(l,t) is fed to layer l+1 (hierarchical state). torch.nn.GRUCell is the only
library primitive; the state cache and update logic are ours.

State-cache rule (this is what makes truncated BPTT work):
  * training mode  -> states are stored WITH their autograd graph so gradients can
                      flow across snapshots inside a window. The trainer calls
                      `state_cache.detach_all()` at each window boundary (the "truncation").
  * eval mode      -> states are stored detached.
"""

import logging
import os
from typing import Dict, List, Optional

import torch
import torch.nn as nn

from .gnn_layers import build_gnn_layer

logger = logging.getLogger(__name__)


class PerNodeStateCache:
    """Per-layer, per-node hidden state store: h_v^(l, t-1). Unseen nodes read as zeros."""

    def __init__(self, hidden_dim: int, num_layers: int):
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self._states: List[Dict[str, torch.Tensor]] = [dict() for _ in range(num_layers)]

    def get(self, layer: int, node_ids: List[str], device: torch.device) -> torch.Tensor:
        """Returns [N, hidden_dim]. Autograd-safe (uses stack, no in-place writes)."""
        store = self._states[layer]
        zero = torch.zeros(self.hidden_dim, device=device)
        rows = [store[n].to(device) if n in store else zero for n in node_ids]
        return torch.stack(rows) if rows else torch.zeros((0, self.hidden_dim), device=device)

    def put(
        self,
        layer: int,
        node_ids: List[str],
        states: torch.Tensor,
        detach: bool,
        mask: Optional[torch.Tensor] = None,
    ) -> None:
        """Stores states[i] for node_ids[i]. If mask is given, only rows where mask[i] is True."""
        store = self._states[layer]
        for i, nid in enumerate(node_ids):
            if mask is not None and not bool(mask[i]):
                continue
            row = states[i]
            store[nid] = row.detach().cpu() if detach else row

    def detach_all(self) -> None:
        """Truncation point of truncated BPTT: cut the graph through every cached state."""
        for store in self._states:
            for nid in list(store.keys()):
                store[nid] = store[nid].detach()

    def contains(self, layer: int, node_id: str) -> bool:
        return node_id in self._states[layer]

    def num_nodes(self, layer: int = 0) -> int:
        return len(self._states[layer])

    def remove(self, node_ids: List[str]) -> None:
        """Drop states of deleted nodes so a re-added node of the same name starts fresh."""
        for store in self._states:
            for nid in node_ids:
                store.pop(nid, None)

    def clear(self) -> None:
        for store in self._states:
            store.clear()


class RolandHierarchicalGRU(nn.Module):
    def __init__(
        self,
        in_dim: int,
        hidden_dim: int = 128,
        out_dim: int = 384,
        num_layers: int = 2,
        gnn_type: str = "GAT",
        dropout: float = 0.1,
        residual: bool = True,
    ):
        super().__init__()
        self.in_dim = in_dim
        self.hidden_dim = hidden_dim
        self.out_dim = out_dim
        self.num_layers = num_layers
        self.gnn_type = gnn_type
        self.residual = residual

        self.input_proj = nn.Linear(in_dim, hidden_dim)
        self.gnn_layers = nn.ModuleList(
            [build_gnn_layer(gnn_type, hidden_dim, hidden_dim, dropout=dropout) for _ in range(num_layers)]
        )
        self.gru_cells = nn.ModuleList(
            [nn.GRUCell(input_size=hidden_dim, hidden_size=hidden_dim) for _ in range(num_layers)]
        )
        self.readout = nn.Sequential(nn.Linear(hidden_dim, out_dim), nn.LayerNorm(out_dim))
        self.state_cache = PerNodeStateCache(hidden_dim, num_layers)

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        node_ids: List[str],
        update_cache: bool = True,
        commit_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        x:           [N, in_dim] text-embedding features
        edge_index:  [2, E] (must contain both directions for undirected graphs)
        node_ids:    length-N stable identifiers (cache keys)
        update_cache: write new states h^(l,t) back to the cache
        commit_mask: [N] bool, only these nodes are written back (others are computed
                     from partial context and must not pollute the cache)
        """
        if x.size(0) != len(node_ids):
            raise ValueError(f"x has {x.size(0)} rows but {len(node_ids)} node_ids were given")

        device = x.device
        h = self.input_proj(x)
        for l in range(self.num_layers):
            h_tilde = self.gnn_layers[l](h, edge_index)                          # Eq. 3
            h_prev_time = self.state_cache.get(l, node_ids, device)
            h = self.gru_cells[l](h_tilde, h_prev_time)                           # Eq. 5
            if update_cache:
                self.state_cache.put(l, node_ids, h, detach=not self.training, mask=commit_mask)

        out = self.readout(h)
        if self.residual and self.out_dim == self.in_dim:
            out = x + out
        return out

    def save_checkpoint(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        torch.save(
            {
                "config": {
                    "in_dim": self.in_dim, "hidden_dim": self.hidden_dim, "out_dim": self.out_dim,
                    "num_layers": self.num_layers, "gnn_type": self.gnn_type, "residual": self.residual,
                },
                "state_dict": self.state_dict(),
            },
            path,
        )
        logger.info("Saved ROLAND checkpoint to %s", path)

    @classmethod
    def from_checkpoint(cls, path: str) -> "RolandHierarchicalGRU":
        """Rebuilds the model from the architecture stored in the checkpoint (no silent shape mismatch)."""
        ckpt = torch.load(path, map_location="cpu")
        if not (isinstance(ckpt, dict) and "config" in ckpt and "state_dict" in ckpt):
            raise ValueError(
                f"{path} is an old-format checkpoint (raw state_dict, no architecture). "
                "Delete it and retrain with `python -m scripts.train_roland`."
            )
        model = cls(**ckpt["config"])
        model.load_state_dict(ckpt["state_dict"])
        model.eval()
        return model