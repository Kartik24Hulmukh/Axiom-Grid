"""Deterministic scheduler regressions, no timing sleeps or load SLO claims."""
import asyncio
import threading

import pytest

from overlay.admission import AdmissionFull, AdmissionGate


@pytest.mark.asyncio
async def test_completion_burst_coalesces_callback_without_losing_capacity(monkeypatch):
    gate = AdmissionGate()
    slots = threading.BoundedSemaphore(8)
    permits = [await gate.acquire(slots, 'native') for _ in range(8)]
    entered = asyncio.Queue()

    async def waiting():
        entered.put_nowait(True)
        return await gate.acquire(slots, 'waiting')

    tasks = [asyncio.create_task(waiting()) for _ in range(8)]
    for _ in tasks:
        await entered.get()
    loop = asyncio.get_running_loop()
    original = loop.call_soon_threadsafe
    callbacks = []

    def recorded(callback, *args, **kwargs):
        callbacks.append(callback)
        return original(callback, *args, **kwargs)

    monkeypatch.setattr(loop, 'call_soon_threadsafe', recorded)
    def native_completion_burst():
        for permit in permits:
            permit.release()

    # Keep the loop in this deterministic test turn while native completions
    # arrive. This is a wake-count oracle, not a measured latency benchmark.
    worker = threading.Thread(target=native_completion_burst)
    worker.start()
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert len(callbacks) == 1
    granted = await asyncio.wait_for(asyncio.gather(*tasks), 2)
    assert gate.pending() == 0
    for permit in granted:
        permit.release()
    assert all(slots.acquire(False) for _ in range(8))
    assert not slots.acquire(False)
    for _ in range(8):
        slots.release()


@pytest.mark.asyncio
async def test_cancelled_middle_waiter_restores_both_caps_and_fifo():
    gate = AdmissionGate(max_waiters=3, per_tenant=2)
    slots = threading.BoundedSemaphore(1)
    held = await gate.acquire(slots, 'running')
    entered = asyncio.Queue()

    async def waiting(tenant):
        entered.put_nowait(True)
        return await gate.acquire(slots, tenant)

    a1 = asyncio.create_task(waiting('a'))
    a2 = asyncio.create_task(waiting('a'))
    b1 = asyncio.create_task(waiting('b'))
    for _ in range(3):
        await entered.get()
    assert gate.pending() == 3
    with pytest.raises(AdmissionFull):
        await gate.acquire(slots, 'b')
    a2.cancel()
    with pytest.raises(asyncio.CancelledError):
        await a2
    assert gate.pending() == 2
    a3 = asyncio.create_task(waiting('a'))
    await entered.get()
    held.release()
    permit = await asyncio.wait_for(a1, 2)
    assert not b1.done() and not a3.done()
    permit.release()
    permit = await asyncio.wait_for(b1, 2)
    assert not a3.done()
    permit.release()
    (await asyncio.wait_for(a3, 2)).release()
    assert gate.pending() == 0
    assert slots.acquire(False)
    slots.release()


@pytest.mark.asyncio
async def test_queue_timing_uses_waiter_context_and_excludes_running_time(monkeypatch):
    from overlay.admission import AdmissionTiming, admission_timing
    import overlay.admission as admission

    clock = [10.0]
    monkeypatch.setattr(admission.time, 'perf_counter', lambda: clock[0])
    gate = AdmissionGate()
    slots = threading.BoundedSemaphore(1)
    held = await gate.acquire(slots, 'native')
    timing = AdmissionTiming()
    token = admission_timing.set(timing)
    entered = asyncio.Event()

    async def waiting():
        entered.set()
        return await gate.acquire(slots, 'waiting')

    task = asyncio.create_task(waiting())
    await entered.wait()
    admission_timing.reset(token)
    # Release from another context; the pump must use the queued accumulator.
    assert admission_timing.get() is None
    clock[0] = 12.5
    held.release()
    granted = await asyncio.wait_for(task, 2)
    assert timing.queue_wait_ms == 2500.0
    clock[0] = 99.0
    granted.release()
    assert timing.queue_wait_ms == 2500.0


@pytest.mark.asyncio
async def test_cancelled_queue_wait_recorded_once(monkeypatch):
    from overlay.admission import AdmissionTiming, admission_timing
    import overlay.admission as admission

    clock = [1.0]
    monkeypatch.setattr(admission.time, 'perf_counter', lambda: clock[0])
    gate = AdmissionGate()
    slots = threading.BoundedSemaphore(1)
    held = await gate.acquire(slots, 'running')
    timing = AdmissionTiming()
    token = admission_timing.set(timing)
    entered = asyncio.Event()

    async def waiting():
        entered.set()
        return await gate.acquire(slots, 'waiting')

    try:
        task = asyncio.create_task(waiting())
        await entered.wait()
        clock[0] = 1.75
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert timing.queue_wait_ms == 750.0
        assert gate.pending() == 0
        held.release()
        assert timing.queue_wait_ms == 750.0
    finally:
        admission_timing.reset(token)


@pytest.mark.asyncio
async def test_distinct_native_lanes_keep_independent_caps_and_wakeups():
    gate = AdmissionGate(max_waiters=1, per_tenant=1)
    extraction = threading.BoundedSemaphore(1)
    evidence = threading.BoundedSemaphore(1)
    held_extraction = await gate.acquire(extraction, 'tenant')
    entered = asyncio.Queue()

    async def waiting(slots):
        entered.put_nowait(True)
        return await gate.acquire(slots, 'tenant')

    queued_extraction = asyncio.create_task(waiting(extraction))
    await entered.get()
    held_evidence = await gate.acquire(evidence, 'tenant')
    queued_evidence = asyncio.create_task(waiting(evidence))
    await entered.get()
    # Limits are per (event loop, native semaphore), not gate-wide.
    assert gate.pending() == 2
    for slots in (extraction, evidence):
        with pytest.raises(AdmissionFull):
            await gate.acquire(slots, 'tenant')
    held_extraction.release()
    granted_extraction = await asyncio.wait_for(queued_extraction, 2)
    assert not queued_evidence.done()
    assert gate.pending() == 1
    held_evidence.release()
    granted_evidence = await asyncio.wait_for(queued_evidence, 2)
    granted_extraction.release()
    granted_evidence.release()
    assert gate.pending() == 0
    assert extraction.acquire(False) and evidence.acquire(False)
    extraction.release()
    evidence.release()
