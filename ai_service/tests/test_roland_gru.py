"""
Behavioural tests for the ROLAND GRU, state cache, bounded k-hop update and trainer.
These check *properties* (gradient flow through time, exact-commit radius, learnability),
not just output shapes, so a wrong implementation fails them.
"""

import os
import random
import sys

import numpy as np
import pytest
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.gnn.neighborhood import BoundedNeighborhoodManager, hop_distances
from app.gnn.roland_gru import PerNodeStateCache, RolandHierarchicalGRU
from app.gnn.trainer import DynamicGraphSnapshot, TruncatedBPTTTrainer, roc_auc, split_stream

DIM = 8


def make_model(**kw):
    torch.manual_seed(0)
    args = dict(in_dim=DIM, hidden_dim=16, out_dim=DIM, num_layers=2, gnn_type="GAT", dropout=0.0)
    args.update(kw)
    return RolandHierarchicalGRU(**args)


def chain_edges(n):
    s = list(range(n - 1)); d = list(range(1, n))
    return torch.tensor([s + d, d + s], dtype=torch.long)


# ------------------------------------------------------------------ state cache
def test_cache_unseen_nodes_read_as_zero_and_roundtrip():
    c = PerNodeStateCache(hidden_dim=4, num_layers=2)
    assert torch.all(c.get(0, ["a", "b"], torch.device("cpu")) == 0)
    c.put(0, ["a", "b"], torch.ones(2, 4) * 0.5, detach=True)
    got = c.get(0, ["b", "zzz"], torch.device("cpu"))
    assert torch.allclose(got[0], torch.full((4,), 0.5)) and torch.all(got[1] == 0)
    assert c.contains(0, "a") and not c.contains(1, "a")


def test_cache_mask_and_remove():
    c = PerNodeStateCache(hidden_dim=4, num_layers=1)
    c.put(0, ["a", "b", "c"], torch.ones(3, 4), detach=True, mask=torch.tensor([True, False, True]))
    assert c.contains(0, "a") and not c.contains(0, "b") and c.contains(0, "c")
    c.remove(["a"])
    assert not c.contains(0, "a")


# ------------------------------------------------------------------ truncated-BPTT mechanics
def test_gradient_flows_through_cached_state_in_train_mode():
    """Output at t=2 must depend (differentiably) on the input at t=1 via the cached state."""
    m = make_model(); m.train()
    ids = ["a", "b", "c"]
    x1 = torch.randn(3, DIM, requires_grad=True)
    x2 = torch.randn(3, DIM)
    ei = chain_edges(3)
    m(x1, ei, ids, update_cache=True)
    out2 = m(x2, ei, ids, update_cache=True)
    out2.pow(2).sum().backward()      # NB: .sum() alone is identically 0 through a LayerNorm output
    assert x1.grad is not None and x1.grad.abs().sum() > 0


def test_detach_all_truncates_the_graph():
    m = make_model(); m.train()
    ids = ["a", "b", "c"]
    x1 = torch.randn(3, DIM, requires_grad=True)
    ei = chain_edges(3)
    m(x1, ei, ids, update_cache=True)
    m.state_cache.detach_all()
    out2 = m(torch.randn(3, DIM), ei, ids, update_cache=True)
    out2.pow(2).sum().backward()
    assert m.input_proj.weight.grad is not None       # the backward pass did run...
    assert x1.grad is None                            # ...but nothing flows back past the truncation point


def test_eval_mode_stores_detached_states():
    m = make_model(); m.eval()
    with torch.no_grad():
        m(torch.randn(3, DIM), chain_edges(3), ["a", "b", "c"], update_cache=True)
    for l in range(m.num_layers):
        assert not m.state_cache.get(l, ["a"], torch.device("cpu")).requires_grad


# ------------------------------------------------------------------ recurrence semantics
def test_history_changes_the_output_but_no_commit_does_not():
    m = make_model(); m.eval()
    ids = ["a", "b", "c"]; x = torch.randn(3, DIM); ei = chain_edges(3)
    with torch.no_grad():
        first = m(x, ei, ids, update_cache=False)
        again = m(x, ei, ids, update_cache=False)
        assert torch.allclose(first, again)                 # deterministic, cache untouched
        m(x, ei, ids, update_cache=True)                    # commit state
        after = m(x, ei, ids, update_cache=False)
    assert not torch.allclose(first, after, atol=1e-6)      # GRU state really feeds the output


