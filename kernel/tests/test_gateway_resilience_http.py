"""Dedicated gateway regression: actual loopback sockets, no provider traffic."""
import contextlib
import json
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from email.utils import formatdate
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from kernel.sidecar.melious_router import MeliousModelRouter, RouterError, SpendCeilingError

MSG = [{"role": "user", "content": "hi"}]


@pytest.fixture
def faults(monkeypatch):
    monkeypatch.setenv("MELIOUS_API_KEY", "loopback-fixture-not-a-provider-key")
    for name in ("MELIOUS_MODELS", "MELIOUS_MODEL_TIMEOUTS", "MELIOUS_TOKEN_CEILING", "MELIOUS_SPEND_LEDGER"):
        monkeypatch.delenv(name, raising=False)
    state = {"calls": [], "entered": threading.Event(), "stop": threading.Event(),
             "mode": "ok", "catalog": {"data": [{"id": "primary"}, {"id": "backup"}]},
             "retry": "60", "release": threading.Event()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            state["calls"].append("GET models")
            self.reply(200, state["catalog"])

        def reply(self, status, data):
            raw = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            if status == 429:
                self.send_header("Retry-After", state["retry"])
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["calls"].append(payload["model"])
            mode = state["mode"]
            state["entered"].set()
            if mode in {"trickle", "headers"}:
                try:
                    if mode == "trickle":
                        self.send_response(200)
                        self.send_header("Content-Length", "10000")
                        self.end_headers()
                    else:
                        self.wfile.write(b"HTTP/1.1 200 OK\r\nX-Slow: ")
                        self.wfile.flush()
                    for _ in range(80):
                        if state["stop"].wait(.02):
                            break
                        self.wfile.write(b" ")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            if mode == "failover" and payload["model"] == "primary":
                self.reply(503, {"error": "upstream-secret-sentinel"})
                return
            if mode == "limited" and payload["model"] == "primary":
                self.reply(429, {})
                return
            if mode == "all_fail":
                self.reply(503, {})
                return
            if mode == "hold":
                assert state["release"].wait(5)
            body = {"choices": [{"message": {"content": "ok"}}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
                    "model": payload["model"]}
            if mode == "billable_bad" and payload["model"] == "primary":
                body["choices"] = []
            if mode == "wrong_model":
                body["model"] = "unrequested-model"
            if mode == "understated_reasoning":
                body["usage"] = {"prompt_tokens": 5, "completion_tokens": 0, "total_tokens": 5,
                                 "completion_tokens_details": {"reasoning_tokens": 6}}
            self.reply(200, body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = False
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    state["base"] = f"http://127.0.0.1:{server.server_port}/v1"
    try:
        yield state
    finally:
        state["stop"].set()
        state["release"].set()
        server.shutdown()
        server.server_close()
        thread.join(3)
        assert not thread.is_alive()


def router(state, **kw):
    return MeliousModelRouter(models=("primary", "backup"), base_url=state["base"],
                              max_retries=0, **kw)


def test_billable_rejected_attempt_blocks_unaffordable_fallback(faults):
    faults["mode"] = "billable_bad"
    r = router(faults, spend_ceiling=10)
    with pytest.raises(SpendCeilingError):
        r.complete(MSG, max_tokens=4)
    assert faults["calls"] == ["primary"]
    assert r.spend.snapshot()["spend_committed"] == 8
    assert r.spend.snapshot()["spend_reserved"] == 0
    assert r.breakers["backup"].failures == 0


@pytest.mark.parametrize("mode", ["trickle", "headers"])
def test_slow_http_exchange_obeys_wall_deadline(faults, mode):
    faults["mode"] = mode
    r = router(faults, timeout=.15, total_timeout=.15)
    start = time.monotonic()
    with pytest.raises(RouterError):
        r.complete(MSG, max_tokens=4)
    assert time.monotonic() - start < .5
    assert faults["calls"] == ["primary"]
    assert r.spend.snapshot()["spend_reserved"] == 0


def test_cancellation_interrupts_http_without_fallback_and_releases_probe(faults):
    faults["mode"] = "trickle"
    r = router(faults, timeout=3, total_timeout=3, max_inflight=1)
    b = r.breakers["primary"]
    b.failures = b.failure_threshold
    b.opened_at = time.monotonic() - b.recovery_seconds - 1
    cancel = threading.Event()
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(r.complete, MSG, max_tokens=4, cancel_event=cancel)
        assert faults["entered"].wait(1)
        start = time.monotonic()
        cancel.set()
        with pytest.raises(RouterError, match="cancel"):
            future.result(timeout=1)
        assert time.monotonic() - start < .5
    assert faults["calls"] == ["primary"]
    assert not b.probing
    assert r.spend.snapshot()["spend_reserved"] == 0
    assert r._slots.acquire(blocking=False)
    r._slots.release()


@pytest.mark.parametrize("header", ["1e100", "999999999999999999999", formatdate(time.time()+100000, usegmt=True)])
def test_huge_retry_after_has_finite_policy_bound(faults, header):
    faults.update(mode="limited", retry=header)
    r = router(faults)
    assert r.complete(MSG, max_tokens=4)["router"]["selected_model"] == "backup"
    remaining = r._cooldown_until["primary"] - time.monotonic()
    assert 0 < remaining <= 3600
    r.complete(MSG, max_tokens=4)
    assert faults["calls"] == ["primary", "backup", "backup"]


def test_real_http_5xx_failover_and_circuit_recovery(faults):
    faults["mode"] = "failover"
    r = router(faults)
    b = r.breakers["primary"]
    b.failure_threshold = 1
    r.complete(MSG, max_tokens=4)
    r.complete(MSG, max_tokens=4)
    assert faults["calls"] == ["primary", "backup", "backup"]
    faults["mode"] = "ok"
    b.opened_at -= b.recovery_seconds + 1
    assert r.complete(MSG, max_tokens=4)["router"]["selected_model"] == "primary"
    assert b.state == "CLOSED" and not b.probing


def test_full_formatted_exception_chain_is_redacted():
    def transport(*args):
        raise RuntimeError("secret-sentinel-from-transport")
    r = MeliousModelRouter(models=("primary",), transport=transport, max_retries=0)
    with pytest.raises(RouterError) as caught:
        r.complete(MSG, max_tokens=4)
    assert "secret-sentinel-from-transport" not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("catalog", [None, {"data": []}, {"data": [{"id": "primary"}]},
    {"data": [{"id": "primary"}, {"id": "primary"}]}, {"data": [{"id": 7}]},
    {"data": [{"id": "primary\nmetric-injection"}]}])
def test_model_catalog_validation_fails_closed(faults, catalog):
    faults["catalog"] = catalog
    with pytest.raises(RouterError):
        router(faults).validate_models()
    assert faults["calls"] == ["GET models"]


def test_catalog_validation_is_explicit_not_alias_verification(faults):
    r = router(faults)
    assert faults["calls"] == []
    assert r.validate_models() == ("primary", "backup")
    assert faults["calls"] == ["GET models"]


def test_reported_model_mismatch_rejected_but_usage_charged(faults):
    faults["mode"] = "wrong_model"
    r = router(faults)
    with pytest.raises(RouterError):
        r.complete(MSG, max_tokens=4)
    assert r.spend.snapshot()["spend_committed"] == 16


@pytest.mark.parametrize("models", [(), "primary", ("primary", "primary"), ("primary\nmetric",), (7,)])
def test_model_configuration_rejects_invalid_identifiers(models):
    with pytest.raises(RouterError):
        MeliousModelRouter(models=models)


def test_pre_cancelled_request_has_no_socket_or_spend(faults):
    cancel = threading.Event()
    cancel.set()
    r = router(faults, max_inflight=1)
    with pytest.raises(RouterError, match="cancel"):
        r.complete(MSG, max_tokens=4, cancel_event=cancel)
    assert faults["calls"] == []
    assert r.get_metrics()["spend_reserved"] == 0


def test_tools_are_included_in_admission_estimate(faults):
    r = router(faults, spend_ceiling=20)
    with pytest.raises(SpendCeilingError):
        r.complete(MSG, max_tokens=4, tools=[{"type": "function", "function": {
            "name": "local", "description": "x"*300, "parameters": {"type": "object"}}}])
    assert faults["calls"] == []


def test_invalid_payload_does_not_mask_validation_with_spend_refusal(faults):
    r = router(faults, spend_ceiling=1)
    with pytest.raises(RouterError, match="completion budget"):
        r.complete(MSG, max_tokens=True)
    assert r.spend.snapshot()["spend_refused"] == 0
    assert faults["calls"] == []


def test_model_field_is_part_of_wire_byte_limit(faults):
    r = router(faults)
    r.MAX_REQUEST_BYTES = len(json.dumps({"messages": MSG, "max_tokens": 4}).encode())
    with pytest.raises(RouterError, match="byte budget"):
        r.complete(MSG, max_tokens=4)
    assert faults["calls"] == []


def test_initial_lock_wait_consumes_total_deadline(faults):
    r = router(faults, total_timeout=.1, acquire_timeout=2)
    with r._lock, ThreadPoolExecutor(1) as pool:
        start = time.monotonic()
        future = pool.submit(r.complete, MSG, max_tokens=4)
        with pytest.raises(RouterError):
            future.result(timeout=.5)
        assert time.monotonic() - start < .5
    assert faults["calls"] == []
    assert r.spend.snapshot()["spend_reserved"] == 0


def test_cancellation_interrupts_state_lock_wait(faults):
    r = router(faults, total_timeout=3, acquire_timeout=2)
    cancel = threading.Event()
    reserved = threading.Event()
    reserve = r.spend.reserve

    def signal_reservation(tokens):
        result = reserve(tokens)
        reserved.set()
        return result

    r.spend.reserve = signal_reservation
    with r._lock, ThreadPoolExecutor(1) as pool:
        future = pool.submit(r.complete, MSG, max_tokens=4, cancel_event=cancel)
        assert reserved.wait(1)
        cancel.set()
        with pytest.raises(RouterError, match="cancel"):
            future.result(timeout=.5)
    assert faults["calls"] == []
    assert r.spend.snapshot()["spend_reserved"] == 0


def test_last_route_retry_has_separate_durable_attempts(faults, tmp_path):
    from kernel.sidecar.melious_router import DurableSpendLedger
    import sqlite3
    faults["mode"] = "all_fail"
    ledger = DurableSpendLedger(str(tmp_path / "gateway.sqlite"), ceiling=100)
    r = MeliousModelRouter(models=("primary",), base_url=faults["base"], max_retries=1,
                          spend=ledger)
    with pytest.raises(RouterError):
        r.complete(MSG, max_tokens=4)
    assert faults["calls"] == ["primary", "primary"]
    with contextlib.closing(sqlite3.connect(ledger.path)) as conn:
        assert conn.execute("SELECT count(*) FROM spend_attempts WHERE state='settled'").fetchone()[0] == 2
    assert ledger.snapshot()["spend_reserved"] == 0


def test_malformed_retry_after_defaults_to_short_route_cooldown(faults):
    faults.update(mode="limited", retry="NaN")
    r = router(faults)
    r.complete(MSG, max_tokens=4)
    r.complete(MSG, max_tokens=4)
    assert faults["calls"] == ["primary", "backup", "backup"]
    assert 0 < r._cooldown_until["primary"] - time.monotonic() <= 1


def test_response_byte_limit_fails_closed(faults):
    r = router(faults)
    r.MAX_RESPONSE_BYTES = 8
    with pytest.raises(RouterError):
        r.complete(MSG, max_tokens=4)
    assert r.spend.snapshot()["spend_reserved"] == 0


def test_injected_status_string_cannot_leak_into_trace_or_chain():
    def transport(*args):
        exc = RuntimeError("transport-secret")
        exc.status = "secret-status-string"
        raise exc
    r = MeliousModelRouter(models=("primary",), transport=transport, max_retries=0)
    with pytest.raises(RouterError) as caught:
        r.complete(MSG, max_tokens=4)
    assert "secret-status-string" not in "".join(traceback.format_exception(caught.value))
    assert not hasattr(caught.value, "status")


def test_actual_http_100_callers_admit_one_half_open_probe(faults):
    from collections import Counter
    faults["mode"] = "hold"
    r = router(faults, max_inflight=100, total_timeout=5, probe_timeout=5)
    # Disable fallback solely for this single-route recovery concurrency oracle.
    r.models = ("primary",)
    breaker = r.breakers["primary"]
    breaker.failures = breaker.failure_threshold
    breaker.opened_at = time.monotonic() - breaker.recovery_seconds - 1
    start = threading.Barrier(100)
    decisions = threading.Barrier(100)

    def call(_):
        start.wait(timeout=5)
        try:
            r.complete(MSG, max_tokens=4)
            return "success"
        except RouterError as exc:
            assert "circuit_open" in str(exc)
            assert faults["entered"].wait(2)
            # All other callers decide before the network probe is released.
            if decisions.wait(timeout=5) == 0:
                faults["release"].set()
            return "refused"

    with ThreadPoolExecutor(100) as pool:
        futures = [pool.submit(call, i) for i in range(100)]
        # Main thread substitutes for the sole HTTP caller at the decision barrier.
        assert faults["entered"].wait(2)
        decisions.wait(timeout=5)
        faults["release"].set()
        outcomes = Counter(f.result(timeout=5) for f in futures)
    assert outcomes == {"success": 1, "refused": 99}
    assert faults["calls"] == ["primary"]
    assert breaker.state == "CLOSED" and not breaker.probing
    assert r.spend.snapshot()["spend_reserved"] == 0
    assert all(r._slots.acquire(False) for _ in range(100))
    assert not r._slots.acquire(False)
    for _ in range(100):
        r._slots.release()


def test_cancelled_native_completion_keeps_slot_until_socket_closes(faults):
    faults["mode"] = "hold"
    r = router(faults, max_inflight=1)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(r.complete, MSG, max_tokens=4)
        try:
            assert faults["entered"].wait(1)
            assert not future.cancel(), "running sync HTTP cannot be future-cancelled"
            with pytest.raises(RouterError, match="inflight"):
                r.complete(MSG, max_tokens=4)
        finally:
            faults["release"].set()
        assert future.result(timeout=2)["router"]["selected_model"] == "primary"
    assert r.spend.snapshot()["spend_reserved"] == 0
    assert r._slots.acquire(False)
    r._slots.release()


def test_per_route_timeout_leaves_budget_for_real_http_fallback(faults):
    r = router(faults, timeout=1, total_timeout=.5)
    r.model_timeouts["primary"] = .08
    faults["mode"] = "trickle"
    # A wrapper chooses fault mode only; the transport is still real HTTP.
    native = r._transport
    def transport(model, payload, timeout):
        faults["mode"] = "trickle" if model == "primary" else "ok"
        return native(model, payload, timeout)
    r._transport = transport
    start = time.monotonic()
    result = r.complete(MSG, max_tokens=4)
    assert result["router"]["selected_model"] == "backup"
    assert faults["calls"] == ["primary", "backup"]
    assert time.monotonic() - start < .5


def test_catalog_uses_same_response_limit_and_returns_permit(faults):
    r = router(faults, max_inflight=1)
    r.MAX_RESPONSE_BYTES = 8
    with pytest.raises(RouterError):
        r.validate_models()
    assert r._slots.acquire(False)
    r._slots.release()


def test_cancellation_chain_does_not_reveal_injected_transport_error():
    cancel = threading.Event()
    def transport(*args):
        cancel.set()
        raise RuntimeError("exception-chain-sensitive-sentinel")
    r = MeliousModelRouter(models=("primary",), max_retries=0, transport=transport)
    with pytest.raises(RouterError, match="cancel") as caught:
        r.complete(MSG, max_tokens=4, cancel_event=cancel)
    assert "exception-chain-sensitive-sentinel" not in "".join(traceback.format_exception(caught.value))


def test_half_open_never_increases_configured_route_timeout(faults):
    r = router(faults, timeout=.1, total_timeout=1)
    b = r.breakers["primary"]
    b.failures = b.failure_threshold
    b.opened_at = time.monotonic() - b.recovery_seconds - 1
    native = r._transport
    seen = []
    def transport(model, payload, timeout):
        seen.append(timeout)
        return native(model, payload, timeout)
    r._transport = transport
    r.complete(MSG, max_tokens=4)
    assert seen == [.1]


def test_reported_reasoning_cannot_evade_completion_or_total_budget(faults):
    faults["mode"] = "understated_reasoning"
    r = router(faults)
    with pytest.raises(RouterError):
        r.complete(MSG, max_tokens=4)
    # Reasoning is a subset of completion; underreported completion and total
    # counts must not silently erase an explicitly reported billable lower bound.
    assert r.get_metrics()["completion_tokens"] == 12
    assert r.spend.snapshot()["spend_committed"] == 22
