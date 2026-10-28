"""Engineering-preview contracts for the auth/rate pure-ASGI gates only."""
import asyncio
import copy
import threading
from collections import deque

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from overlay import server
from overlay.tests.test_request_guard_contract import fresh_metrics
from overlay.tests.test_response_middleware_contract import SECURITY, invoke, scope

KEYS = ["synthetic-gate-key-first", "synthetic-gate-key-middle", "synthetic-gate-key-last"]
DIGESTS = {server.hashlib.sha256(key.encode()).hexdigest(): f"tenant-{i}" for i, key in enumerate(KEYS)}


@pytest.fixture(autouse=True)
def running_overlay(monkeypatch):
    """No production lifespan, inference, or external services."""
    monkeypatch.setattr(server, "OPS_METRICS", fresh_metrics())
    monkeypatch.setattr(server, "_API_KEY_DIGESTS", {})
    monkeypatch.setattr(server, "_AUTH_REQUIRED", False)
    monkeypatch.setattr(server, "_AUTH_EXEMPT_PATHS", {"/healthz"})
    monkeypatch.setattr(server, "_AUTH_EXEMPT_PREFIXES", ())
    monkeypatch.setattr(server, "_RATE_LIMIT_PER_MIN", 2)
    monkeypatch.setattr(server, "_RATE_LIMIT_PER_MIN_AUTH", 3)
    monkeypatch.setattr(server, "_RATE_LIMIT_WINDOW_S", 60.)
    monkeypatch.setattr(server, "_RATE_LIMIT_EXEMPT_PATHS", {"/healthz"})
    monkeypatch.setattr(server, "_RATE_LIMIT_BUCKET_HIGH_WATER", 10)
    monkeypatch.setattr(server, "_RATE_LIMIT_BUCKET_HARD_CAP", 20)
    monkeypatch.setattr(server, "_rate_limit_buckets", {})
    monkeypatch.setattr(server, "_rate_limit_lock", threading.Lock())
    monkeypatch.setattr(server, "_TRUST_PROXY", False)
    yield


def registered(role):
    name = {"auth": "ApiKeyAuthMiddleware", "rate": "RateLimitMiddleware"}[role]
    entries = [m for m in server.app.user_middleware if m.cls.__name__ == name]
    assert len(entries) == 1, f"Expected one registered {name}"
    assert not issubclass(entries[0].cls, BaseHTTPMiddleware)
    return entries[0]


def wrap(app, role):
    entry = registered(role)
    return entry.cls(app, **entry.kwargs)


async def exercise(role, legacy, s):
    called = []
    async def call_next(request):
        called.append(True)
        assert not server._rate_limit_lock.locked()
        return Response(b"ok", status_code=202, headers={"x-kept": "yes"})
    async def endpoint(actual, receive, send):
        assert actual is s
        assert not server._rate_limit_lock.locked()
        called.append(True)
        await send({"type": "http.response.start", "status": 202,
                    "headers": [(b"content-length", b"2"), (b"x-kept", b"yes")]})
        await send({"type": "http.response.body", "body": b"ok"})
    if legacy:
        original = server.api_key_auth_middleware if role == "auth" else server.rate_limit_middleware
        response = await original(Request(s), call_next)
        result = response.status_code, response.body, dict(response.raw_headers)
    else:
        messages = await invoke(wrap(endpoint, role), s)
        result = (messages[0]["status"], b"".join(m.get("body", b"") for m in messages),
                  dict(messages[0]["headers"]))
    assert not server._rate_limit_lock.locked()
    return result, called, s.get("state", {}), copy.deepcopy(server.OPS_METRICS), copy.deepcopy(server._rate_limit_buckets)


