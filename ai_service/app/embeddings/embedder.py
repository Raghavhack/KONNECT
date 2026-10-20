"""
Sentence-Transformers Embeddings Module.
Provides fast dense vector embeddings (e.g., all-MiniLM-L6-v2), normalization,
batching, and cosine similarity calculation.
"""

import logging
import hashlib
import os
from typing import List, Union, Optional
import numpy as np
import torch
from ..config import settings

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SentenceTransformer = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False

if settings.HF_TOKEN :
    os.environ["HF_TOKEN"] = settings.HF_TOKEN
else:
    pass

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Computes cosine similarity between two 1D or 2D numpy arrays."""
    norm_a = np.linalg.norm(a, axis=-1, keepdims=True)
    norm_b = np.linalg.norm(b, axis=-1, keepdims=True)
    denom = (norm_a * norm_b) + 1e-9
    return float(np.sum((a * b) / denom))


class SentenceTransformerEmbedder:
    """
    Wraps sentence-transformers models with in-memory caching and fallback projection.
    Default model: 'all-MiniLM-L6-v2' (384 dimensions, ~15ms latency per batch).
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        embedding_dim: int = 384,
        cache_size: int = 5000,
    ):
        self.model_name = model_name

        if torch.cuda.is_available() :
            self.device = "cuda"
        else :
            self.device = "cpu"

        self.embedding_dim = embedding_dim
        self.model = None
        self._cache = {}
        self.cache_size = cache_size
        self._initialize_model()

    def _initialize_model(self) -> None:
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning(
                "sentence-transformers not installed. "
                "Embedder will use deterministic projection fallback."
            )
            return

        try:
            self.model = SentenceTransformer(self.model_name, device=self.device)
            # Determine actual embedding dimension from model
            dummy = self.model.encode("test", convert_to_numpy=True)
            self.embedding_dim = dummy.shape[-1]
            logger.info(
                f"Loaded SentenceTransformer '{self.model_name}' (dim={self.embedding_dim}) on {self.device}"
            )
        except Exception as e:
            logger.warning(
                f"Could not load SentenceTransformer '{self.model_name}' ({e}). "
            )
            raise e

    def _fallback_embed(self, text: str) -> np.ndarray:
        """
        Generates a deterministic unit-normalized pseudo-embedding for testing/fallback.
        Accumulates deterministic word-level vectors so overlapping vocabulary yields semantic similarity.
        """
        words = [w.strip().lower() for w in text.split() if w.strip()]
        if not words:
            words = [text.strip().lower() or "empty"]

        vec = np.zeros(self.embedding_dim, dtype=np.float32)
        for w in words:
            seed = int(hashlib.sha256(w.encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.RandomState(seed)
            vec += rng.randn(self.embedding_dim).astype(np.float32)

        norm = np.linalg.norm(vec)
        return vec / (norm + 1e-9)

    def embed_text(self, text: str) -> np.ndarray:
        """Embeds a single string into a 1D normalized float32 numpy array."""
        if text in self._cache:
            return self._cache[text]

        if self.model is not None:
            emb = self.model.encode(
                text,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            ).astype(np.float32)
        else:
            emb = self._fallback_embed(text)

        if len(self._cache) < self.cache_size:
            self._cache[text] = emb
        return emb

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Embeds a list of strings into a 2D numpy array [N, dim]."""
        if not texts:
            return np.empty((0, self.embedding_dim), dtype=np.float32)

        results = []
        uncached_texts = []
        uncached_indices = []

        for idx, t in enumerate(texts):
            if t in self._cache:
                results.append((idx, self._cache[t]))
            else:
                uncached_texts.append(t)
                uncached_indices.append(idx)

        if uncached_texts:
            if self.model is not None:
                new_embs = self.model.encode(
                    uncached_texts,
                    batch_size=batch_size,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                ).astype(np.float32)
            else:
                new_embs = np.array([self._fallback_embed(t) for t in uncached_texts], dtype=np.float32)

            for text, emb, orig_idx in zip(uncached_texts, new_embs, uncached_indices):
                if len(self._cache) < self.cache_size:
                    self._cache[text] = emb
                results.append((orig_idx, emb))

        results.sort(key=lambda x: x[0])
        return np.array([r[1] for r in results], dtype=np.float32)

    def compute_similarity(self, text_a: str, text_b: str) -> float:
        """Computes cosine similarity between two text strings."""
        emb_a = self.embed_text(text_a)
        emb_b = self.embed_text(text_b)
        return float(np.dot(emb_a, emb_b))
