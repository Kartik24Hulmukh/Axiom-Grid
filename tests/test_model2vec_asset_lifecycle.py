"""Real-model resource ownership regressions; no model mocks or warning filters."""

import builtins
import gc
import json
import socket
from contextlib import ExitStack
from pathlib import Path

import numpy as np
import pytest
from model2vec import StaticModel

from kairo.core.model2vec_assets import load_local_static_model

MODEL_DIR = Path(__file__).resolve().parents[1] / "kairo-sidecar/assets/models/potion-base-8M"


def test_local_loader_matches_real_upstream_without_egress(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Local model loading attempted network access")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    monkeypatch.setattr(socket, "gethostbyname", denied)
    # Own upstream's leaked config handle in the reference harness only. This
    # calls the actual unmodified public upstream loader and real encode path.
    original_open = builtins.open
    with ExitStack() as files:
        def owned_open(*args, **kwargs):
            return files.enter_context(original_open(*args, **kwargs))

        with monkeypatch.context() as reference_patch:
            reference_patch.setattr(builtins, "open", owned_open)
            reference = StaticModel.from_pretrained(MODEL_DIR, force_download=False)
    actual = load_local_static_model(MODEL_DIR)
    assert actual.dim == reference.dim == 256
    assert actual.normalize == reference.normalize is True
    assert actual.config == reference.config
    assert actual.tokens == reference.tokens
    assert actual.base_model_name == reference.base_model_name
    assert actual.language == reference.language
    np.testing.assert_array_equal(actual.embedding, reference.embedding)
    texts = ["How many people work there?", "Total revenue in fiscal year 2025", "", "Unicode: café 東京"]
    np.testing.assert_array_equal(actual.encode(texts), reference.encode(texts))
    del actual, reference
    gc.collect()


@pytest.mark.parametrize("malformed", [False, True])
def test_config_handle_closed_on_success_and_failure(tmp_path, monkeypatch, malformed):
    opened = []
    original_open = Path.open

    def tracked_open(path, *args, **kwargs):
        handle = original_open(path, *args, **kwargs)
        if path.name == "config.json":
            opened.append(handle)
        return handle

    monkeypatch.setattr(Path, "open", tracked_open)
    if malformed:
        (tmp_path / "config.json").write_text("{invalid", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_local_static_model(tmp_path)
    else:
        model = load_local_static_model(MODEL_DIR)
        assert model.dim == 256
    assert opened and all(handle.closed for handle in opened)
    gc.collect()


def test_missing_local_assets_fail_without_hub_fallback(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Missing local assets attempted network access")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    with pytest.raises(FileNotFoundError):
        load_local_static_model(tmp_path)


def test_retrieval_repo_only_layout_uses_real_local_loader(monkeypatch):
    from kairo.docintel.retrieval import RetrievalIndex

    original_import = builtins.__import__

    def repo_only_import(name, *args, **kwargs):
        if name == "sidecar.model_paths":
            raise ModuleNotFoundError("sidecar not installed in repo-only layout")
        return original_import(name, *args, **kwargs)

    def denied(*args, **kwargs):
        pytest.fail("Retrieval model loading attempted network access")

    monkeypatch.setattr(builtins, "__import__", repo_only_import)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    monkeypatch.setenv("KAIRO_REQUIRE_SEMANTIC", "1")
    index = RetrievalIndex()
    index._init_embedding()
    assert index._embed_backend == "model2vec"
    expected = load_local_static_model(MODEL_DIR).encode(["How many people work there?"])[0]
    np.testing.assert_array_equal(index._embed_fn("How many people work there?"), expected)
    gc.collect()
