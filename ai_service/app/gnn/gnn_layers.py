"""
Base GNN message-passing layers.

Per the architecture doc, standard message passing is a *library* component
(PyTorch Geometric). PyG is a hard requirement: there is no silent fallback to a
hand-written layer, because a fallback would be a different model and a checkpoint
trained with one would not behave the same with the other.
"""

import torch.nn as nn

try:
    from torch_geometric.nn import GATConv, SAGEConv
except ImportError as e:  # fail fast and loudly
    raise ImportError(
        "torch_geometric is required (pip install torch_geometric). "
        "KONNECT does not ship a fallback GNN layer."
    ) from e


def build_gnn_layer(layer_type: str, in_dim: int, out_dim: int, heads: int = 1, dropout: float = 0.1) -> nn.Module:
    """Builds one message-passing layer. layer_type: 'GAT' or 'GraphSAGE'."""
    kind = layer_type.upper()
    if kind == "GAT":
        # GATConv adds self-loops by default, so isolated nodes keep their own features.
        return GATConv(in_dim, out_dim, heads=heads, concat=False, dropout=dropout)
    if kind in ("GRAPHSAGE", "SAGE"):
        return SAGEConv(in_dim, out_dim, aggr="mean")
    raise ValueError(f"Unknown gnn_type '{layer_type}'. Use 'GAT' or 'GraphSAGE'.")