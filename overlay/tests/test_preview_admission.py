"""Preview cancellation must not release native work's admission permit."""
import asyncio
import concurrent.futures
import threading

import pytest
from fastapi import HTTPException

from overlay import server


@pytest.mark.asyncio
async def test_cancelled_preview_keeps_slot_until_worker_finishes(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    monkeypatch.setattr(server, "_admission", server.AdmissionGate(max_waiters=0))
    slots = threading.BoundedSemaphore(1)
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    def held(_req):
        entered.set()
        assert release.wait(5)
        return {"success": True}
    monkeypatch.setattr(server, "_extraction_slots", slots)
    monkeypatch.setattr(server, "_extraction_pool", pool)
    monkeypatch.setattr(server, "_run_document_preview", held)
    task = asyncio.create_task(server.run_demo(server.DemoRequest(file="sample_memo_01.txt")))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        with pytest.raises(HTTPException) as captured:
            await server.run_demo(server.DemoRequest(file="sample_memo_01.txt"))
        assert captured.value.status_code == 503
        assert not slots.acquire(blocking=False)
    finally:
        release.set()
        await asyncio.to_thread(pool.shutdown, wait=True, cancel_futures=True)
    assert slots.acquire(blocking=False)
    slots.release()


@pytest.mark.asyncio
async def test_submission_failure_returns_preview_permit(monkeypatch):
    monkeypatch.setattr(server, "_admission", server.AdmissionGate(max_waiters=0))
    slots = threading.BoundedSemaphore(1)
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    pool.shutdown()
    monkeypatch.setattr(server, "_extraction_slots", slots)
    monkeypatch.setattr(server, "_extraction_pool", pool)
    with pytest.raises(HTTPException) as captured:
        await server.run_demo(server.DemoRequest(file="sample_memo_01.txt"))
    assert captured.value.status_code == 500
    assert slots.acquire(blocking=False)
    slots.release()
