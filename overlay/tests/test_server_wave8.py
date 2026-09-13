"""Wave 8 hardening regressions: OPS-003 request-id correlation,
OPS-004 extraction-pool backpressure (load shedding), SEC-009 information-
disclosure closure on error paths, router lock-acquisition latency budget
and half-open probe deadline."""
import threading
import time

import pytest
from fastapi.testclient import TestClient

from kernel.sidecar.melious_router import MeliousModelRouter, RouterError
from overlay import server as s
from overlay.server import app

client = TestClient(app)


# ---- OPS-003: request-id correlation ------------------------------------

def test_response_echoes_supplied_request_id():
    r = client.get("/healthz", headers={"X-Request-Id": "wave8-abc123"})
    assert r.headers["X-Request-Id"] == "wave8-abc123"


def test_request_id_minted_when_absent():
    r = client.get("/healthz")
    rid = r.headers["X-Request-Id"]
    assert rid and len(rid) == 32
    assert rid != client.get("/healthz").headers["X-Request-Id"]


def test_request_id_sanitized_against_log_injection():
    evil = "ok-id" + chr(13) + chr(10) + "X-Injected: pwned"
    r = client.get("/healthz", headers={"X-Request-Id": evil})
    rid = r.headers["X-Request-Id"]
    assert chr(13) not in rid and chr(10) not in rid and ":" not in rid
    assert rid == "ok-idX-Injectedpwned"


# ---- SEC-009: error responses must not leak internals --------------------

def test_extract_document_read_error_does_not_leak_path_or_exception(tmp_path):
    # A file inside an allowed root (temp dir) that exists as a *directory*
    # forces an OSError on read while passing the sandbox resolver.
    d = tmp_path / "wave8_unreadable.txt"
    d.write_text("SECRET_INTERNAL_CONTENT", encoding="utf-8")
    d.chmod(0o000)
    try:
        r = client.post("/api/extract-document", json={"file": str(d)})
    finally:
        d.chmod(0o644)
    assert r.status_code == 422
    assert r.json()["detail"] == "Unable to read document"
    assert str(tmp_path) not in r.text and "PermissionError" not in r.text


# ---- OPS-004: extraction-pool backpressure --------------------------------

def test_extraction_pool_sheds_load_fast_when_saturated(monkeypatch):
    monkeypatch.setattr(s, "_extraction_slots", threading.BoundedSemaphore(1))
    gate = threading.Event()

    def slow_run(_doc):
        gate.wait(5)
        raise AssertionError("should be cancelled by gate set in finally")

    import overlay.server as _srv
    monkeypatch.setattr(_srv.orchestrator, "run", slow_run)
    try:
        # Saturate the single slot from a background thread.
        bg = {}
        def occupy():
            bg["resp"] = client.post("/api/extract-document", json={"file": "fixtures/wedge/sample_memo_01.txt"})
        t = threading.Thread(target=occupy)
        t.start()
        time.sleep(0.5)  # let the background request take the slot
        t0 = time.perf_counter()
        r = client.post("/api/extract-document", json={"file": "fixtures/wedge/sample_memo_01.txt"})
        dt = time.perf_counter() - t0
        assert r.status_code == 503
        assert "saturated" in r.json()["detail"]
        assert r.headers["Retry-After"] == "1"
        assert dt < 2.0, f"shedding must be fast, took {dt:.2f}s"
        assert s.OPS_METRICS.get("extraction_shed_total", 0) >= 1
    finally:
        gate.set()
        t.join(timeout=10)


def test_extraction_shed_counter_in_prometheus_metrics():
    s.OPS_METRICS["extraction_shed_total"] = 3
    body = client.get("/metrics?format=prometheus").text
    assert "axiom_extraction_shed_total 3" in body
    assert "extraction_shed_total" in client.get("/metrics").json()


# ---- Router: lock-acquisition latency budget + probe deadline -------------

def _ok(model, payload, timeout):
    return {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 1}}


def test_router_fails_fast_when_lock_is_held():
    r = MeliousModelRouter(transport=_ok, acquire_timeout=0.05)
    hold = threading.Event()
    holder = threading.Thread(target=lambda: (r._lock.acquire(), hold.set(), time.sleep(1.5), r._lock.release()))
    holder.start()
    hold.wait(2)  # another thread owns the RLock now (same-thread would re-enter)
    try:
        t0 = time.perf_counter()
        with pytest.raises(RouterError, match="saturated"):
            r.complete([{"role": "user", "content": "hi"}])
        assert time.perf_counter() - t0 < 1.0
    finally:
        holder.join(timeout=5)
    # Router is still healthy once the lock is free.
    out = r.complete([{"role": "user", "content": "hi"}])
    assert out["router"]["selected_model"] == r.models[0]


def test_half_open_probe_uses_shorter_probe_timeout():
    seen_timeouts = []
    def slow_fail(model, payload, timeout):
        seen_timeouts.append(timeout)
        raise TimeoutError("upstream hung")
    r = MeliousModelRouter(models=("m1",), transport=slow_fail, timeout=10.0,
                           probe_timeout=2.0, max_retries=0, sleep=lambda _s: None)
    breaker = r.breakers["m1"]
    breaker.failure_threshold = 1
    with pytest.raises(RouterError):
        r.complete([{"role": "user", "content": "x"}])
    assert breaker.state == "OPEN"
    breaker.opened_at -= 999  # force recovery window elapsed -> next call is the probe
    with pytest.raises(RouterError):
        r.complete([{"role": "user", "content": "x"}])
    assert seen_timeouts[0] == 10.0          # normal call: full timeout
    assert seen_timeouts[1] == 2.0           # half-open probe: short deadline
    assert breaker.state == "OPEN"           # failed probe re-opens
