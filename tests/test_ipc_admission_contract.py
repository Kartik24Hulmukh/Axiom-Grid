"""Negative/unit IPC admission oracles; not native Windows or engine proof."""
import asyncio
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kairo-sidecar"))
from sidecar import ipc


class FakeTransport:
    def __init__(self):
        self.closed = False
        self.written = []

    def close(self):
        self.closed = True

    def write(self, data):
        self.written.append(data)


def frame(value=None):
    return json.dumps({"action": "ping"} if value is None else value).encode() + b"\n"


def connected(handler, budget=None):
    protocol = ipc.NamedPipeProtocol(handler, budget)
    transport = FakeTransport()
    protocol.connection_made(transport)
    return protocol, transport


def empty(budget):
    assert budget.outstanding == 0
    assert budget.retained_bytes == 0


@pytest.mark.asyncio
async def test_count_admission_before_task_creation_and_future_data_drop():
    release = asyncio.Event()
    started = 0

    async def handler(req):
        nonlocal started
        started += 1
        await release.wait()
        return {"ok": True}

    p, t = connected(handler)
    try:
        p.data_received(frame() * 32)
        assert len(p._active_tasks) == 32
        assert p.admission.outstanding == 32
        assert p.admission.retained_bytes == len(frame()) * 32
        await asyncio.sleep(0)
        assert started == 16
        p.data_received(frame() + b"fragment")
        assert t.closed and p.buffer == b""
        assert len(p._active_tasks) == 32  # No 33rd task allocated.
        p.data_received(frame() * 64)
        assert len(p._active_tasks) == 32
        release.set()
        await p.drain()
        assert started == 16  # Queued work was cancelled; active work finished.
        empty(p.admission)
        assert not t.written
    finally:
        release.set()
        await p.drain()