def test_commit_mask_only_writes_selected_nodes():
    m = make_model(); m.eval()
    ids = ["a", "b", "c"]
    with torch.no_grad():
        m(torch.randn(3, DIM), chain_edges(3), ids, update_cache=True,
          commit_mask=torch.tensor([True, False, False]))
    assert m.state_cache.contains(0, "a") and not m.state_cache.contains(0, "b")


def test_mismatched_node_ids_rejected():
    with pytest.raises(ValueError):
        make_model()(torch.randn(3, DIM), chain_edges(3), ["a", "b"])


def test_checkpoint_roundtrip(tmp_path):
    m = make_model(); m.eval()
    p = str(tmp_path / "m.pt"); m.save_checkpoint(p)
    m2 = RolandHierarchicalGRU.from_checkpoint(p)
    x = torch.randn(3, DIM); ei = chain_edges(3)
    with torch.no_grad():
        assert torch.allclose(m(x, ei, ["a", "b", "c"], update_cache=False),
                              m2(x, ei, ["a", "b", "c"], update_cache=False), atol=1e-6)


# ------------------------------------------------------------------ bounded k-hop update
def chain_nodes(n):
    rng = np.random.RandomState(0)
    return ([{"name": f"N{i}", "embedding": rng.randn(DIM).tolist()} for i in range(n)],
            [{"src": f"N{i}", "tgt": f"N{i+1}"} for i in range(n - 1)])


def test_hop_distances_on_chain():
    d = hop_distances(["N0"], [f"N{i}" for i in range(5)], [(f"N{i}", f"N{i+1}") for i in range(4)])
    assert d == {f"N{i}": i for i in range(5)}


def test_bounded_update_commits_only_nodes_with_exact_receptive_field():
    m = make_model()                                    # L = 2
    mgr = BoundedNeighborhoodManager(m, default_k=4)    # commit radius = k - L = 2
    nodes, edges = chain_nodes(7)
    updated, metrics = mgr.run_bounded_update(["N0"], nodes, edges, k=4)
    assert set(updated) == {"N0", "N1", "N2"}
    assert metrics["affected_nodes"] == 7 and metrics["committed_nodes"] == 3
    assert not m.state_cache.contains(0, "N3")          # boundary context never pollutes the cache


def test_k_smaller_than_layers_commits_seeds_only():
    mgr = BoundedNeighborhoodManager(make_model(), default_k=1)
    nodes, edges = chain_nodes(5)
    updated, _ = mgr.run_bounded_update(["N0"], nodes, edges, k=1)
    assert set(updated) == {"N0"}


def test_nodes_without_text_embedding_are_skipped_not_invented():
    mgr = BoundedNeighborhoodManager(make_model(), default_k=4)
    nodes, edges = chain_nodes(3)
    nodes.append({"name": "ghost"})                     # no embedding
    updated, _ = mgr.run_bounded_update(["N0", "ghost"], nodes, edges, k=4)
    assert "ghost" not in updated


def test_same_edit_applied_twice_is_stable_for_unchanged_nodes_when_not_committed():
    """Guard for drift: with commit radius 0 (k=L) far nodes keep their old cached state."""
    m = make_model(); mgr = BoundedNeighborhoodManager(m, default_k=2)
    nodes, edges = chain_nodes(6)
    mgr.run_bounded_update(["N0"], nodes, edges, k=4)
    before = m.state_cache.get(0, ["N1"], torch.device("cpu")).clone()
    mgr.run_bounded_update(["N5"], nodes, edges, k=2)   # edit far away, radius 0
    assert torch.allclose(before, m.state_cache.get(0, ["N1"], torch.device("cpu")))