@pytest.mark.parametrize("configured,required,path,headers,status,tenant", [
    (False, False, "/api/private", [], 202, None),
    (False, True, "/api/private", [], 503, None),
    (False, True, "/healthz", [], 202, None),
    (True, False, "/healthz", [], 202, None),
    (True, False, "/api/private", [], 401, None),
    (True, True, "/api/private", [(b"x-api-key", b"invalid")], 401, None),
    (True, False, "/api/private", [(b"x-api-key", KEYS[0].encode())], 202, "tenant-0"),
    (True, True, "/api/private", [(b"authorization", ("bEaReR " + KEYS[1]).encode())], 202, "tenant-1"),
    (True, False, "/api/private", [(b"x-api-key", (" " + KEYS[2] + " ").encode())], 202, "tenant-2"),
    (True, False, "/api/private", [(b"authorization", b"Bearer wrong"), (b"x-api-key", KEYS[0].encode())], 401, None),
    (True, False, "/api/private", [(b"authorization", b"Basic ignored"), (b"x-api-key", KEYS[0].encode())], 202, "tenant-0"),
    (True, False, "/api/private", [(b"authorization", b"Bearer "), (b"x-api-key", KEYS[0].encode())], 202, "tenant-0"),
    (True, False, "/healthz/child", [], 401, None),
])
def test_auth_differential_and_fail_closed(monkeypatch, configured, required, path, headers, status, tenant):
    monkeypatch.setattr(server, "_API_KEY_DIGESTS", dict(DIGESTS) if configured else {})
    monkeypatch.setattr(server, "_AUTH_REQUIRED", required)
    async def run():
        results = []
        for legacy in (True, False):
            monkeypatch.setattr(server, "OPS_METRICS", fresh_metrics())
            result = await exercise("auth", legacy, scope(path, headers, {"request_id": "preserved"}))
            response, calls, state, metrics, _ = result
            assert response[0] == status and bool(calls) is (status == 202)
            assert state.get("tenant") == tenant and state["request_id"] == "preserved"
            assert metrics.get("auth_rejections_total", 0) == int(status in {401, 503})
            assert response[2].get(b"www-authenticate") == (b'Bearer realm="axiom-grid"' if status == 401 else None)
            if status == 503:
                assert b"Service misconfigured" in response[1]
            results.append(result)
        assert results[0] == results[1]
    asyncio.run(run())


@pytest.mark.parametrize("key", [*KEYS, "invalid-key", None])
def test_auth_checks_all_configured_digests_without_early_success(monkeypatch, key):
    monkeypatch.setattr(server, "_API_KEY_DIGESTS", dict(DIGESTS))
    comparisons = []
    real_compare = server.hmac.compare_digest
    def compare(a, b):
        comparisons.append((a, b))
        return real_compare(a, b)
    monkeypatch.setattr(server.hmac, "compare_digest", compare)
    async def run():
        headers = [] if key is None else [(b"x-api-key", key.encode())]
        await exercise("auth", False, scope(headers=headers))
        expected = [] if key is None else [(server.hashlib.sha256(key.encode()).hexdigest(), digest) for digest in DIGESTS]
        assert comparisons == expected
    asyncio.run(run())


def test_auth_current_configuration_exemptions_and_metric_map(monkeypatch):
    async def run():
        async def endpoint(s, receive, send):
            await send({"type": "http.response.start", "status": 204, "headers": []})
        app = wrap(endpoint, "auth")
        old = server.OPS_METRICS
        monkeypatch.setattr(server, "_AUTH_REQUIRED", True)
        current = fresh_metrics()
        monkeypatch.setattr(server, "OPS_METRICS", current)
        assert (await invoke(app, scope()))[0]["status"] == 503
        monkeypatch.setattr(server, "_API_KEY_DIGESTS", dict(DIGESTS))
        assert (await invoke(app, scope()))[0]["status"] == 401
        s = scope(headers=[(b"x-api-key", KEYS[0].encode())], state={"tenant": "old", "request_id": "keep"})
        assert (await invoke(app, s))[0]["status"] == 204
        assert s["state"] == {"tenant": "tenant-0", "request_id": "keep"}
        monkeypatch.setattr(server, "_AUTH_EXEMPT_PATHS", {"/api/contract"})
        assert (await invoke(app, scope()))[0]["status"] == 204
        monkeypatch.setattr(server, "_AUTH_EXEMPT_PATHS", set())
        monkeypatch.setattr(server, "_AUTH_EXEMPT_PREFIXES", ("/public/",))
        assert (await invoke(app, scope("/public/child")))[0]["status"] == 204
        assert (await invoke(app, scope("/publicity")))[0]["status"] == 401
        assert current["auth_rejections_total"] == 3
        assert "auth_rejections_total" not in old
    asyncio.run(run())


