"""Bounded event-driven round-robin waiting; native permits live until done."""
from __future__ import annotations

import asyncio
import contextvars
import threading
import time
import weakref
from collections import OrderedDict
from dataclasses import dataclass


@dataclass
class AdmissionTiming:
    """Request-local gate waiting only, excluding native executor/work time."""

    queue_wait_ms: float = 0.0


# A mutable request-owned accumulator is shared with copied task contexts.
# The pump runs in a completion callback's context, so each waiter retains its
# accumulator explicitly rather than reading the pump's ambient ContextVar.
admission_timing = contextvars.ContextVar("admission_timing", default=None)


def _record_wait(entry):
    timing, queued_at = entry
    if timing is not None:
        timing.queue_wait_ms += (time.perf_counter() - queued_at) * 1000


class AdmissionFull(Exception):
    pass


class Permit:
    def __init__(self, gate, slots):
        self.gate, self.slots = gate, slots
        self._released = False
        self._lock = threading.Lock()

    def release(self):
        with self._lock:
            if self._released:
                return
            self._released = True
            self.slots.release()
        self.gate.wake(self.slots)


class _Waiters:
    def __init__(self, loop, slots):
        self.loop = weakref.ref(loop)
        self.slots = slots
        self.tenants = OrderedDict()
        self.count = 0
        self.wake_scheduled = False


class AdmissionGate:
    def __init__(self, max_waiters=192, per_tenant=96):
        self.max_waiters, self.per_tenant = max_waiters, per_tenant
        self._lock = threading.RLock()
        # Queue values never retain an idle loop. Cancelled futures are removed.
        self._loops = weakref.WeakKeyDictionary()

    def _queue(self, loop, slots):
        queues = self._loops.setdefault(loop, {})
        return queues.setdefault(slots, _Waiters(loop, slots))

    def _pump(self, queue):
        with self._lock:
            while queue.tenants:
                tenant = next(iter(queue.tenants))
                waiting = queue.tenants[tenant]
                while waiting and next(iter(waiting)).done():
                    _, entry = waiting.popitem(last=False)
                    queue.count -= 1
                    _record_wait(entry)
                if not waiting:
                    del queue.tenants[tenant]
                    continue
                if not queue.slots.acquire(blocking=False):
                    break
                future, entry = waiting.popitem(last=False)
                queue.count -= 1
                _record_wait(entry)
                if waiting:
                    queue.tenants.move_to_end(tenant)
                else:
                    del queue.tenants[tenant]
                future.set_result(Permit(self, queue.slots))

    def _drain(self, queue):
        # A burst of native completions needs one loop callback, not one each.
        # Reset and pump under the same lock so no concurrent wake is lost.
        with self._lock:
            queue.wake_scheduled = False
            self._pump(queue)

    def wake(self, slots):
        with self._lock:
            queues = [qs[slots] for qs in list(self._loops.values()) if slots in qs]
            for queue in queues:
                loop = queue.loop()
                if loop and not loop.is_closed() and not queue.wake_scheduled:
                    try:
                        queue.wake_scheduled = True
                        loop.call_soon_threadsafe(self._drain, queue)
                    except RuntimeError:
                        # Loop shutdown racing a completed native worker.
                        queue.wake_scheduled = False

    async def acquire(self, slots, tenant):
        loop = asyncio.get_running_loop()
        with self._lock:
            queue = self._queue(loop, slots)
            # Do not let a new caller bypass already waiting tenants.
            if not queue.count and slots.acquire(blocking=False):
                return Permit(self, slots)
            if queue.count >= self.max_waiters or len(queue.tenants.get(tenant, ())) >= self.per_tenant:
                raise AdmissionFull()
            future = loop.create_future()
            # Ordered sets preserve FIFO and allow O(1) cancellation unlink.
            timing = admission_timing.get()
            queue.tenants.setdefault(tenant, OrderedDict())[future] = (
                timing, time.perf_counter() if timing is not None else None
            )
            queue.count += 1
            self._pump(queue)
        try:
            return await future
        except BaseException:
            with self._lock:
                waiting = queue.tenants.get(tenant)
                if waiting and future in waiting:
                    entry = waiting.pop(future)
                    queue.count -= 1
                    _record_wait(entry)
                    if not waiting:
                        del queue.tenants[tenant]
                # A grant may be delivered in the same turn as cancellation.
                if future.done() and not future.cancelled():
                    future.result().release()
            raise

    def pending(self):
        with self._lock:
            return sum(q.count for qs in self._loops.values() for q in qs.values())


async def until_disconnect(operation, request, timeout):
    """Await work or an actual receive-side disconnect, with no polling sleeps.

    Called only AFTER FastAPI consumed the request body. A direct library call
    passes request=None. Cancellation removes queued futures; a running native
    operation still owns its permit through its own done callback.
    """
    if request is None:
        return await asyncio.wait_for(operation, timeout)
    async def disconnected():
        while True:
            if (await request.receive())["type"] == "http.disconnect":
                return
    task = asyncio.ensure_future(operation)
    watcher = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait((task, watcher), timeout=timeout,
                                     return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            # A rejected queue entry and an already-observed dead peer may
            # finish in the same loop turn. There is no retry recipient in
            # that case. Do not mask storage failures or actual completed work;
            # a connected overload still propagates AdmissionFull unchanged.
            if (watcher in done and not task.cancelled()
                    and isinstance(task.exception(), AdmissionFull)):
                raise ClientDisconnected()
            return task.result()
        if watcher in done:
            raise ClientDisconnected()
        raise TimeoutError()
    finally:
        for pending in (task, watcher):
            if not pending.done():
                pending.cancel()
        await asyncio.gather(task, watcher, return_exceptions=True)


class ClientDisconnected(Exception):
    pass