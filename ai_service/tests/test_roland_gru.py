"""
Tests for ROLAND Dynamic Graph GRU (Equations 5-7), State Cache, and Truncated-BPTT.
"""

import pytest
import sys
import os
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.gnn.roland_gru import RolandHierarchicalGRU, PerNodeStateCache
from app.gnn.trainer import TruncatedBPTTTrainer, DynamicGraphSnapshot

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False


def test_per_node_state_cache():
    cache = PerNodeStateCache(hidden_dim=64)
    node_ids = ["node_A", "node_B"]

    # Initial states should be zeros
    states_0 = cache.get_states(layer_idx=0, node_ids=node_ids, use_torch=False)
    assert states_0.shape == (2, 64)
    assert np.all(states_0 == 0.0)

    # Update states
    new_states = np.ones((2, 64), dtype=np.float32) * 0.5
    cache.update_states(layer_idx=0, node_ids=node_ids, new_states=new_states)

    # Verify retrieval
    retrieved = cache.get_states(layer_idx=0, node_ids=node_ids, use_torch=False)
    assert np.allclose(retrieved, 0.5)


def test_roland_hierarchical_gru_forward():
    in_dim = 32
    hidden_dim = 64
    out_dim = 32
    num_layers = 2

    model = RolandHierarchicalGRU(
        in_dim=in_dim,
        hidden_dim=hidden_dim,
        out_dim=out_dim,
        num_layers=num_layers,
    )

    node_ids = ["ent_1", "ent_2", "ent_3"]
    N = len(node_ids)

    # Snapshot t=1: 3 nodes, 2 edges
    features_t1 = np.random.randn(N, in_dim).astype(np.float32)
    edge_index_t1 = np.array([[0, 1], [1, 2]], dtype=np.int64)

    if TORCH_AVAILABLE and isinstance(model, torch.nn.Module):
        x_t = torch.tensor(features_t1)
        edge_t = torch.tensor(edge_index_t1)
        out_t1 = model(x=x_t, edge_index=edge_t, node_ids=node_ids, update_cache=True)
        assert out_t1.shape == (N, out_dim)
    else:
        out_t1 = model.forward(x=features_t1, edge_index=edge_index_t1, node_ids=node_ids, update_cache=True)
        assert out_t1.shape == (N, out_dim)

    # Check that cache for all layers is now populated
    for l in range(num_layers):
        assert model.state_cache.contains(l, "ent_1")
        assert model.state_cache.contains(l, "ent_2")
        assert model.state_cache.contains(l, "ent_3")

    # Snapshot t=2: ent_4 is newly added
    node_ids_t2 = ["ent_1", "ent_2", "ent_3", "ent_4"]
    features_t2 = np.random.randn(4, in_dim).astype(np.float32)
    edge_index_t2 = np.array([[0, 1, 2], [1, 2, 3]], dtype=np.int64)

    if TORCH_AVAILABLE and isinstance(model, torch.nn.Module):
        x_t2 = torch.tensor(features_t2)
        edge_t2 = torch.tensor(edge_index_t2)
        out_t2 = model(x=x_t2, edge_index=edge_t2, node_ids=node_ids_t2, update_cache=True)
        assert out_t2.shape == (4, out_dim)
    else:
        out_t2 = model.forward(x=features_t2, edge_index=edge_index_t2, node_ids=node_ids_t2, update_cache=True)
        assert out_t2.shape == (4, out_dim)

    assert model.state_cache.contains(0, "ent_4")


def test_truncated_bptt_trainer():
    if not TORCH_AVAILABLE:
        pytest.skip("PyTorch not installed; skipping gradient training test")

    in_dim = 16
    hidden_dim = 32
    out_dim = 16

    model = RolandHierarchicalGRU(
        in_dim=in_dim, hidden_dim=hidden_dim, out_dim=out_dim, num_layers=2
    )

    trainer = TruncatedBPTTTrainer(model=model, lr=0.01, window_size=2)

    # Create synthetic snapshots
    snapshots = []
    for step in range(4):
        nodes = [f"n_{i}" for i in range(5)]
        feat = np.random.randn(5, in_dim).astype(np.float32)
        pos = np.array([[0, 1, 2], [1, 2, 3]], dtype=np.int64)
        neg = np.array([[0, 3], [4, 1]], dtype=np.int64)
        snapshots.append(DynamicGraphSnapshot(timestamp=float(step), node_ids=nodes, features=feat, pos_edges=pos, neg_edges=neg))

    losses = trainer.train_dynamic_stream(snapshots=snapshots, epochs=2)
    assert len(losses) == 2
    assert all(isinstance(l, float) for l in losses)
