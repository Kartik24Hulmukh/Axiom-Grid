"""Isolated engineering-preview contracts for origin/governor ASGI guards."""
import asyncio
import copy
import logging
from collections import deque

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from overlay import server
from overlay.tests.test_response_middleware_contract import (
    SECURITY,
    invoke,
    scope,
)


@pytest.fixture(autouse=True)
def running_overlay():
    """Synthetic apps do not start the production lifespan."""
    yield


def fresh_metrics():
    return {"started_at": 123, "requests_total": 0, "errors_total": 0,
            "status_counts": {}, "latency_ms_max": 0., "latency_ms_total": 0.,
            "latency_samples": deque(maxlen=10000)}


@pytest.fixture(autouse=True)
def isolate_metrics(monkeypatch):
    monkeypatch.setattr(server, "OPS_METRICS", fresh_metrics())


def registered(role):
    name = {"origin": "OriginGateMiddleware", "governor": "RequestGovernorMiddleware"}[role]
    matches = [m for m in server.app.user_middleware if m.cls.__name__ == name]
    assert len(matches) == 1, f"Expected one pure ASGI {name} registration"
    assert not issubclass(matches[0].cls, BaseHTTPMiddleware)
    return matches[0]


def wrap(app, role):
    item = registered(role)
    return item.cls(app, **item.kwargs)


def completion_records(caplog):
    return [r for r in caplog.records if r.getMessage() == "request completed"]


def comparable_metrics(metrics):
    return {key: value for key, value in metrics.items() if not key.startswith("latency_")}


@pytest.mark.parametrize("origin", [None, b"http://localhost", b"http://127.0.0.1:8888",
                                    b"http://testserver", b"https://testserver:443",
                                    b"tauri://localhost", b"", b"null", b"https://evil.example",
                                    b"http://localhost/path", b"http://localhost?", b"http://localhost#",
                                    b"http://evil@localhost", b"http://localhost:",
                                    b" http://localhost", b"http://localhost\r\n", b"\xff"])
def test_origin_differential_no_body_io(origin):
    async def run():
        headers = [] if origin is None else [(b"origin", origin)]
        calls = []
        async def call_next(request):
            calls.append("legacy")
            return Response(b"endpoint", status_code=202, headers={"x-kept": "yes"})
        expected = await server.enforce_origin_gate(Request(scope(headers=headers)), call_next)
        async def endpoint(s, receive, send):
            calls.append("asgi")
            await send({"type": "http.response.start", "status": 202,
                        "headers": [(b"content-length", b"8"), (b"x-kept", b"yes")]})
            await send({"type": "http.response.body", "body": b"endpoint"})
        messages = await invoke(wrap(endpoint, "origin"), scope(headers=headers))
        assert messages[0]["status"] == expected.status_code
        assert b"".join(m.get("body", b"") for m in messages) == expected.body
        assert dict(messages[0]["headers"]) == dict(expected.raw_headers)
        assert calls == (["legacy", "asgi"] if expected.status_code == 202 else [])
    asyncio.run(run())


def test_origin_policy_and_callback_resolve_dynamically(monkeypatch):
    async def run():
        async def endpoint(s, receive, send):
            await send({"type": "http.response.start", "status": 204, "headers": []})
        app = wrap(endpoint, "origin")
        origin = "https://dynamic.example"
        for allowed in (False, True, False):
            monkeypatch.setattr(server, "ALLOWED_ORIGINS", {origin} if allowed else set())
            messages = await invoke(app, scope(headers=[(b"origin", origin.encode())]))
            assert messages[0]["status"] == (204 if allowed else 403)
        monkeypatch.setattr(server, "_CORS_ORIGINS", [origin])
        assert (await invoke(app, scope(headers=[(b"origin", origin.encode())])))[0]["status"] == 204
        monkeypatch.setattr(server, "_origin_allowed", lambda value: False)
        assert (await invoke(app, scope(headers=[(b"origin", origin.encode())])))[0]["status"] == 403
    asyncio.run(run())


@pytest.mark.parametrize("length", [None, b"0", b"10", b"00010", b"11", b"",
                                    b"-1", b"+1", b" 1", b"1 ", b"1.0", b"1e1",
                                    b"1,1", b"\xb2", b"9" * 5000])
