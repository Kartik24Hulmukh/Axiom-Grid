"""Actual HTTP lookup/review isolation and completion-owned evidence capacity."""
import asyncio
import concurrent.futures
import threading

import pytest
from fastapi.testclient import TestClient

from overlay import server
from overlay.tenant_context import current_tenant, tenant_context


def test_http_lookup_and_unknown_review_finish_while_parser_is_held(monkeypatch):
    """A controlled slow parser proves isolation, not a production latency SLO."""
    entered, release = threading.Event(), threading.Event()
    original = server.resolve_sandbox_path

    def held(path):
        entered.set()
        assert release.wait(10), "test failed to release parser"
        return original(path)

    monkeypatch.setattr(server, "resolve_sandbox_path", held)
    monkeypatch.setattr(server, "_extraction_slots", threading.BoundedSemaphore(1))
    with TestClient(server.app) as client, concurrent.futures.ThreadPoolExecutor(3) as callers:
        parse = callers.submit(client.post, "/demo", json={"file": "sample_memo_01.txt"})
        try:
            assert entered.wait(3)
            source = callers.submit(client.get, "/api/source/never-existed")
            review = callers.submit(client.post, "/correct", json={
                "ext_id": "never-existed", "field_name": "author", "original": "source",
                "corrected": "review", "reason": "isolation test", "expected_revision": 0,
            })
            assert source.result(timeout=1).status_code == 404
            assert review.result(timeout=1).status_code == 404
            assert not parse.done(), "slow parser was released prematurely"
        finally:
            release.set()
        assert parse.result(timeout=5).status_code == 200


@pytest.mark.asyncio
async def test_evidence_lane_cancellation_keeps_native_capacity_and_tenant(monkeypatch):
    pool = concurrent.futures.ThreadPoolExecutor(1)
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(server, "_evidence_pool", pool)
    monkeypatch.setattr(server, "_evidence_slots", slots)
    monkeypatch.setattr(server, "_admission", server.AdmissionGate(max_waiters=0))
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    observed = []

    def held():
        observed.append(current_tenant())
        entered.set()
        try:
            assert release.wait(5)
        finally:
            finished.set()

    token = tenant_context.set("isolated-fixture-tenant")
    task = asyncio.create_task(server._evidence_call(held))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not slots.acquire(blocking=False)
        with pytest.raises(server.HTTPException) as error:
            await server._evidence_call(lambda: None)
        assert error.value.status_code == 503
        assert observed == ["isolated-fixture-tenant"]
    finally:
        tenant_context.reset(token)
        release.set()
        assert await asyncio.to_thread(finished.wait, 3)
        await asyncio.to_thread(pool.shutdown, wait=True)
    assert slots.acquire(blocking=False)
    slots.release()


def test_repeated_lifespan_reaps_both_lanes(monkeypatch):
    monkeypatch.setattr(server, "_evidence_pool", concurrent.futures.ThreadPoolExecutor(1))
    monkeypatch.setattr(
        server, "_document_metadata_pool", concurrent.futures.ThreadPoolExecutor(1)
    )
    for _ in range(2):
        with TestClient(server.app) as client:
            assert client.get("/api/source/missing-lifecycle").status_code == 404
            assert server._evidence_pool.submit(lambda: 7).result(timeout=2) == 7
        assert all(not thread.is_alive() for thread in server._evidence_pool._threads)
        assert all(
            not thread.is_alive()
            for thread in server._document_metadata_pool._threads
        )
        assert all(not thread.is_alive() for thread in server._extraction_pool._threads)
