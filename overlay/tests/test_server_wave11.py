"""Strict origin parsing and byte-safe request correlation regressions."""
import pytest
from fastapi.testclient import TestClient

from overlay import server


@pytest.mark.parametrize("origin", [
    "http://localhost:80@evil.example",
    "http://127.0.0.1:80@evil.example",
    "http://localhost:bad",
    "http://localhost:65536",
    "http://localhost:80/path",
    "http://localhost:80?query=x",
    "http://localhost:80#fragment",
    "http://testserver:80@evil.example",
])
def test_origin_must_be_exact_authority(origin):
    with TestClient(server.app) as client:
        assert client.get("/healthz", headers={"Origin": origin}).status_code == 403


@pytest.mark.parametrize("origin", ["http://localhost:8765", "http://127.0.0.1:8765", "tauri://localhost"])
def test_valid_local_origins_remain_allowed(origin):
    with TestClient(server.app) as client:
        assert client.get("/healthz", headers={"Origin": origin}).status_code == 200


def test_explicit_configured_origin_is_honored(monkeypatch):
    monkeypatch.setattr(server, "_CORS_ORIGINS", ["https://app.example.com"])
    with TestClient(server.app) as client:
        assert client.get("/healthz", headers={"Origin": "https://app.example.com"}).status_code == 200


def test_request_id_strips_non_ascii():
    with TestClient(server.app) as client:
        response = client.get("/healthz", headers=[(b"x-request-id", b"id-\xff")])
        assert response.status_code == 200
        assert response.headers["x-request-id"] == "id-"


@pytest.mark.asyncio
async def test_cancelled_request_retains_slot_until_worker_finishes(monkeypatch):
    import asyncio
    import threading

    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(server, "_extraction_slots", slots)

    def blocked_run(self, doc):
        entered.set()
        try:
            release.wait(5)
            raise RuntimeError("synthetic worker failure")
        finally:
            finished.set()

    monkeypatch.setattr(server.OrchestratorImpl, "run", blocked_run)
    task = asyncio.create_task(server.extract_document(
        server.ExtractDocumentRequest(file="fixtures/wedge/sample_memo_01.txt")))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        acquired = slots.acquire(blocking=False)
        if acquired:
            slots.release()
        assert not acquired, "request cancellation released capacity for still-running work"
    finally:
        release.set()
        await asyncio.to_thread(finished.wait, 3)
        await asyncio.sleep(0.05)
    assert slots.acquire(blocking=False)
    slots.release()
