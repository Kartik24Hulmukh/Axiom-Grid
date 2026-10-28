"""Engineering-preview contracts for the two response-only ASGI conversions.

The original dispatch callables are the differential oracle. These tests never
invoke extraction, inference, external services, or the production lifespan.
"""
import asyncio
import copy
from collections import deque
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from overlay import server

FIXED_ID = "0123456789abcdef0123456789abcdef"
SECURITY = {
    b"x-content-type-options": b"nosniff",
    b"x-frame-options": b"DENY",
    b"referrer-policy": b"no-referrer",
    b"permissions-policy": b"camera=(), microphone=(), geolocation=()",
}
CSP = (b"default-src 'self'; script-src 'self' 'unsafe-inline'; "
       b"style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       b"connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")


@pytest.fixture(autouse=True)
def running_overlay():
    """Override directory fixture: isolated ASGI apps need no global lifespan."""
    yield


@pytest.fixture(autouse=True)
def deterministic_ids(monkeypatch):
    monkeypatch.setattr(server.uuid, "uuid4", lambda: SimpleNamespace(hex=FIXED_ID))


def scope(path="/api/contract", headers=(), state=None):
    result = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
              "http_version": "1.1", "method": "GET", "scheme": "http",
              "path": path, "raw_path": path.encode(), "root_path": "",
              "query_string": b"", "headers": list(headers),
              "server": ("testserver", 80), "client": ("127.0.0.1", 1234)}
    if state is not None:
        result["state"] = state
    return result


def registered(role):
    expected = role.replace("_", "") + "middleware"
    matches = [m for m in server.app.user_middleware
               if m.cls.__name__.replace("_", "").lower() == expected]
    assert len(matches) == 1, f"Expected one registered pure ASGI {role} middleware"
    entry = matches[0]
    assert not issubclass(entry.cls, BaseHTTPMiddleware)
    return entry


def wrap(app, roles=("request_id", "security_headers")):
    for role in roles:
        item = registered(role)
        app = item.cls(app, **item.kwargs)
    return app


async def invoke(app, request_scope, receive=None, send=None):
    messages = []

    async def no_receive():
        raise AssertionError("Response middleware must not consume request messages")

    async def capture(message):
        messages.append(copy.deepcopy(message))

    await app(request_scope, receive or no_receive, send or capture)
    return messages


def header_values(messages, name):
    start = next(m for m in messages if m["type"] == "http.response.start")
    return [value for key, value in start["headers"] if key.lower() == name]


@pytest.mark.parametrize("raw", [None, b"", b" \t ", b"client-ID_1.2", b" a/b\r\nc\x00\xff ",
                                      b"a" * 64, b"a" * 65, b"!/@\xff", b"x" * 64 + b"!"])
def test_request_id_differential_and_shared_state(raw):
    async def run():
        headers = [] if raw is None else [(b"x-request-id", raw)]
        legacy_scope = scope(headers=headers, state={"tenant": "existing"})
        legacy_response = Response(b"body", headers={"X-REQUEST-ID": "stale"})
        observed = []

        async def call_next(request):
            observed.append(request.state.request_id)
            request.state.downstream = "shared"
            return legacy_response

        await server.request_id_middleware(Request(legacy_scope), call_next)
        shared = {"tenant": "existing"}
        actual_scope = scope(headers=headers, state=shared)

        async def endpoint(s, receive, send):
            assert s is actual_scope and s["state"] is shared
            assert Request(s).state.request_id == observed[0]
            Request(s).state.downstream = "shared"
            await send({"type": "http.response.start", "status": 201,
                        "headers": [(b"x-request-id", b"stale")]})
            await send({"type": "http.response.body", "body": b"body"})

        messages = await invoke(wrap(endpoint, ("request_id",)), actual_scope)
        assert shared == legacy_scope["state"]
        assert header_values(messages, b"x-request-id") == [legacy_response.headers["x-request-id"].encode()]
        assert messages[-1]["body"] == b"body"
    asyncio.run(run())


def test_request_id_first_duplicate_input_and_missing_state():
    async def run():
        s = scope(headers=[(b"x-request-id", b"first"), (b"x-request-id", b"second")])
        async def endpoint(s, receive, send):
            assert s["state"]["request_id"] == "first"
            await send({"type": "http.response.start", "status": 200, "headers": []})
        assert header_values(await invoke(wrap(endpoint, ("request_id",)), s), b"x-request-id") == [b"first"]
    asyncio.run(run())