@pytest.mark.parametrize("trusted,forwarded,key,client,expected", [
    (False, b"1.2.3.4", None, ("10.0.0.1", 2), "10.0.0.1"),
    (True, b" 1.2.3.4 , 5.6.7.8", None, ("10.0.0.1", 2), "1.2.3.4"),
    (True, b"not-an-ip", None, None, "not-an-ip"),
    (True, b" , 5.6.7.8", None, ("10.0.0.1", 2), "10.0.0.1"),
    (True, b"x" * 65, None, None, "unknown"),
    (False, None, None, None, "unknown"),
    (True, b"1.2.3.4", KEYS[0], ("10.0.0.1", 2), "tenant:tenant-0"),
    (True, b"1.2.3.4", "invalid", ("10.0.0.1", 2), "1.2.3.4"),
])
def test_rate_bucket_identity_preserves_tenant_proxy_and_ip_semantics(monkeypatch, trusted, forwarded, key, client, expected):
    monkeypatch.setattr(server, "_TRUST_PROXY", trusted)
    monkeypatch.setattr(server, "_API_KEY_DIGESTS", dict(DIGESTS))
    headers = [] if forwarded is None else [(b"x-forwarded-for", forwarded)]
    if key is not None:
        headers.append((b"x-api-key", key.encode()))
    s = scope(headers=headers)
    s["client"] = client
    asyncio.run(exercise("rate", False, s))
    assert list(server._rate_limit_buckets) == [expected]


@pytest.mark.parametrize("case,expected", [("fresh", 202), ("full", 429), ("expired", 202),
                                         ("boundary", 429), ("tenant", 202), ("tenantfull", 429),
                                         ("disabled", 202), ("exempt", 202), ("minretry", 429)])
def test_rate_differential_window_retry_and_bypass(monkeypatch, case, expected):
    # A fixed synchronous monotonic value does not affect an asyncio clock:
    # avoid patching the shared time module used by event-loop scheduling.
    import types
    monkeypatch.setattr(server, "time", types.SimpleNamespace(monotonic=lambda: 100.))
    if case.startswith("tenant"):
        monkeypatch.setattr(server, "_API_KEY_DIGESTS", dict(DIGESTS))
    if case == "disabled":
        monkeypatch.setattr(server, "_RATE_LIMIT_PER_MIN", 0)
    async def run():
        results = []
        for legacy in (True, False):
            initial = {"full": [99., 100.], "expired": [39., 99.], "boundary": [40., 99.],
                       "tenant": [99., 100.], "tenantfull": [98., 99., 100.],
                       "disabled": [99., 100.], "exempt": [99., 100.], "minretry": [40., 40.]}.get(case, [])
            name = "tenant:tenant-0" if case.startswith("tenant") else "127.0.0.1"
            buckets = {name: deque(initial)} if initial else {}
            monkeypatch.setattr(server, "_rate_limit_buckets", buckets)
            s = scope("/healthz" if case == "exempt" else "/api/contract",
                      [(b"x-api-key", KEYS[0].encode())] if case.startswith("tenant") else [])
            result = await exercise("rate", legacy, s)
            response, calls, _, _, actual = result
            assert response[0] == expected and bool(calls) is (expected == 202)
            if expected == 429:
                expected_retry = {"full": b"59", "tenantfull": b"58", "boundary": b"1", "minretry": b"1"}
                assert response[2][b"retry-after"] == expected_retry[case]
                assert list(actual[name]) == initial
            elif case in {"disabled", "exempt"}:
                assert actual == buckets and list(actual[name]) == initial
            else:
                assert actual[name][-1] == 100.
                if case == "expired":
                    assert list(actual[name]) == [99., 100.]
            results.append(result)
        assert results[0] == results[1]
    asyncio.run(run())


def test_rate_stale_cleanup_and_hard_cap_eviction_preserve_current_map(monkeypatch):
    import types
    monkeypatch.setattr(server, "time", types.SimpleNamespace(monotonic=lambda: 100.))
    monkeypatch.setattr(server, "_RATE_LIMIT_BUCKET_HIGH_WATER", 2)
    monkeypatch.setattr(server, "_RATE_LIMIT_BUCKET_HARD_CAP", 3)
    async def run():
        for legacy in (True, False):
            buckets = {"empty": deque(), "stale": deque([39.]), "current": deque([99.])}
            monkeypatch.setattr(server, "_rate_limit_buckets", buckets)
            await exercise("rate", legacy, scope())
            assert server._rate_limit_buckets is buckets
            assert set(buckets) == {"current", "127.0.0.1"}
            buckets.clear()
            buckets.update({"oldest": deque([70.]), "middle": deque([80.]), "newest": deque([90.])})
            await exercise("rate", legacy, scope())
            assert set(buckets) == {"middle", "newest", "127.0.0.1"}
            # Existing key at cap must not evict unrelated buckets.
            await exercise("rate", legacy, scope())
            assert set(buckets) == {"middle", "newest", "127.0.0.1"}
    asyncio.run(run())


