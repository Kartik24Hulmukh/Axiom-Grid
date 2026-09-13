"""Repeated ASGI lifespan and worker teardown regression."""
import concurrent.futures

from fastapi.testclient import TestClient

import overlay.server as srv


def test_repeated_lifespan_reopens_store_and_reaps_workers(monkeypatch):
    from kernel.sidecar.memory_store import MemoryStoreImpl

    monkeypatch.setattr(srv, "memory_store", MemoryStoreImpl())
    monkeypatch.setattr(srv, "_extraction_pool", concurrent.futures.ThreadPoolExecutor(1))
    for _ in range(2):
        with TestClient(srv.app) as client:
            assert not srv.memory_store.closed
            assert client.get("/livez").status_code == 200
            assert srv._extraction_pool.submit(lambda: 7).result(timeout=2) == 7
        assert srv.memory_store.closed
        assert all(not thread.is_alive() for thread in srv._extraction_pool._threads)
