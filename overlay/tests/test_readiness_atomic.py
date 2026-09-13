"""Cold-start contention must initialize once, without event-loop publication."""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pytest

from overlay import server
from packs.memo.pack import ClassifiedMemoPack


def test_cold_start_single_publication(monkeypatch):
    calls = 0
    lock = Lock()
    original = ClassifiedMemoPack.extract_text
    def extract(self, text):
        nonlocal calls
        with lock:
            calls += 1
        return original(self, text)
    monkeypatch.setattr(ClassifiedMemoPack, "extract_text", extract)
    server._readyz_probe_ok.clear()
    try:
        with ThreadPoolExecutor(max_workers=100) as pool:
            results = list(pool.map(lambda _: server._run_readyz_probe(), range(1000)))
        assert all(r["status"] == "ready" for r in results)
        assert calls == 1
        assert server._readyz_probe_ok.is_set()
    finally:
        server._readyz_probe_ok.clear()


def test_failed_probe_is_not_cached(monkeypatch):
    server._readyz_probe_ok.clear()
    monkeypatch.setattr(ClassifiedMemoPack, "extract_text", lambda *args: {})
    with pytest.raises(RuntimeError, match="zero fields"):
        server._run_readyz_probe()
    assert not server._readyz_probe_ok.is_set()
