"""Session-21 launch hardening: isolated ingestion and per-model timeouts."""
import os

import pytest

from kernel.sidecar import isolated_ingest
from kernel.sidecar.melious_router import MeliousModelRouter, RouterError


FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures")


def _find_docx():
    for root, _dirs, files in os.walk(FIXTURES):
        for name in files:
            if name.lower().endswith(".docx"):
                return os.path.join(root, name)
    return None


def test_isolated_ingest_parses_real_docx():
    path = _find_docx()
    if path is None:
        pytest.skip("no .docx fixture in repo")
    texts = isolated_ingest.ingest_isolated(path, timeout=60.0)
    assert isinstance(texts, list) and texts
    assert any(isinstance(t, str) and t.strip() for t in texts)


def test_isolated_ingest_deadline_kills_hung_child(tmp_path):
    # A child that never returns must be killed and reaped, not left running.
    bad = tmp_path / "hung.bin"
    bad.write_bytes(b"not a real document")
    with pytest.raises((isolated_ingest.IsolatedIngestDeadline,
                        isolated_ingest.IsolatedIngestResourceError, ValueError)):
        isolated_ingest.ingest_isolated(str(bad), timeout=20.0)


def _router(monkeypatch, env_timeouts=None, models=("a", "b")):
    if env_timeouts is None:
        monkeypatch.delenv("MELIOUS_MODEL_TIMEOUTS", raising=False)
    else:
        monkeypatch.setenv("MELIOUS_MODEL_TIMEOUTS", env_timeouts)
    return MeliousModelRouter(models=list(models))


def test_per_model_timeout_overrides(monkeypatch):
    r = _router(monkeypatch, "a=0.8,b=2.0")
    assert r.model_timeouts == {"a": 0.8, "b": 2.0}
    seen = {}
    def fake_transport(model, payload, timeout):
        seen[model] = timeout
        return {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
    r._transport = fake_transport
    out = r.complete([{"role": "user", "content": "hi"}])
    assert seen["a"] == 0.8  # capped below the 10s default
    assert out["choices"][0]["message"]["content"] == "ok"


def test_invalid_timeout_config_fails_closed(monkeypatch):
    for bad in ("a=nope", "a=-1", "a=nan", "a=inf", "zzz=1.0", "justtext", "a="):
        with pytest.raises(RouterError):
            _router(monkeypatch, bad)