def test_governor_length_differential_and_no_body_reads(monkeypatch, caplog, length):
    monkeypatch.setattr(server, "MAX_UPLOAD_BYTES", 10)
    async def run():
        headers = [] if length is None else [(b"content-length", length)]
        results = []
        for legacy in (True, False):
            caplog.clear()
            monkeypatch.setattr(server, "OPS_METRICS", fresh_metrics())
            calls = []
            async def call_next(request, calls=calls):
                calls.append("endpoint")
                return Response(b"ok", status_code=201)
            async def endpoint(s, receive, send, calls=calls):
                calls.append("endpoint")
                await send({"type": "http.response.start", "status": 201,
                            "headers": [(b"content-length", b"2")]})
                await send({"type": "http.response.body", "body": b"ok"})
            if legacy:
                response = await server.request_governor_middleware(Request(scope(headers=headers)), call_next)
                status, body, raw_headers = response.status_code, response.body, response.raw_headers
            else:
                messages = await invoke(wrap(endpoint, "governor"), scope(headers=headers))
                status = messages[0]["status"]
                body = b"".join(m.get("body", b"") for m in messages)
                raw_headers = messages[0]["headers"]
            records = completion_records(caplog)
            assert len(records) == (1 if calls else 0)
            if records:
                assert records[0].levelno == logging.INFO
            results.append((status, body, dict(raw_headers), calls, comparable_metrics(server.OPS_METRICS)))
        assert results[0] == results[1]
    with caplog.at_level(logging.INFO, logger="overlay.server"):
        asyncio.run(run())


