"""Session 9 launch gate: 100-worker fallback chain under 429/5xx must stay
sub-200ms per call, never raise, and honour Retry-After cooldown.

Deterministic: injected transport, no-op sleep, no wall-clock waits."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from kernel.sidecar.melious_router import CircuitBreaker, MeliousModelRouter, RouterError


class _Upstream(Exception):
    def __init__(self, status, retry_after=0):
        super().__init__(f"HTTP {status}")
        self.status = status
        self.retry_after = retry_after


def _ok(model):
    return {"choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4}, "model": model}


def _router(transport, **kw):
    return MeliousModelRouter(models=("m-primary", "m-ratelimited", "m-flaky", "m-healthy"),
                              transport=transport, sleep=lambda _d: None, max_retries=1,
                              max_inflight=100, **kw)


def test_100_workers_fallback_chain_sub_200ms_and_no_panics():
    calls = {"n": 0}
    lock = threading.Lock()

    def transport(model, payload, timeout):
        with lock:
            calls["n"] += 1
        if model == "m-healthy":
            return _ok(model)
        if model == "m-ratelimited":
            raise _Upstream(429, retry_after=60)
        raise _Upstream(503)

    router = _router(transport)
    latencies = []
    lat_lock = threading.Lock()

    def one(_i):
        t0 = time.perf_counter()
        out = router.complete([{"role": "user", "content": "x"}], max_tokens=8)
        with lat_lock:
            latencies.append(time.perf_counter() - t0)
        return out["model"]

    with ThreadPoolExecutor(max_workers=100) as pool:
        served = list(pool.map(one, range(1000)))

    assert served == ["m-healthy"] * 1000
    latencies.sort()
    p99 = latencies[int(0.99 * (len(latencies) - 1))]
    assert p99 < 0.2, f"P99 fallback decision latency {p99*1000:.1f}ms breaches 200ms breaker budget"
    metrics = router.get_metrics()
    assert metrics["requests"] == 1000 and metrics["successes"] == 1000
    assert metrics["circuits"]["m-primary"] == "OPEN"
    assert metrics["circuits"]["m-flaky"] == "OPEN"
    assert metrics["circuits"]["m-healthy"] == "CLOSED"
    # Open circuits and Retry-After cooldown must shed load: far fewer upstream
    # attempts than 1000 requests x 3 failing routes x (1 + retries).
    assert calls["n"] < 1000 + 3 * 2 * 2 + 1000 // 10


def test_retry_after_cooldown_suppresses_hammering():
    hits = {"m-ratelimited": 0, "m-healthy": 0}

    def transport(model, payload, timeout):
        hits[model] = hits.get(model, 0) + 1
        if model == "m-ratelimited":
            raise _Upstream(429, retry_after=120)
        if model == "m-healthy":
            return _ok(model)
        raise _Upstream(500)

    router = MeliousModelRouter(models=("m-ratelimited", "m-healthy"), transport=transport,
                                sleep=lambda _d: None, max_retries=0, max_inflight=100)
    for _ in range(50):
        assert router.complete([{"role": "user", "content": "x"}], max_tokens=8)["model"] == "m-healthy"
    assert hits["m-ratelimited"] == 1, "429 Retry-After must place the route in cooldown, not be re-hammered"
    assert hits["m-healthy"] == 50


def test_all_routes_down_fails_fast_with_status():
    def transport(model, payload, timeout):
        raise _Upstream(503)

    router = _router(transport)
    t0 = time.perf_counter()
    with pytest.raises(RouterError) as info:
        router.complete([{"role": "user", "content": "x"}], max_tokens=8)
    assert time.perf_counter() - t0 < 0.2
    assert getattr(info.value, "status", None) == 503


def test_breaker_trips_after_threshold_and_admits_single_probe():
    b = CircuitBreaker(recovery_seconds=1.0)
    now = 100.0
    for _ in range(3):
        b.failure(now)
    assert b.opened_at == now and not b.allow(now + 0.5)
    assert b.allow(now + 1.5) is True
    assert b.allow(now + 1.5) is False, "only one half-open probe may be admitted"
