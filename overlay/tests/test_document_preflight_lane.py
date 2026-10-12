"""Document metadata avoids CPU head-of-line blocking without bypassing admission."""
import asyncio
import concurrent.futures
import threading
import time

import pytest

from overlay import server


@pytest.fixture
def staged_pools(monkeypatch):
    metadata = concurrent.futures.ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="axiom-metadata-test"
    )
    extraction = concurrent.futures.ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="axiom-extract-test"
    )
    slots = threading.BoundedSemaphore(2)
    monkeypatch.setattr(server, "_document_metadata_pool", metadata)
    monkeypatch.setattr(server, "_extraction_pool", extraction)
    monkeypatch.setattr(server, "_extraction_slots", slots)
    monkeypatch.setattr(server, "_admission", server.AdmissionGate(max_waiters=0))
    yield metadata, extraction, slots
    metadata.shutdown(wait=True, cancel_futures=True)
    extraction.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_unknown_source_finishes_while_cpu_worker_is_held(staged_pools):
    entered = threading.Event()
    release = threading.Event()

    def held_cpu():
        entered.set()
        assert release.wait(5)
        return "done"

    first = asyncio.create_task(
        server._document_call(held_cpu, "sample_memo_01.txt")
    )
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        started = time.perf_counter()
        with pytest.raises(server.HTTPException) as error:
            await server._document_call(
                lambda: pytest.fail("missing source reached CPU"),
                "missing-preflight-source.txt",
            )
        assert error.value.status_code == 404
        assert time.perf_counter() - started < 1
        assert not first.done()
    finally:
        release.set()
    assert await first == "done"


@pytest.mark.asyncio
async def test_successful_metadata_is_revalidated_on_cpu_worker(
    monkeypatch, staged_pools, tmp_path
):
    target = tmp_path / "document.txt"
    target.write_text("content")
    calls = []

    def resolve(_reference):
        calls.append(threading.current_thread().name)
        if len(calls) == 1:
            return target
        raise server.HTTPException(404, "Document not found")

    monkeypatch.setattr(server, "resolve_sandbox_path", resolve)

    with pytest.raises(server.HTTPException) as error:
        await server._document_call(
            lambda: server.resolve_sandbox_path("opaque-reference"),
            "opaque-reference",
        )
    assert error.value.status_code == 404
    assert len(calls) == 2
    assert calls[0].startswith("axiom-metadata-test")
    assert calls[1].startswith("axiom-extract-test")


@pytest.mark.asyncio
async def test_document_call_uses_one_extraction_permit(monkeypatch, staged_pools):
    original = server._admission
    acquisitions = []

    class RecordingGate:
        async def acquire(self, slots, tenant):
            acquisitions.append((slots, tenant))
            return await original.acquire(slots, tenant)

    monkeypatch.setattr(server, "_admission", RecordingGate())
    thread_name = await server._document_call(
        lambda: threading.current_thread().name,
        "sample_memo_01.txt",
    )

    assert len(acquisitions) == 1
    assert acquisitions[0][0] is server._extraction_slots
    assert thread_name.startswith("axiom-extract-test")