def test_rate_dynamic_buckets_limits_proxy_exemption_and_lock(monkeypatch):
    async def run():
        async def endpoint(s, receive, send):
            assert not server._rate_limit_lock.locked()
            await send({"type": "http.response.start", "status": 204, "headers": []})
        app = wrap(endpoint, "rate")
        old = server._rate_limit_buckets
        current = {}
        monkeypatch.setattr(server, "_rate_limit_buckets", current)
        lock = threading.Lock()
        monkeypatch.setattr(server, "_rate_limit_lock", lock)
        monkeypatch.setattr(server, "_TRUST_PROXY", True)
        monkeypatch.setattr(server, "_RATE_LIMIT_PER_MIN", 1)
        s = lambda: scope(headers=[(b"x-forwarded-for", b"dynamic-ip")])
        assert (await invoke(app, s()))[0]["status"] == 204
        assert (await invoke(app, s()))[0]["status"] == 429
        monkeypatch.setattr(server, "_RATE_LIMIT_PER_MIN", 2)
        assert (await invoke(app, s()))[0]["status"] == 204
        monkeypatch.setattr(server, "_RATE_LIMIT_EXEMPT_PATHS", {"/api/contract"})
        assert (await invoke(app, s()))[0]["status"] == 204
        assert len(current["dynamic-ip"]) == 2 and not old and not lock.locked()
    asyncio.run(run())


@pytest.mark.parametrize("role", ["auth", "rate"])
@pytest.mark.parametrize("kind", ["websocket", "lifespan"])
def test_non_http_identity_no_gate_io(role, kind, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("HTTP-only helper called for non-HTTP scope")
    monkeypatch.setattr(server, "_auth_enabled", forbidden)
    monkeypatch.setattr(server, "_authenticate", forbidden)
    monkeypatch.setattr(server, "_client_key", forbidden)
    async def run():
        s = {"type": kind}
        async def receive():
            raise AssertionError("unexpected receive")
        async def send(message):
            raise AssertionError("unexpected send")
        async def endpoint(actual, recv, emit):
            assert actual is s and recv is receive and emit is send
        await wrap(endpoint, role)(s, receive, send)
        assert s == {"type": kind}
    asyncio.run(run())


@pytest.mark.parametrize("role", ["auth", "rate"])
def test_http_stream_is_identity_passthrough_and_lock_not_held(role):
    async def run():
        s = scope()
        output = []
        events = [{"type": "http.response.start", "status": 206, "headers": [], "trailers": True},
                  {"type": "http.response.body", "body": b"one", "more_body": True},
                  {"type": "http.response.body", "body": b"", "more_body": True},
                  {"type": "http.response.body", "body": b"two", "more_body": False},
                  {"type": "http.response.trailers", "headers": [(b"checksum", b"ok")]}]
        async def receive():
            return {"type": "http.disconnect"}
        async def send(message):
            assert not server._rate_limit_lock.locked()
            output.append(message)
        async def endpoint(actual, recv, emit):
            assert actual is s and recv is receive and emit is send
            for index, message in enumerate(events):
                await emit(message)
                assert len(output) == index + 1
            assert await recv() == {"type": "http.disconnect"}
        await wrap(endpoint, role)(s, receive, send)
        assert output == events
    asyncio.run(run())


@pytest.mark.parametrize("role", ["auth", "rate"])
@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError, OSError])
def test_downstream_errors_propagate_and_release_lock(role, failure):
    async def run():
        error = failure("synthetic")
        async def endpoint(s, receive, send):
            assert not server._rate_limit_lock.locked()
            raise error
        with pytest.raises(failure) as exc:
            await invoke(wrap(endpoint, role), scope())
        assert exc.value is error and not server._rate_limit_lock.locked()
    asyncio.run(run())


def test_rate_exception_inside_critical_section_releases_lock(monkeypatch):
    class BrokenBuckets(dict):
        def setdefault(self, *args):
            assert server._rate_limit_lock.locked()
            raise RuntimeError("synthetic map error")
    monkeypatch.setattr(server, "_rate_limit_buckets", BrokenBuckets())
    async def run():
        async def endpoint(s, receive, send):
            raise AssertionError("must reject before endpoint")
        with pytest.raises(RuntimeError, match="synthetic map error"):
            await invoke(wrap(endpoint, "rate"), scope())
        assert not server._rate_limit_lock.locked()
    asyncio.run(run())


