"""
Kairo Phantom — Embeddings interface (SPEC §S3)
Provides local embedding extraction with graceful degradation to word-hashing.
"""
from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence

logger = logging.getLogger(__name__)

# Default dimensions
EMBEDDING_DIM = 384

def get_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Calculate a normalized embedding vector for the text.
    Falls back to a deterministic word-frequency hashing vector when offline/no models.
    """
    try:
        import numpy as np
    except ImportError:
        # Non-numpy fallback
        import math
        vec = [0.0] * dim
        words = text.lower().split()
        if not words:
            return vec
        for word in words:
            h = hashlib.sha256(word.encode('utf-8')).digest()
            for idx in range(4):
                slot = int.from_bytes(h[idx*2:(idx+1)*2], 'little') % dim
                val = (h[idx*2+8] / 255.0) * 2.0 - 1.0
                vec[slot] += val
        sq_sum = sum(x*x for x in vec)
        norm = math.sqrt(sq_sum)
        if norm > 0:
            return [x / norm for x in vec]
        return vec

    # Numpy-based calculation
    import numpy as np
    vec = np.zeros(dim)
    words = text.lower().split()
    if not words:
        return vec.tolist()
    for word in words:
        h = hashlib.sha256(word.encode('utf-8')).digest()
        for idx in range(4):
            slot = int.from_bytes(h[idx*2:(idx+1)*2], 'little') % dim
            val = (h[idx*2+8] / 255.0) * 2.0 - 1.0
            vec[slot] += val
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()

def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
    """Calculate the cosine similarity between two vectors."""
    try:
        import numpy as np
        a = np.array(v1)
        b = np.array(v2)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
    except Exception:  # noqa: BLE001 -- isolate optional engine or worker failure at boundary
        # Non-numpy fallback
        import math
        dot = sum(x*y for x, y in zip(v1, v2))
        norm_a = math.sqrt(sum(x*x for x in v1))
        norm_b = math.sqrt(sum(x*x for x in v2))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