@pytest.mark.parametrize("path", ["/", "/a.html", "/nested/a.html", "/a.HTML", "/a.html/", "/api/contract", "/a.htmlx"])
@pytest.mark.parametrize("existing_csp", [None, "downstream-policy"])
def test_security_exact_path_rule_differential(path, existing_csp):
    async def run():
        headers = {k.decode().upper(): "stale" for k in SECURITY}
        if existing_csp is not None:
            headers["Content-Security-Policy"] = existing_csp
        original = Response(b"unchanged", headers=headers)
        raw_headers = list(original.raw_headers)
        async def call_next(request):
            return original
        await server.security_headers_middleware(Request(scope(path)), call_next)
        async def endpoint(s, receive, send):
            await send({"type": "http.response.start", "status": 418, "headers": raw_headers})
            await send({"type": "http.response.body", "body": b"unchanged"})
        messages = await invoke(wrap(endpoint, ("security_headers",)), scope(path))
        assert dict(messages[0]["headers"]) == dict(original.raw_headers)
        assert messages[0]["status"] == 418
        assert messages[-1]["body"] == b"unchanged"
        expected = [CSP] if path == "/" or path.endswith(".html") else ([] if existing_csp is None else [existing_csp.encode()])
        assert header_values(messages, b"content-security-policy") == expected
    asyncio.run(run())


