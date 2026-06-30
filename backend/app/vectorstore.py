"""In-memory vector store scoped to a single session.

Chunks + their embeddings live in numpy arrays. Retrieval is a cosine
similarity (dot product on normalized vectors) top-k search. No external DB.
"""
from __future__ import annotations

from typing import List, Tuple

import numpy as np

from . import embeddings


class VectorStore:
    def __init__(self, chunks: List[dict]):
        self.chunks = chunks  # each: {chunk_id, chunk_text, start_ts, end_ts}
        texts = [c["chunk_text"] for c in chunks]
        self.matrix = embeddings.embed_texts(texts) if texts else np.zeros((0, 384))

    def search(self, query: str, k: int = 5) -> List[Tuple[dict, float]]:
        """Return up to k (chunk, similarity) pairs, highest similarity first."""
        if self.matrix.shape[0] == 0:
            return []
        q = embeddings.embed_query(query)
        scores = self.matrix @ q  # cosine sim (vectors are normalized)
        k = min(k, len(self.chunks))
        top_idx = np.argsort(-scores)[:k]
        return [(self.chunks[int(i)], float(scores[int(i)])) for i in top_idx]
