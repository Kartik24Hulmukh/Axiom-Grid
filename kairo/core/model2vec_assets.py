"""Load local model2vec-format inference assets without hub resolution.

Model2Vec 0.9.0's persistence loader leaves config.json unclosed. Keep resource
ownership here, using the public StaticModel constructor and unchanged tensors,
tokenizer and normalization config. This deliberately supports only the flat
model2vec layout vendored by Kairo, not hub IDs or sentence-transformer layouts.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_local_static_model(model_dir: str | Path):
    """Load real local assets; missing/malformed files fail without network fallback."""
    from model2vec import StaticModel
    from model2vec.modelcards import get_metadata_from_readme
    from safetensors import safe_open
    from tokenizers import Tokenizer

    folder = Path(model_dir)
    with (folder / "config.json").open(encoding="utf-8") as config_file:
        config = json.load(config_file)
    with safe_open(folder / "model.safetensors", framework="numpy") as tensors:
        vectors = tensors.get_tensor("embeddings")
        keys = set(tensors.keys())
        weights = tensors.get_tensor("weights") if "weights" in keys else None
        mapping = tensors.get_tensor("mapping") if "mapping" in keys else None
    tokenizer = Tokenizer.from_file(str(folder / "tokenizer.json"))
    readme = folder / "README.md"
    metadata = get_metadata_from_readme(readme) if readme.is_file() else {}
    return StaticModel(
        vectors=vectors,
        tokenizer=tokenizer,
        config=config,
        weights=weights,
        token_mapping=mapping,
        base_model_name=metadata.get("base_model"),
        language=metadata.get("language"),
    )
