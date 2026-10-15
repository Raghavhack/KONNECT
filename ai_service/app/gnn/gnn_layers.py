"""
Base GNN Message Passing Layers.
Supports PyTorch Geometric (PyG) GAT and GraphSAGE layers,
with pure PyTorch fallback implementations to ensure cross-platform resilience.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    nn = None
    F = None
    TORCH_AVAILABLE = False

try:
    from torch_geometric.nn import GATConv, SAGEConv
    PYG_AVAILABLE = True
except ImportError:
    GATConv = None
    SAGEConv = None
    PYG_AVAILABLE = False


if TORCH_AVAILABLE:
    class PurePyTorchGATLayer(nn.Module):
        """
        Pure PyTorch implementation of Graph Attention Network (GAT) layer.
        Used as a standard fallback when PyG native C++ binaries are not present.
        """

        def __init__(self, in_dim: int, out_dim: int, heads: int = 1, dropout: float = 0.1):
            super().__init__()
            self.in_dim = in_dim
            self.out_dim = out_dim
            self.heads = heads
            self.fc = nn.Linear(in_dim, out_dim * heads, bias=False)
            self.attn_src = nn.Parameter(torch.zeros(size=(1, heads, out_dim)))
            self.attn_dst = nn.Parameter(torch.zeros(size=(1, heads, out_dim)))
            nn.init.xavier_uniform_(self.attn_src.data, gain=1.414)
            nn.init.xavier_uniform_(self.attn_dst.data, gain=1.414)
            self.leaky_relu = nn.LeakyReLU(0.2)
            self.dropout = nn.Dropout(dropout)

        def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
            """
            x: [N, in_dim]
            edge_index: [2, E]
            """
            N = x.size(0)
            h = self.fc(x).view(N, self.heads, self.out_dim)

            if edge_index.size(1) == 0:
                return h.mean(dim=1)

            src, dst = edge_index[0], edge_index[1]
            alpha_src = (h[src] * self.attn_src).sum(dim=-1)  # [E, heads]
            alpha_dst = (h[dst] * self.attn_dst).sum(dim=-1)  # [E, heads]
            alpha = self.leaky_relu(alpha_src + alpha_dst)

            # Softmax normalization per destination node
            # For simplicity, exponential weighting with self-loops
            exp_alpha = torch.exp(alpha - alpha.max())
            denom = torch.zeros(N, self.heads, device=x.device)
            denom.index_add_(0, dst, exp_alpha)
            denom = denom + 1e-9

            # Message aggregation
            weighted_msg = h[src] * exp_alpha.unsqueeze(-1)  # [E, heads, out_dim]
            out = torch.zeros(N, self.heads, self.out_dim, device=x.device)
            out.index_add_(0, dst, weighted_msg)
            out = out / denom.unsqueeze(-1)
            out = self.dropout(out)
            return out.mean(dim=1)  # Average heads -> [N, out_dim]

    class PurePyTorchSAGELayer(nn.Module):
        """Pure PyTorch implementation of GraphSAGE with Mean Aggregation."""

        def __init__(self, in_dim: int, out_dim: int):
            super().__init__()
            self.lin_self = nn.Linear(in_dim, out_dim, bias=True)
            self.lin_neigh = nn.Linear(in_dim, out_dim, bias=False)

        def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
            N = x.size(0)
            h_self = self.lin_self(x)
            if edge_index.size(1) == 0:
                return F.relu(h_self)

            src, dst = edge_index[0], edge_index[1]
            deg = torch.zeros(N, 1, device=x.device)
            deg.index_add_(0, dst, torch.ones(edge_index.size(1), 1, device=x.device))
            deg = torch.clamp(deg, min=1.0)

            neigh_sum = torch.zeros(N, x.size(1), device=x.device)
            neigh_sum.index_add_(0, dst, x[src])
            neigh_mean = neigh_sum / deg

            h_neigh = self.lin_neigh(neigh_mean)
            return F.relu(h_self + h_neigh)

    def build_gnn_layer(layer_type: str, in_dim: int, out_dim: int, heads: int = 1, dropout: float = 0.1) -> nn.Module:
        """Constructs GNN layer, preferring PyG if available, else pure PyTorch fallback."""
        if PYG_AVAILABLE:
            if layer_type.upper() == "GAT":
                return GATConv(in_dim, out_dim, heads=heads, concat=False, dropout=dropout)
            else:
                return SAGEConv(in_dim, out_dim, aggr="mean")
        else:
            if layer_type.upper() == "GAT":
                return PurePyTorchGATLayer(in_dim, out_dim, heads=heads, dropout=dropout)
            else:
                return PurePyTorchSAGELayer(in_dim, out_dim)

else:
    # Dummy placeholder when torch is completely uninstalled
    class BuildGNNPlaceholder:
        def __init__(self, *args, **kwargs):
            pass
    def build_gnn_layer(*args, **kwargs):
        return None
