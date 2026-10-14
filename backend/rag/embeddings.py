from functools import lru_cache

import numpy as np
from fastembed import TextEmbedding

from config import EMBEDDING_MODEL, MODEL_CACHE_DIR


@lru_cache(maxsize=1)
def get_embedding_model() -> TextEmbedding:
    return TextEmbedding(
        model_name=EMBEDDING_MODEL,
        cache_dir=str(MODEL_CACHE_DIR),
    )


def _normalize(vectors: list[np.ndarray] | np.ndarray) -> np.ndarray:
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms > 0)


def embed_texts(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.empty((0, 0), dtype=np.float32)
    return _normalize(list(get_embedding_model().embed(texts)))


def embed_query(text: str) -> np.ndarray:
    return embed_texts([text])[0]