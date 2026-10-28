"""Synthetic executor regressions: no source I/O, parsing, model or network."""
import asyncio
import concurrent.futures
import threading

import pytest

from overlay import server


class CountingSlots:
    def __init__(self):
        self.semaphore = threading.BoundedSemaphore(1)
        self.releases = 0

    def acquire(self, blocking=False):
        return self.semaphore.acquire(blocking=blocking)

    def release(self):
        self.releases += 1
        self.semaphore.release()


@pytest.mark.asyncio
async def test_cancel_queued_work_does_no_io_and_releases_once(monkeypatch):
    slots = CountingSlots()
    queued = asyncio.Event()
    future = concurrent.futures.Future()

    class QueuedExecutor:
        def submit(self, *args, **kwargs):
            # Deliberately do not run the submitted source-access function.
            queued.set()
            return future

    def no_source_io(*args):
        raise AssertionError("cancelled queued work must not access a source")

    monkeypatch.setattr(server, "_extraction_slots", slots)
    monkeypatch.setattr(server, "_extraction_pool", QueuedExecutor())
    monkeypatch.setattr(server, "resolve_sandbox_path", no_source_io)
    task = asyncio.create_task(server.extract_document(
        server.ExtractDocumentRequest(file="synthetic-not-opened.txt")))
    await asyncio.wait_for(queued.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    for _ in range(3):
        await asyncio.sleep(0)
    assert future.cancelled()
    assert slots.releases == 1
    assert slots.acquire(blocking=False)
    assert not slots.acquire(blocking=False)
    slots.release()


@pytest.mark.asyncio
async def test_cancel_running_work_retains_slot_until_finish_and_releases_once(monkeypatch):
    slots = CountingSlots()
    started = asyncio.Event()
    future = concurrent.futures.Future()

    class RunningExecutor:
        def submit(self, *args, **kwargs):
            # Model an already-running worker without source I/O or a thread:
            # cancellation cannot complete this future; only finish below can.
            assert future.set_running_or_notify_cancel()
            started.set()
            return future

    def no_source_io(*args):
        raise AssertionError("controlled executor must not access a source")

    monkeypatch.setattr(server, "_extraction_slots", slots)
    monkeypatch.setattr(server, "_extraction_pool", RunningExecutor())
    monkeypatch.setattr(server, "resolve_sandbox_path", no_source_io)
    task = asyncio.create_task(server.extract_document(
        server.ExtractDocumentRequest(file="synthetic-running-not-opened.txt")))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        assert future.running()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        for _ in range(3):
            await asyncio.sleep(0)
        assert future.running() and not future.cancelled()
        assert slots.releases == 0
        assert not slots.acquire(blocking=False), "cancelled waiter must not free running capacity"
    finally:
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        if not future.done():
            future.set_result((None, None, None))

    # Concurrent-future done callbacks run synchronously in this controlled
    # executor, so the count has no cross-thread observation race.
    assert future.done() and not future.cancelled()
    assert slots.releases == 1
    assert slots.acquire(blocking=False)
    assert not slots.acquire(blocking=False)
    slots.semaphore.release()
    for _ in range(3):
        await asyncio.sleep(0)
    assert slots.releases == 1


@pytest.mark.asyncio
async def test_executor_submit_failure_releases_once_before_source_io(monkeypatch):
    slots = CountingSlots()

    class FailedExecutor:
        def submit(self, *args, **kwargs):
            raise RuntimeError("synthetic executor unavailable")

    def no_source_io(*args):
        raise AssertionError("failed submission must not access a source")

    monkeypatch.setattr(server, "_extraction_slots", slots)
    monkeypatch.setattr(server, "_extraction_pool", FailedExecutor())
    monkeypatch.setattr(server, "resolve_sandbox_path", no_source_io)
    with pytest.raises(RuntimeError, match="synthetic executor unavailable"):
        await server.extract_document(server.ExtractDocumentRequest(file="not-opened.txt"))
    assert slots.releases == 1
    assert slots.acquire(blocking=False)
    assert not slots.acquire(blocking=False)
    slots.release()