# ------------------------------------------------------------------ trainer
def test_roc_auc_known_values():
    assert roc_auc(torch.tensor([0.1, 0.2, 0.8, 0.9]), torch.tensor([0., 0., 1., 1.])) == 1.0
    assert roc_auc(torch.tensor([0.9, 0.8, 0.2, 0.1]), torch.tensor([0., 0., 1., 1.])) == 0.0
    assert roc_auc(torch.tensor([0.5, 0.5]), torch.tensor([1., 1.])) == 0.5


def test_split_stream_is_chronological_and_disjoint():
    snaps = [None] * 20
    tr, va, te = split_stream(snaps, 0.7, 0.15)
    assert list(tr) == list(range(14)) and list(va) == [14, 15, 16] and list(te) == [17, 18, 19]


def make_growing_stream(noise=1.5, n_nodes=60, n_clusters=5, steps=16, seed=0):
    """Clustered features with heavy noise; same-cluster edges are born at random times and
    persist. Raw features alone are only moderately predictive; aggregating over the existing
    graph (message passing) denoises them, so a model that learns must beat the raw baseline."""
    rng = np.random.RandomState(seed)
    cluster = np.arange(n_nodes) % n_clusters
    centers = rng.randn(n_clusters, DIM)
    feats = (centers[cluster] + noise * rng.randn(n_nodes, DIM)).astype(np.float32)
    ids = [f"n{i}" for i in range(n_nodes)]
    pairs = [(i, j) for i in range(n_nodes) for j in range(i + 1, n_nodes) if cluster[i] == cluster[j]]
    born = {p: rng.randint(0, steps) for p in pairs}
    snaps = []
    for t in range(steps):
        es = [p for p in pairs if born[p] <= t]
        arr = np.array(es, dtype=np.int64).T if es else np.empty((2, 0), dtype=np.int64)
        snaps.append(DynamicGraphSnapshot(float(t), ids, feats, arr))
    return snaps


def raw_feature_baseline_auc(trainer, snaps, eval_range):
    """Link prediction by dot product of the raw text embeddings (no graph, no learning)."""
    S, L = [], []
    for t in eval_range:
        if t + 1 >= len(snaps):
            continue
        tgt = trainer._targets(snaps[t], snaps[t + 1], "cpu")
        if tgt is None:
            continue
        pairs, labels = tgt
        x = torch.tensor(snaps[t].features)
        S.append((x[pairs[0]] * x[pairs[1]]).sum(-1)); L.append(labels)
    return roc_auc(torch.cat(S), torch.cat(L))


def test_trained_model_beats_raw_embeddings_and_untrained_model_on_held_out_future():
    """Averaged over 3 independent streams so one lucky/unlucky seed cannot decide the result."""
    raws, untrained, trained = [], [], []
    for seed in range(3):
        random.seed(seed); torch.manual_seed(seed)
        snaps = make_growing_stream(seed=seed)
        _, _, te = split_stream(snaps)
        trainer = TruncatedBPTTTrainer(make_model(), lr=0.01, window_size=3, seed=seed)
        raws.append(raw_feature_baseline_auc(trainer, snaps, te))
        untrained.append(trainer.evaluate(snaps, te)["auc"])
        hist = trainer.train(snaps, epochs=30, patience=8)
        assert hist["train_loss"][-1] < hist["train_loss"][0]
        trained.append(trainer.evaluate(snaps, te)["auc"])
    raw, un, tr = np.mean(raws), np.mean(untrained), np.mean(trained)
    assert tr > raw + 0.08, f"trained {tr:.3f} vs raw-embedding baseline {raw:.3f}"
    assert tr > un + 0.10, f"trained {tr:.3f} vs untrained {un:.3f}"


def test_evaluation_never_trains_and_is_repeatable():
    random.seed(0); torch.manual_seed(0)
    snaps = make_growing_stream(steps=12)
    trainer = TruncatedBPTTTrainer(make_model(), seed=0)
    _, _, te = split_stream(snaps)
    before = {k: v.clone() for k, v in trainer.model.state_dict().items()}
    a = trainer.evaluate(snaps, te)["auc"]
    trainer.rng = random.Random(0)
    b = trainer.evaluate(snaps, te)["auc"]
    assert a == b
    assert all(torch.equal(before[k], v) for k, v in trainer.model.state_dict().items())