@pytest.mark.asyncio
async def test_two_connections_shared_byte_budget_and_reconnect():
    release = asyncio.Event()

    async def handler(req):
        await release.wait()
        return {"ok": True}

    budget = ipc.AdmissionBudget()
    p, _ = connected(handler, budget)
    q, qt = connected(handler, budget)
    line = json.dumps({"text": "x" * (ipc.MAX_RETAINED_REQUEST_BYTES // 2)}).encode() + b"\n"
    assert len(line) < ipc.MAX_MESSAGE_BYTES
    try:
        p.data_received(line)
        await asyncio.sleep(0)
        assert budget.outstanding == 1
        assert budget.retained_bytes == len(line)
        q.data_received(line)
        assert qt.closed and not q._active_tasks
        assert budget.retained_bytes == len(line)
        release.set()
        await p.drain()
        await q.drain()
        empty(budget)
        r, rt = connected(handler, budget)
        r.data_received(frame())
        await r.drain()
        assert json.loads(rt.written[0])["ok"]
        empty(budget)
    finally:
        release.set()
        await p.drain()
        await q.drain()


@pytest.mark.asyncio
async def test_shared_count_not_just_per_connection():
    release = asyncio.Event()

    async def handler(req):
        await release.wait()
        return {"ok": True}

    budget = ipc.AdmissionBudget()
    p, _ = connected(handler, budget)
    q, qt = connected(handler, budget)
    try:
        p.data_received(frame() * 21)
        q.data_received(frame() * 11)
        assert budget.outstanding == 32
        assert len(p._active_tasks) == 21 and len(q._active_tasks) == 11
        q.data_received(frame())
        assert qt.closed and budget.outstanding == 32
        release.set()
        await p.drain()
        await q.drain()
        empty(budget)
    finally:
        release.set()
        await p.drain()
        await q.drain()


@pytest.mark.asyncio
async def test_cancel_before_coroutine_start_releases_once():
    called = 0

    async def handler(req):
        nonlocal called
        called += 1
        return {"ok": True}

    p, _ = connected(handler)
    p.data_received(frame())
    task = next(iter(p._active_tasks))
    task.cancel()
    task.cancel()
    await p.drain()
    assert task.cancelled() and called == 0
    empty(p.admission)
    await p.drain()
    empty(p.admission)


@pytest.mark.asyncio
async def test_disconnect_preserves_started_handler_and_cancels_waiters():
    release = asyncio.Event()
    all_started = asyncio.Event()
    started = completed = 0

    async def handler(req):
        nonlocal started, completed
        started += 1
        if started == 16:
            all_started.set()
        await release.wait()
        completed += 1
        return {"ok": True}

    p, t = connected(handler)
    try:
        p.data_received(frame() * 21)
        await all_started.wait()
        p.connection_lost(None)
        p.connection_lost(None)
        assert p.buffer == b""
        p.data_received(frame())
        release.set()
        await p.drain()
        assert started == completed == 16
        assert not t.written
        empty(p.admission)
    finally:
        release.set()
        await p.drain()


@pytest.mark.asyncio
async def test_error_invalid_json_blank_and_normal_completion_release():
    async def handler(req):
        if req.get("fail"):
            raise ValueError("controlled unit error")
        return {"ok": True}

    p, t = connected(handler)
    p.data_received(b"{invalid}\n\n" + frame({"fail": True}) + frame())
    await p.drain()
    empty(p.admission)
    replies = [json.loads(x) for x in t.written]
    assert len(replies) == 3
    assert [r["ok"] for r in replies] == [False, False, True]
    p.data_received(frame())
    await p.drain()
    empty(p.admission)
    assert len(t.written) == 4


@pytest.mark.asyncio
async def test_fragment_overflow_clears_closes_and_drops_future_data():
    async def handler(req):
        raise AssertionError("must not run")

    p, t = connected(handler)
    p.data_received(b"x" * ipc.MAX_MESSAGE_BYTES)
    p.data_received(b"x")
    assert t.closed and p.buffer == b""
    p.data_received(frame())
    assert not p._active_tasks
    empty(p.admission)


@pytest.mark.asyncio
async def test_exact_byte_budget_and_cancel_before_start_on_overload():
    async def handler(req):
        raise AssertionError("must not run")

    p, t = connected(handler)
    p.data_received(b"x" * (ipc.MAX_RETAINED_REQUEST_BYTES - 1) + b"\n")
    assert p.admission.retained_bytes == ipc.MAX_RETAINED_REQUEST_BYTES
    assert len(p._active_tasks) == 1
    p.data_received(b"\n")
    assert t.closed and len(p._active_tasks) == 1
    await p.drain()
    empty(p.admission)


@pytest.mark.asyncio
async def test_task_creation_failure_rolls_back(monkeypatch):
    async def handler(req):
        raise AssertionError("must not run")

    def fail_create(coroutine):
        raise RuntimeError("controlled task creation failure")

    p, t = connected(handler)
    with monkeypatch.context() as patch:
        patch.setattr(ipc.asyncio, "create_task", fail_create)
        with pytest.raises(RuntimeError, match="controlled task creation failure"):
            p.data_received(frame())
    assert t.closed and not p._active_tasks and p.buffer == b""
    empty(p.admission)


@pytest.mark.asyncio
async def test_actual_server_factory_captures_shared_budget(monkeypatch):
    async def handler(req):
        return {"ok": True}

    protocols = []
    sentinel = object()

    class FakeLoop:
        async def start_serving_pipe(self, factory, name):
            assert name == "unit-only-pipe"
            protocols.extend([factory(), factory()])
            return sentinel

    with monkeypatch.context() as patch:
        patch.setattr(ipc.sys, "platform", "win32")
        patch.setattr(ipc.asyncio, "get_running_loop", lambda: FakeLoop())
        result = await ipc.start_named_pipe_server("unit-only-pipe", handler)
    assert result is sentinel
    assert protocols[0].admission is protocols[1].admission
    assert ipc.NamedPipeProtocol(handler).admission is not protocols[0].admission
    assert ipc.NamedPipeProtocol(handler).admission is not ipc.NamedPipeProtocol(handler).admission
    empty(protocols[0].admission)
