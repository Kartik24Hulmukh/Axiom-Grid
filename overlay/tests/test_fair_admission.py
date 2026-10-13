"""Event-driven cancellation/fairness; no arbitrary timing sleeps as assertions."""
import asyncio
import threading
import pytest
from overlay.admission import AdmissionGate, AdmissionFull, until_disconnect, ClientDisconnected


@pytest.mark.asyncio
async def test_caps_cancelled_waiters_and_round_robin():
    gate=AdmissionGate(max_waiters=3,per_tenant=2);slots=threading.BoundedSemaphore(1)
    first=await gate.acquire(slots,'busy')
    started=asyncio.Queue()
    async def queued(tenant):
        started.put_nowait(tenant)
        return await gate.acquire(slots,tenant)
    a=asyncio.create_task(queued('a')); await started.get()
    b=asyncio.create_task(queued('b')); await started.get()
    a2=asyncio.create_task(queued('a')); await started.get()
    assert gate.pending()==3
    with pytest.raises(AdmissionFull):await gate.acquire(slots,'c')
    first.release();p=await asyncio.wait_for(a,1);assert not b.done();p.release()
    p=await asyncio.wait_for(b,1);assert not a2.done()
    a2.cancel()
    with pytest.raises(asyncio.CancelledError):await a2
    p.release();assert gate.pending()==0
    final=await gate.acquire(slots,'a');final.release();final.release()
    assert slots.acquire(False);slots.release()


@pytest.mark.asyncio
async def test_grant_cancellation_race_does_not_leak_permit():
    gate=AdmissionGate();slots=threading.BoundedSemaphore(1)
    for _ in range(100):
        first=await gate.acquire(slots,'a')
        entered=asyncio.Event()
        async def waiter():
            entered.set();return await gate.acquire(slots,'a')
        task=asyncio.create_task(waiter());await entered.wait()
        first.release();task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert slots.acquire(False);slots.release()
    assert gate.pending()==0


@pytest.mark.asyncio
async def test_receive_disconnect_cancels_waiting_without_polling():
    gate=AdmissionGate();slots=threading.BoundedSemaphore(1)
    first=await gate.acquire(slots,'a');messages=asyncio.Queue();entered=asyncio.Event()
    class Request:
        async def receive(self):
            entered.set();return await messages.get()
    task=asyncio.create_task(until_disconnect(gate.acquire(slots,'b'),Request(),1))
    await entered.wait();assert gate.pending()==1
    messages.put_nowait({'type':'http.disconnect'})
    with pytest.raises(ClientDisconnected):await task
    assert gate.pending()==0
    assert not slots.acquire(False);first.release()
    assert slots.acquire(False);slots.release()