def test_compliant_duplicate_targets_are_replaced_without_touching_other_headers():
    async def run():
        expected = {**SECURITY, b"content-security-policy": CSP, b"x-request-id": b"client-id"}
        raw = [(key, b"stale") for key in expected]
        # ASGI requires lowercase response header names. Case-insensitive
        # mapping inputs are covered separately via the legacy Response oracle.
        raw += [(key, b"duplicate") for key in expected]
        raw += [(b"set-cookie", b"a=1"), (b"set-cookie", b"b=2")]
        async def endpoint(s, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": raw})
        messages = await invoke(wrap(endpoint), scope("/", [(b"x-request-id", b"client-id")]))
        for key, value in expected.items():
            assert header_values(messages, key) == [value]
        assert header_values(messages, b"set-cookie") == [b"a=1", b"b=2"]
    asyncio.run(run())


def test_streaming_is_incremental_and_preserves_extensions_and_chunks():
    async def run():
        events = []
        chunks = [{"type": "http.response.body", "body": b"first", "more_body": True},
                  {"type": "http.response.body", "body": b"", "more_body": True},
                  {"type": "http.response.body", "body": b"last", "more_body": False}]
        async def send(message):
            events.append(copy.deepcopy(message))
        async def endpoint(s, receive, send):
            await send({"type": "http.response.start", "status": 206, "headers": [], "trailers": True})
            assert len(events) == 1  # no buffering until response completion
            for index, chunk in enumerate(chunks):
                await send(chunk)
                assert len(events) == index + 2
                await asyncio.sleep(0)
            await send({"type": "http.response.trailers", "headers": [(b"checksum", b"ok")]})
        await invoke(wrap(endpoint), scope("/"), send=send)
        assert events[0]["status"] == 206 and events[0]["trailers"] is True
        assert events[1:4] == chunks
        assert events[4] == {"type": "http.response.trailers", "headers": [(b"checksum", b"ok")]}
    asyncio.run(run())


@pytest.mark.parametrize("role", ["request_id", "security_headers"])
@pytest.mark.parametrize("kind", ["websocket", "lifespan"])
def test_non_http_is_identity_passthrough(role, kind):
    async def run():
        s = {"type": kind}
        before = copy.deepcopy(s)
        async def receive():
            return {"type": kind + ".disconnect"}
        async def send(message):
            pass
        async def endpoint(actual, recv, emit):
            assert actual is s and recv is receive and emit is send
        await wrap(endpoint, (role,))(s, receive, send)
        assert s == before
    asyncio.run(run())


@pytest.mark.parametrize("after_start", [False, True])
@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
def test_exception_and_cancellation_propagate_without_fabricated_response(after_start, failure):
    async def run():
        events = []
        error = failure("synthetic failure")
        async def send(message):
            events.append(message)
        async def endpoint(s, receive, send):
            if after_start:
                await send({"type": "http.response.start", "status": 200, "headers": []})
                await send({"type": "http.response.body", "body": b"part", "more_body": True})
            raise error
        with pytest.raises(failure) as exc:
            await invoke(wrap(endpoint), scope(), send=send)
        assert exc.value is error
        assert len(events) == (2 if after_start else 0)
    asyncio.run(run())


def test_disconnect_receive_and_send_failures_are_not_swallowed():
    async def run():
        disconnect = {"type": "http.disconnect"}
        calls = []
        async def receive():
            calls.append("receive")
            return disconnect
        async def endpoint(s, recv, send):
            assert recv is receive
            assert await recv() is disconnect
        assert await invoke(wrap(endpoint), scope(), receive=receive) == []
        assert calls == ["receive"]
        error = OSError("client disconnected")
        async def broken_send(message):
            raise error
        async def emitting(s, recv, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
        with pytest.raises(OSError) as exc:
            await invoke(wrap(emitting), scope(), send=broken_send)
        assert exc.value is error
    asyncio.run(run())


def test_inflight_task_cancellation_is_not_detached_or_swallowed():
    async def run():
        started, finalized = asyncio.Event(), asyncio.Event()
        async def endpoint(s, receive, send):
            try:
                started.set()
                await asyncio.Event().wait()
            finally:
                finalized.set()
        task = asyncio.create_task(invoke(wrap(endpoint), scope()))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finalized.is_set()
    asyncio.run(run())


def test_concurrent_requests_do_not_share_correlation_state():
    async def run():
        entered = 0
        ready = asyncio.Event()
        async def endpoint(s, receive, send):
            nonlocal entered
            entered += 1
            if entered == 2:
                ready.set()
            await asyncio.wait_for(ready.wait(), 1)
            await send({"type": "http.response.start", "status": 200, "headers": []})
        app = wrap(endpoint)
        first, second = await asyncio.gather(
            invoke(app, scope(headers=[(b"x-request-id", b"first")])),
            invoke(app, scope(headers=[(b"x-request-id", b"second")])))
        assert header_values(first, b"x-request-id") == [b"first"]
        assert header_values(second, b"x-request-id") == [b"second"]
    asyncio.run(run())


def isolated_app(legacy=False):
    app = FastAPI()
    for entry in server.app.user_middleware:
        replacement = entry
        for role in ("request_id", "security_headers"):
            if entry is registered(role) and legacy:
                replacement = Middleware(BaseHTTPMiddleware, dispatch=getattr(server, role + "_middleware"))
        app.user_middleware.append(replacement)

    @app.get("/api/contract")
    async def endpoint(request: Request, code: int = 200):
        if code != 200:
            raise HTTPException(code, detail="synthetic handled error")
        return {"request_id": request.state.request_id, "tenant": getattr(request.state, "tenant", None)}
    return app


def test_registered_order_preserves_upstream_visibility_and_legacy_functions():
    entries = server.app.user_middleware
    labels = []
    for entry in entries:
        dispatch = entry.kwargs.get("dispatch")
        labels.append(dispatch.__name__ if dispatch else entry.cls.__name__)
    names = ["RateLimitMiddleware", "ApiKeyAuthMiddleware", "RequestGovernorMiddleware",
             registered("security_headers").cls.__name__, registered("request_id").cls.__name__, "OriginGateMiddleware"]
    indices = [labels.index(name) for name in names]
    assert indices == sorted(indices)
    for role in ("request_id", "security_headers"):
        original = getattr(server, role + "_middleware")
        assert callable(original)
        assert not any(m.kwargs.get("dispatch") is original for m in entries)


@pytest.mark.parametrize("scenario, status", [("normal", 200), ("handled", 422), ("handled500", 500),
                                              ("validation", 422), ("notfound", 404), ("origin", 403),
                                              ("auth", 401), ("misconfigured", 503), ("rate", 429), ("bodylimit", 400)])
def test_registered_stack_differential_errors_and_early_rejections(monkeypatch, scenario, status):
    key = "synthetic-contract-key-123456789"
    digest = server.hashlib.sha256(key.encode()).hexdigest()
    monkeypatch.setattr(server, "_API_KEY_DIGESTS", {digest: "synthetic-tenant"})
    monkeypatch.setattr(server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(server, "_RATE_LIMIT_PER_MIN", 300)
    monkeypatch.setattr(server, "_RATE_LIMIT_PER_MIN_AUTH", 3000)
    observations = []
    real_authenticate = server._authenticate
    real_client_key = server._client_key
    def authenticate(request):
        observations.append(("auth", getattr(request.state, "request_id", None)))
        return real_authenticate(request)
    def client_key(request):
        observations.append(("rate", getattr(request.state, "request_id", None)))
        return real_client_key(request)
    monkeypatch.setattr(server, "_authenticate", authenticate)
    monkeypatch.setattr(server, "_client_key", client_key)
    results = []
    for legacy in (True, False):
        observations.clear()
        monkeypatch.setattr(server, "_rate_limit_buckets", {})
        headers = {"x-api-key": key, "x-request-id": "contract-id"}
        path = "/api/contract"
        if scenario == "auth":
            headers.pop("x-api-key")
        elif scenario == "misconfigured":
            monkeypatch.setattr(server, "_API_KEY_DIGESTS", {})
        elif scenario == "rate":
            monkeypatch.setattr(server, "_rate_limit_buckets", {
                "tenant:synthetic-tenant": deque([server.time.monotonic()] * 3000)})
        elif scenario == "bodylimit":
            headers["content-length"] = "not-decimal"
        elif scenario == "origin":
            headers["origin"] = "https://invalid.example"
        elif scenario == "handled":
            path += "?code=422"
        elif scenario == "handled500":
            path += "?code=500"
        elif scenario == "validation":
            path += "?code=not-an-int"
        elif scenario == "notfound":
            path = "/api/contract-missing"
        with TestClient(isolated_app(legacy)) as client:
            response = client.get(path, headers=headers)
        assert response.status_code == status
        if scenario == "bodylimit":
            # The outer BodyLimit rejects malformed lengths before auth/rate.
            assert observations == []
        else:
            assert observations and all(rid is None for _, rid in observations)
        selected = {k: v for k, v in response.headers.items()
                    if k.encode() in SECURITY or k in {"x-request-id", "content-security-policy", "www-authenticate", "retry-after"}}
        results.append((response.status_code, response.json(), selected))
        early = scenario in {"auth", "misconfigured", "rate", "bodylimit"}
        assert ("x-request-id" in response.headers) is not early
        for name, value in SECURITY.items():
            assert response.headers.get(name.decode()) == (None if early else value.decode())
        if scenario == "normal":
            assert response.json() == {"request_id": "contract-id", "tenant": "synthetic-tenant"}
    assert results[0] == results[1]


def test_upstream_state_observer_sees_id_only_after_downstream(monkeypatch):
    monkeypatch.setattr(server, "_API_KEY_DIGESTS", {})
    monkeypatch.setattr(server, "_AUTH_REQUIRED", False)
    monkeypatch.setattr(server, "_RATE_LIMIT_PER_MIN", 0)
    snapshots = []
    for legacy in (True, False):
        app = isolated_app(legacy)
        observed = []
        async def upstream(request, call_next, observed=observed):
            observed.append(getattr(request.state, "request_id", None))
            response = await call_next(request)
            observed.append(request.state.request_id)
            return response
        app.add_middleware(BaseHTTPMiddleware, dispatch=upstream)
        with TestClient(app) as client:
            response = client.get("/api/contract", headers={"x-request-id": "shared-upstream"})
        assert response.status_code == 200
        assert observed == [None, "shared-upstream"]
        snapshots.append(observed)
    assert snapshots[0] == snapshots[1]


def test_registered_request_id_length_limit_remains_runtime_configurable(monkeypatch):
    monkeypatch.setattr(server, "_REQUEST_ID_MAX_LEN", 3)
    async def run():
        s = scope(headers=[(b"x-request-id", b"four")])
        async def endpoint(s, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
        original = Response()
        async def call_next(request):
            return original
        await server.request_id_middleware(Request(scope(headers=s["headers"])), call_next)
        messages = await invoke(wrap(endpoint, ("request_id",)), s)
        assert header_values(messages, b"x-request-id") == [original.headers["x-request-id"].encode()] == [FIXED_ID.encode()]
    asyncio.run(run())