def test_governor_upload_ceiling_remains_dynamic(monkeypatch):
    async def run():
        async def endpoint(s, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
        app = wrap(endpoint, "governor")
        for ceiling, expected in ((9, 413), (10, 200), (11, 200), (0, 413)):
            monkeypatch.setattr(server, "MAX_UPLOAD_BYTES", ceiling)
            messages = await invoke(app, scope(headers=[(b"content-length", b"10")]))
            assert messages[0]["status"] == expected
    asyncio.run(run())


@pytest.mark.parametrize("status", [200, 404, 422, 500, 503])
def test_completion_once_at_headers_not_body_duration(monkeypatch, caplog, status):
    clock = [20.]
    monkeypatch.setattr(server.time, "perf_counter", lambda: clock[0])
    async def run():
        metrics = server.OPS_METRICS
        samples, counts = metrics["latency_samples"], metrics["status_counts"]
        output = []
        s = scope("/api/contract", state={"tenant": "kept"})
        async def send(message):
            output.append(copy.deepcopy(message))
        async def endpoint(actual, receive, emit):
            assert actual is s
            actual["state"]["request_id"] = "shared-id"
            clock[0] += .025
            await emit({"type": "http.response.start", "status": status, "headers": [], "trailers": True})
            assert len(completion_records(caplog)) == 1
            assert metrics["requests_total"] == 1
            clock[0] += 3  # Body latency is deliberately excluded, as in legacy.
            for chunk in (b"first", b"", b"last"):
                await emit({"type": "http.response.body", "body": chunk, "more_body": True})
                assert output[-1]["body"] == chunk
                assert len(completion_records(caplog)) == 1
            await emit({"type": "http.response.body", "body": b"", "more_body": False})
            await emit({"type": "http.response.trailers", "headers": [(b"checksum", b"ok")]})
        await invoke(wrap(endpoint, "governor"), s, send=send)
        record, = completion_records(caplog)
        assert record.levelno == logging.INFO
        assert (record.request_id, record.path, record.status, record.client, record.latency_ms) == (
            "shared-id", "/api/contract", status, "127.0.0.1", 25.)
        assert metrics["status_counts"] is counts and metrics["latency_samples"] is samples
        assert counts == {str(status): 1}
        assert metrics["errors_total"] == int(status >= 500)
        assert metrics["latency_ms_total"] == pytest.approx(25.)
        assert list(samples) == pytest.approx([25.])
        assert metrics["latency_ms_max"] == 25.
        assert output[0]["trailers"] is True
        assert output[-1] == {"type": "http.response.trailers", "headers": [(b"checksum", b"ok")]}
    with caplog.at_level(logging.INFO, logger="overlay.server"):
        asyncio.run(run())


def test_completion_uses_current_metric_logger_and_request_log_context(monkeypatch, caplog):
    from contextvars import ContextVar
    from queue import Queue

    context = ContextVar("guard_contract_context", default="outside")
    snapshots = []
    queue_handler = server._NonBlockingQueueHandler(Queue())
    class SnapshotHandler(logging.Handler):
        def emit(self, record):
            if record.getMessage() == "request completed":
                snapshots.append(queue_handler.prepare(record))
    logger = logging.getLogger("guard-contract-current")
    handler = SnapshotHandler()
    old_metrics = server.OPS_METRICS
    replacement = fresh_metrics()
    monkeypatch.setattr(server, "log_context", lambda: {"trace_id": context.get()})
    async def run():
        async def endpoint(s, receive, send):
            # Swap after wrapper construction, not just between requests.
            monkeypatch.setattr(server, "OPS_METRICS", replacement)
            monkeypatch.setattr(server, "logger", logger)
            context.set("request-local-trace")
            s.setdefault("state", {})["request_id"] = "context-id"
            await send({"type": "http.response.start", "status": 200, "headers": []})
        app = wrap(endpoint, "governor")
        await invoke(app, scope())
    logger.addHandler(handler)
    try:
        with caplog.at_level(logging.INFO, logger=logger.name):
            asyncio.run(run())
    finally:
        logger.removeHandler(handler)
    assert old_metrics["requests_total"] == 0
    assert replacement["requests_total"] == 1
    record, = completion_records(caplog)
    assert record.name == logger.name and record.request_id == "context-id"
    prepared, = snapshots
    assert dict(prepared._queued_log_context) == {"trace_id": "request-local-trace"}


@pytest.mark.parametrize("role", ["origin", "governor"])
@pytest.mark.parametrize("kind", ["websocket", "lifespan"])
def test_non_http_identity_passthrough(role, kind, caplog):
    async def run():
        s = {"type": kind}
        before = copy.deepcopy(s)
        async def receive():
            raise AssertionError("unused")
        async def send(message):
            raise AssertionError("unused")
        async def endpoint(actual, recv, emit):
            assert actual is s and recv is receive and emit is send
        await wrap(endpoint, role)(s, receive, send)
        assert s == before
        assert not completion_records(caplog)
        assert server.OPS_METRICS["requests_total"] == 0
    asyncio.run(run())


@pytest.mark.parametrize("role", ["origin", "governor"])
@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
@pytest.mark.parametrize("started", [False, True])
def test_errors_cancellation_count_only_started_responses(role, failure, started, caplog):
    async def run():
        error = failure("synthetic")
        output = []
        async def send(message):
            output.append(message)
        async def endpoint(s, receive, emit):
            if started:
                await emit({"type": "http.response.start", "status": 200, "headers": []})
            raise error
        with pytest.raises(failure) as exc:
            await invoke(wrap(endpoint, role), scope(), send=send)
        assert exc.value is error
        assert len(output) == int(started)
        expected = int(started and role == "governor")
        assert len(completion_records(caplog)) == expected
        assert server.OPS_METRICS["requests_total"] == expected
    with caplog.at_level(logging.INFO, logger="overlay.server"):
        asyncio.run(run())


@pytest.mark.parametrize("role", ["origin", "governor"])
def test_disconnect_or_return_without_start_is_not_completion(role, caplog):
    async def run():
        disconnect = {"type": "http.disconnect"}
        async def receive():
            return disconnect
        async def endpoint(s, recv, send):
            assert recv is receive and await recv() is disconnect
        assert await invoke(wrap(endpoint, role), scope(), receive=receive) == []
        assert not completion_records(caplog)
        assert server.OPS_METRICS["requests_total"] == 0
    asyncio.run(run())


def isolated_stack(legacy):
    app = FastAPI()
    replacement = {
        "OriginGateMiddleware": server.enforce_origin_gate,
        "RequestGovernorMiddleware": server.request_governor_middleware,
        "RequestIdMiddleware": server.request_id_middleware,
        "SecurityHeadersMiddleware": server.security_headers_middleware,
    }
    for entry in server.app.user_middleware:
        dispatch = replacement.get(entry.cls.__name__)
        app.user_middleware.append(Middleware(BaseHTTPMiddleware, dispatch=dispatch)
                                   if legacy and dispatch else entry)
    @app.get("/api/guard-contract")
    async def endpoint(request: Request, code: int = 200):
        if code != 200:
            raise HTTPException(code, "synthetic handled failure")
        return {"request_id": request.state.request_id}
    return app


@pytest.mark.parametrize("case,status,completed,headers", [
    ("normal", 200, 1, True), ("handled", 500, 1, True),
    ("origin", 403, 1, True), ("auth", 401, 0, False),
    ("rate", 429, 0, False), ("bodylimit", 413, 0, False)])
def test_full_registered_stack_differential(monkeypatch, caplog, case, status, completed, headers):
    key = "synthetic-guard-contract-key"
    digest = server.hashlib.sha256(key.encode()).hexdigest()
    monkeypatch.setattr(server, "_API_KEY_DIGESTS", {digest: "tenant"})
    monkeypatch.setattr(server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(server, "_RATE_LIMIT_PER_MIN", 300)
    monkeypatch.setattr(server, "_RATE_LIMIT_PER_MIN_AUTH", 3000)
    monkeypatch.setattr(server, "MAX_UPLOAD_BYTES", 1024)
    results = []
    with caplog.at_level(logging.INFO, logger="overlay.server"):
        for legacy in (True, False):
            caplog.clear()
            monkeypatch.setattr(server, "OPS_METRICS", fresh_metrics())
            monkeypatch.setattr(server, "_rate_limit_buckets", {})
            request_headers = {"x-api-key": key, "x-request-id": "guard-id"}
            path = "/api/guard-contract"
            if case == "handled":
                path += "?code=500"
            elif case == "origin":
                request_headers["origin"] = "https://invalid.example"
            elif case == "auth":
                request_headers.pop("x-api-key")
            elif case == "rate":
                monkeypatch.setattr(server, "_rate_limit_buckets", {
                    "tenant:tenant": deque([server.time.monotonic()] * 3000)})
            elif case == "bodylimit":
                request_headers["content-length"] = "1025"
            with TestClient(isolated_stack(legacy)) as client:
                response = client.get(path, headers=request_headers)
            assert response.status_code == status
            assert len(completion_records(caplog)) == completed
            assert server.OPS_METRICS["requests_total"] == completed
            assert ("x-request-id" in response.headers) is headers
            for name, value in SECURITY.items():
                assert response.headers.get(name.decode()) == (value.decode() if headers else None)
            selected = {k: v for k, v in response.headers.items()
                        if k.encode() in SECURITY or k in {"x-request-id", "retry-after", "www-authenticate"}}
            results.append((response.status_code, response.json(), selected, comparable_metrics(server.OPS_METRICS)))
            if completed:
                record, = completion_records(caplog)
                assert record.request_id == "guard-id" and record.status == status
    assert results[0] == results[1]


def test_registered_order_and_no_legacy_guard_dispatch():
    entries = server.app.user_middleware
    labels = [m.kwargs["dispatch"].__name__ if "dispatch" in m.kwargs else m.cls.__name__ for m in entries]
    expected = ["BodyLimitMiddleware", "rate_limit_middleware", "api_key_auth_middleware",
                "RequestGovernorMiddleware", "SecurityHeadersMiddleware", "RequestIdMiddleware", "OriginGateMiddleware"]
    indices = [labels.index(name) for name in expected]
    assert indices == sorted(indices)
    for legacy in (server.enforce_origin_gate, server.request_governor_middleware):
        assert not any(m.kwargs.get("dispatch") is legacy for m in entries)


def test_origin_accepted_http_stream_is_identity_passthrough():
    async def run():
        s = scope(headers=[(b"origin", b"http://localhost")])
        before = copy.deepcopy(s)
        output = []
        messages = [{"type": "http.response.start", "status": 206, "headers": [], "trailers": True},
                    {"type": "http.response.body", "body": b"a", "more_body": True},
                    {"type": "http.response.body", "body": b"", "more_body": True},
                    {"type": "http.response.body", "body": b"z", "more_body": False},
                    {"type": "http.response.trailers", "headers": [(b"checksum", b"ok")]}]
        async def receive():
            raise AssertionError("guard may not consume receive")
        async def send(message):
            output.append(message)
        async def endpoint(actual, recv, emit):
            assert actual is s and recv is receive and emit is send
            for index, message in enumerate(messages):
                await emit(message)
                assert len(output) == index + 1
        await wrap(endpoint, "origin")(s, receive, send)
        assert output == messages and s == before
    asyncio.run(run())


@pytest.mark.parametrize("role", ["origin", "governor"])
@pytest.mark.parametrize("started", [False, True])
def test_real_task_cancellation_finalizes_downstream(role, started, caplog):
    async def run():
        entered, finalized = asyncio.Event(), asyncio.Event()
        async def endpoint(s, receive, send):
            try:
                if started:
                    await send({"type": "http.response.start", "status": 200, "headers": []})
                entered.set()
                await asyncio.Event().wait()
            finally:
                finalized.set()
        task = asyncio.create_task(invoke(wrap(endpoint, role), scope()))
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finalized.is_set()
        expected = int(started and role == "governor")
        assert len(completion_records(caplog)) == expected
        assert server.OPS_METRICS["requests_total"] == expected
    with caplog.at_level(logging.INFO, logger="overlay.server"):
        asyncio.run(run())


@pytest.mark.parametrize("role", ["origin", "governor"])
def test_outer_start_send_failure_propagates_but_header_ready_completion_remains(role, caplog):
    async def run():
        error = OSError("client disconnected while forwarding start")
        async def send(message):
            raise error
        async def endpoint(s, receive, emit):
            await emit({"type": "http.response.start", "status": 200, "headers": []})
        with pytest.raises(OSError) as exc:
            await invoke(wrap(endpoint, role), scope(), send=send)
        assert exc.value is error
        expected = int(role == "governor")
        assert len(completion_records(caplog)) == expected
        assert server.OPS_METRICS["requests_total"] == expected
    with caplog.at_level(logging.INFO, logger="overlay.server"):
        asyncio.run(run())
