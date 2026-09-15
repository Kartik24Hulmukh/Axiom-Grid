"""Admission must precede document I/O, not only pipeline execution."""
import threading

import pytest

from fastapi.testclient import TestClient
from overlay import server


def test_saturated_extraction_does_not_resolve_or_read_document(monkeypatch):
    slots = threading.BoundedSemaphore(1)
    assert slots.acquire(blocking=False)
    monkeypatch.setattr(server, "_extraction_slots", slots)
    def forbidden_resolve(_path):
        raise AssertionError("document I/O happened before admission")
    monkeypatch.setattr(server, "resolve_sandbox_path", forbidden_resolve)
    try:
        with TestClient(server.app) as client:
            response = client.post("/api/extract-document", json={"file": "sample_memo_01.txt"})
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "1"
    finally:
        slots.release()


def test_oversize_document_rejected_and_admission_reusable(monkeypatch, tmp_path):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(server, "_extraction_slots", slots)
    monkeypatch.setattr(server, "MAX_UPLOAD_BYTES", 256)
    path = tmp_path / "oversize.txt"
    path.write_bytes(b"x" * 257)
    with TestClient(server.app) as client:
        response = client.post("/api/extract-document", json={"file": str(path)})
        assert response.status_code == 413
        path.write_text("CLASSIFICATION: UNCLASSIFIED\nSUBJECT: small memo\n")
        assert client.post("/api/extract-document", json={"file": str(path)}).status_code == 200
    assert slots.acquire(blocking=False)
    slots.release()


def test_missing_document_releases_admission(monkeypatch):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(server, "_extraction_slots", slots)
    with TestClient(server.app) as client:
        for _ in range(2):
            assert client.post("/api/extract-document", json={"file": "missing-admission-test.txt"}).status_code == 404
    assert slots.acquire(blocking=False)
    slots.release()


@pytest.mark.asyncio
async def test_cancelled_waiter_keeps_capacity_until_real_worker_finishes(monkeypatch):
    import asyncio

    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(server, "_extraction_slots", slots)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = server.resolve_sandbox_path
    def blocked_resolve(path):
        entered.set()
        assert release.wait(5), "test worker was not released"
        return original(path)
    monkeypatch.setattr(server, "resolve_sandbox_path", blocked_resolve)
    original_submit = server._extraction_pool.submit
    def submit(*args, **kwargs):
        future = original_submit(*args, **kwargs)
        future.add_done_callback(lambda _: finished.set())
        return future
    monkeypatch.setattr(server._extraction_pool, "submit", submit)
    task = asyncio.create_task(server.extract_document(server.ExtractDocumentRequest(file="sample_memo_01.txt")))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not slots.acquire(blocking=False), "cancelled waiter released running capacity"
        with pytest.raises(server.HTTPException) as error:
            await server.extract_document(server.ExtractDocumentRequest(file="sample_memo_01.txt"))
        assert error.value.status_code == 503
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 5)
        await asyncio.to_thread(server._extraction_pool.shutdown, wait=True)
    assert slots.acquire(blocking=False)
    slots.release()
