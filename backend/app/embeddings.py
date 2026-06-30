"""Local embeddings via sentence-transformers/all-MiniLM-L6-v2.

The model is loaded lazily and cached process-wide (it's a singleton: loading
it is the expensive part, ~80MB download on first run). All embeddings are
L2-normalized so a dot product equals cosine similarity.
"""
from __future__ import annotations

import threading
from typing import List

import numpy as np

from . import config

_model = None
_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                # Imported here so the heavy torch import only happens on first use.
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(config.EMBEDDING_MODEL)
    return _model


def embed_texts(texts: List[str]) -> np.ndarray:
    """Return a (n, dim) float32 array of normalized embeddings."""
    model = get_model()
    vecs = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return np.asarray(vecs, dtype=np.float32)


def embed_query(text: str) -> np.ndarray:
    return embed_texts([text])[0]
