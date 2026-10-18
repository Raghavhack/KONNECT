"""
ROLAND Dynamic Graph Learning Framework - Hierarchical GRU State Update (Eq. 5-7).
Core Research Contribution - Implemented From Scratch.

Maintains per-node temporal hidden states across snapshots/edits, updating representations
hierarchically across GNN layers with bounded neighborhood latency.
"""

import logging
from typing import List, Dict, Tuple, Optional, Any
import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    nn = None
    TORCH_AVAILABLE = False

from .gnn_layers import build_gnn_layer


class PerNodeStateCache:
    """
    Per-node hierarchical hidden state cache.
    Stores h_v^(l, t-1) indexed by layer index and unique entity identifier.
    Provides fast O(1) state lookup and delta-bounded updates.
    """

    def __init__(self, hidden_dim: int):
        self.hidden_dim = hidden_dim
        # Map: layer_idx -> {node_id -> state (Tensor or np.ndarray)}
        self.cache: Dict[int, Dict[str, Any]] = {}

    def get_layer_cache(self, layer_idx: int) -> Dict[str, Any]:
        if layer_idx not in self.cache:
            self.cache[layer_idx] = {}
        return self.cache[layer_idx]

    def get_states(
        self,
        layer_idx: int,
        node_ids: List[str],
        device: Optional[Any] = None,
        use_torch: bool = True,
    ) -> Any:
        """
        Retrieves hidden states for the specified node IDs at layer l.
        Initializes missing nodes with zeros (or small Gaussian noise).
        """
        layer_c = self.get_layer_cache(layer_idx)
        num_nodes = len(node_ids)

        if use_torch and TORCH_AVAILABLE:
            states = torch.zeros((num_nodes, self.hidden_dim), device=device, dtype=torch.float32)
            for i, nid in enumerate(node_ids):
                if nid in layer_c:
                    cached = layer_c[nid]
                    if isinstance(cached, torch.Tensor):
                        states[i] = cached.to(device)
                    else:
                        states[i] = torch.tensor(cached, device=device, dtype=torch.float32)
            return states
        else:
            arr = np.zeros((num_nodes, self.hidden_dim), dtype=np.float32)
            for i, nid in enumerate(node_ids):
                if nid in layer_c:
                    cached = layer_c[nid]
                    if isinstance(cached, np.ndarray):
                        arr[i] = cached
                    else:
                        arr[i] = np.array(cached, dtype=np.float32)
            return arr

    def update_states(
        self,
        layer_idx: int,
        node_ids: List[str],
        new_states: Any,
    ) -> None:
        """
        Updates the cached representations h_v^(l, t) for nodes in this snapshot.
        """
        layer_c = self.get_layer_cache(layer_idx)
        for i, nid in enumerate(node_ids):
            state = new_states[i]
            if TORCH_AVAILABLE and isinstance(state, torch.Tensor):
                layer_c[nid] = state.detach().cpu()
            else:
                layer_c[nid] = np.array(state, dtype=np.float32)

    def contains(self, layer_idx: int, node_id: str) -> bool:
        return node_id in self.get_layer_cache(layer_idx)

    def clear(self) -> None:
        self.cache.clear()


if TORCH_AVAILABLE:
    class RolandHierarchicalGRU(nn.Module):
        """
        PyTorch Implementation of ROLAND Dynamic Graph GRU.
        Implements Equations 5, 6, and 7:

        Eq. 5: ~h_v^(l, t) = GNN^(l)( { h_u^(l-1, t) : u in N(v) } )  [Spatial Message Passing]
        Eq. 6:  h_v^(l, t) = GRU^(l)( ~h_v^(l, t), h_v^(l, t-1) )     [Recurrent Temporal Update]
        Eq. 7:  h_v^(l, t) -> Input to Layer l+1                     [Hierarchical Passing]
        """

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

            # Initial feature projection
            self.input_proj = nn.Linear(in_dim, hidden_dim)

            # Hierarchical GNN layers and GRU cells
            self.gnn_layers = nn.ModuleList()
            self.gru_cells = nn.ModuleList()

            for _ in range(num_layers):
                gnn_l = build_gnn_layer(gnn_type, in_dim=hidden_dim, out_dim=hidden_dim, dropout=dropout)
                self.gnn_layers.append(gnn_l)
                # torch.nn.GRUCell as the recurrence primitive
                self.gru_cells.append(nn.GRUCell(input_size=hidden_dim, hidden_size=hidden_dim))

            # Readout projection to output embedding dimension
            self.readout = nn.Sequential(
                nn.Linear(hidden_dim, out_dim),
                nn.LayerNorm(out_dim),
            )

            # Per-node state cache
            self.state_cache = PerNodeStateCache(hidden_dim=hidden_dim)

        def forward(
            self,
            x: torch.Tensor,
            edge_index: torch.Tensor,
            node_ids: List[str],
            update_cache: bool = True,
        ) -> torch.Tensor:
            """
            Performs the ROLAND forward pass on the (sub)graph.

            x: [N, in_dim] Node initial features (text embeddings)
            edge_index: [2, E] Graph edges
            node_ids: [N] Identifier of each node in x
            update_cache: bool, whether to commit updated states to state_cache
            """
            device = x.device
            # Layer 0: Project input features
            h_prev_layer = self.input_proj(x)  # [N, hidden_dim]

            # Hierarchical update across L GNN layers (Eq. 5-7)
            for l in range(self.num_layers):
                # Eq. 5: Spatial Message Passing to get candidate representation ~h^(l, t)
                h_tilde = self.gnn_layers[l](h_prev_layer, edge_index)

                # Retrieve previous temporal hidden state h^(l, t-1) from cache
                h_prev_time = self.state_cache.get_states(
                    layer_idx=l, node_ids=node_ids, device=device, use_torch=True
                )

                # Eq. 6: Recurrent temporal update using GRUCell primitive
                h_curr = self.gru_cells[l](h_tilde, h_prev_time)

                # Eq. 7: Feed updated state h^(l, t) to layer l+1
                h_prev_layer = h_curr

                # Cache state update
                if update_cache:
                    self.state_cache.update_states(
                        layer_idx=l, node_ids=node_ids, new_states=h_curr
                    )

            # Final embedding readout with residual connection to text embedding space
            proj_h = self.readout(h_prev_layer)
            if self.residual and self.out_dim == self.in_dim:
                out_embeddings = x + proj_h
            else:
                out_embeddings = proj_h
            return out_embeddings

        def save_checkpoint(self, path: str) -> None:
            """
            Saves PyTorch model weights to disk.
            """
            import os
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            torch.save(self.state_dict(), path)
            logger.info(f"Saved ROLAND model checkpoint to {path}")

        def load_checkpoint(self, path: str) -> bool:
            """
            Loads PyTorch model weights from disk.
            """
            import os
            if not os.path.exists(path):
                return False
            try:
                state_dict = torch.load(path, map_location="cpu")
                self.load_state_dict(state_dict)
                logger.info(f"Successfully loaded ROLAND model checkpoint from {path}")
                return True
            except Exception as e:
                logger.warning(f"Failed to load ROLAND checkpoint from {path}: {e}")
                return False

else:
    raise ValueError("PyTorch Not installed.")