def full_stack(legacy):
    app = FastAPI()
    originals = {"ApiKeyAuthMiddleware": server.api_key_auth_middleware,
                 "RateLimitMiddleware": server.rate_limit_middleware,
                 "OriginGateMiddleware": server.enforce_origin_gate,
                 "RequestGovernorMiddleware": server.request_governor_middleware,
                 "RequestIdMiddleware": server.request_id_middleware,
                 "SecurityHeadersMiddleware": server.security_headers_middleware}
    for entry in server.app.user_middleware:
        dispatch = originals.get(entry.cls.__name__)
        app.user_middleware.append(Middleware(BaseHTTPMiddleware, dispatch=dispatch) if legacy and dispatch else entry)
    @app.get("/api/gate-contract")
    async def endpoint(request: Request, code: int = 200):
        if code != 200:
            raise HTTPException(code, "synthetic")
        return {"tenant": getattr(request.state, "tenant", None), "request_id": request.state.request_id}
    return app


@pytest.mark.parametrize("case,status,headers", [("normal", 200, True), ("handled", 422, True),
                                              ("origin", 403, True), ("auth", 401, False),
                                              ("misconfigured", 503, False), ("rate", 429, False)])
def test_all_six_legacy_vs_registered_stack(monkeypatch, case, status, headers):
    monkeypatch.setattr(server, "_API_KEY_DIGESTS", dict(DIGESTS))
    monkeypatch.setattr(server, "_AUTH_REQUIRED", True)
    async_results = []
    for legacy in (True, False):
        monkeypatch.setattr(server, "OPS_METRICS", fresh_metrics())
        monkeypatch.setattr(server, "_rate_limit_buckets", {})
        h = {"x-api-key": KEYS[0], "x-request-id": "gate-id"}
        path = "/api/gate-contract"
        if case == "handled":
            path += "?code=422"
        elif case == "origin":
            h["origin"] = "https://invalid.example"
        elif case == "auth":
            h.pop("x-api-key")
        elif case == "misconfigured":
            monkeypatch.setattr(server, "_API_KEY_DIGESTS", {})
        elif case == "rate":
            monkeypatch.setattr(server, "_rate_limit_buckets", {"tenant:tenant-0": deque([server.time.monotonic()] * 3)})
        with TestClient(full_stack(legacy)) as client:
            response = client.get(path, headers=h)
        assert response.status_code == status
        assert ("x-request-id" in response.headers) is headers
        for name, value in SECURITY.items():
            assert response.headers.get(name.decode()) == (value.decode() if headers else None)
        assert server.OPS_METRICS["requests_total"] == int(headers)
        if case == "normal":
            assert response.json() == {"tenant": "tenant-0", "request_id": "gate-id"}
        selected = {k: v for k, v in response.headers.items() if k.encode() in SECURITY or k in {"x-request-id", "retry-after", "www-authenticate"}}
        async_results.append((status, response.json(), selected, server.OPS_METRICS.get("auth_rejections_total", 0)))
    assert async_results[0] == async_results[1]


def test_original_order_and_no_legacy_dispatch_registration():
    entries = server.app.user_middleware
    labels = [m.kwargs["dispatch"].__name__ if "dispatch" in m.kwargs else m.cls.__name__ for m in entries]
    expected = ["BodyLimitMiddleware", "RateLimitMiddleware", "ApiKeyAuthMiddleware", "RequestGovernorMiddleware",
                "SecurityHeadersMiddleware", "RequestIdMiddleware", "OriginGateMiddleware"]
    positions = [labels.index(name) for name in expected]
    assert positions == sorted(positions)
    for role, original in (("auth", server.api_key_auth_middleware), ("rate", server.rate_limit_middleware)):
        registered(role)
        assert not any(m.kwargs.get("dispatch") is original for m in entries)


@pytest.mark.parametrize("role", ["auth", "rate"])
def test_actual_cancellation_does_not_detach_downstream_or_hold_lock(role):
    async def run():
        entered, finalized = asyncio.Event(), asyncio.Event()
        async def endpoint(s, receive, send):
            try:
                assert not server._rate_limit_lock.locked()
                entered.set()
                await asyncio.Event().wait()
            finally:
                finalized.set()
        task = asyncio.create_task(invoke(wrap(endpoint, role), scope()))
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finalized.is_set() and not server._rate_limit_lock.locked()
    asyncio.run(run())


def test_rate_rejection_send_failure_happens_after_lock_release(monkeypatch):
    monkeypatch.setattr(server, "_rate_limit_buckets", {"127.0.0.1": deque([server.time.monotonic()] * 2)})
    async def run():
        error = OSError("synthetic client disconnect")
        async def send(message):
            assert not server._rate_limit_lock.locked()
            raise error
        async def endpoint(s, receive, send):
            raise AssertionError("rejection must not invoke endpoint")
        with pytest.raises(OSError) as exc:
            await invoke(wrap(endpoint, "rate"), scope(), send=send)
        assert exc.value is error and not server._rate_limit_lock.locked()
    asyncio.run(run())
