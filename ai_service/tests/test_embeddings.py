"""
Tests for SentenceTransformer Embedder.
"""

import pytest
import sys
import os
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.embeddings.embedder import SentenceTransformerEmbedder, cosine_similarity


def test_embed_text():
    embedder = SentenceTransformerEmbedder(embedding_dim=384)
    emb = embedder.embed_text("Knowledge graphs represent entities and relations.")
    assert isinstance(emb, np.ndarray)
    assert emb.shape[-1] == 384
    # Unit normalization check
    norm = np.linalg.norm(emb)
    assert abs(norm - 1.0) < 1e-3


def test_embed_batch():
    embedder = SentenceTransformerEmbedder(embedding_dim=384)
    texts = [
        "First document text about databases.",
        "Second text discussing machine learning models.",
        "Third sentence describing knowledge retrieval.",
    ]
    batch_emb = embedder.embed_batch(texts)
    assert batch_emb.shape == (3, 384)


def test_cosine_similarity():
    embedder = SentenceTransformerEmbedder(embedding_dim=384)
    emb1 = embedder.embed_text("artificial intelligence and machine learning")
    emb2 = embedder.embed_text("artificial intelligence and deep neural networks")
    emb3 = embedder.embed_text("recipe for baking chocolate chip cookies")

    sim_related = cosine_similarity(emb1, emb2)
    sim_unrelated = cosine_similarity(emb1, emb3)
    assert sim_related > sim_unrelated
