"""Offline diagnostic tests only: no server, subprocess, sockets or workload."""
import asyncio
import hashlib
import json
from pathlib import Path
import sys

import httpcore
import httpx
import pytest

from scripts import diagnose_launch_transport as diag


def test_forwards_kwargs_none_extensions_and_returns_same_response(monkeypatch):
    calls = []
    response = httpx.Response(422)
    payload = b"secret body"
    headers = {"Authorization": "secret"}

    async def original(client, *args, **kwargs):
        calls.append((args, kwargs))
        await kwargs["extensions"]["trace"]("http11.receive_response_headers.complete", {"return_value": "secret"})
        return response

    monkeypatch.setattr(httpx.AsyncClient, "request", original)
    d = diag.Diagnostics()
    async def exercise():
        with diag.instrument_requests(d):
            result = await httpx.AsyncClient.request(object(), "POST", "/correct", content=payload,
                headers=headers, extensions=None, timeout=None, follow_redirects=False)
        assert result is response
    asyncio.run(exercise())
    assert httpx.AsyncClient.request is original
    args, kwargs = calls[0]
    assert args == ("POST", "/correct")
    assert kwargs["content"] is payload and kwargs["headers"] is headers
    assert kwargs["timeout"] is None and kwargs["follow_redirects"] is False
    assert len(calls) == 1
    assert d.details[0]["status"] == 422
    assert "secret" not in json.dumps(d.report())


def test_custom_trace_extensions_not_mutated_and_exact_exception(monkeypatch):
    seen = []
    def callback(name, info):
        seen.append((name, info))
    async def async_callback(name, info):
        callback(name, info)
    extensions = {"trace": async_callback, "custom": object()}
    cause = httpcore.ReadError("secret cause")
    error = httpx.ReadError("secret exception")
    error.__cause__ = cause
    info = {"exception": cause, "request": "secret request", "return_value": "secret"}
    async def original(client, *args, **kwargs):
        assert kwargs["extensions"]["custom"] is extensions["custom"]
        await kwargs["extensions"]["trace"]("http11.receive_response_headers.failed", info)
        raise error
    monkeypatch.setattr(httpx.AsyncClient, "request", original)
    d = diag.Diagnostics()
    async def exercise():
        with diag.instrument_requests(d):
            with pytest.raises(httpx.ReadError) as caught:
                await httpx.AsyncClient.request(object(), method="GET", url="http://user:secret@localhost/api/source/secret?token=secret", extensions=extensions)
            assert caught.value is error and caught.value.__cause__ is cause
    asyncio.run(exercise())
    assert seen == [("http11.receive_response_headers.failed", info)]
    assert extensions["trace"] is (async_callback)
    assert d.details[0]["endpoint"] == "/api/source/{doc_id}"
    assert d.details[0]["status"] == 0
    assert d.details[0]["exception_type"] == "httpx.ReadError"
    assert d.details[0]["cause_type"] == "httpcore.ReadError"
    assert d.details[0]["trace_events"][0]["exception_type"] == "httpcore.ReadError"
    assert "secret" not in json.dumps(d.report())


def test_event_detail_and_report_caps_and_fast_aggregate_only(monkeypatch, tmp_path):
    async def original(client, *args, **kwargs):
        for _ in range(140):
            await kwargs["extensions"]["trace"]("secret.event.failed", {"body": "secret"})
        return httpx.Response(404)
    monkeypatch.setattr(httpx.AsyncClient, "request", original)
    d = diag.Diagnostics(max_report_bytes=16384)
    async def exercise():
        with diag.instrument_requests(d):
            for _ in range(20):
                await httpx.AsyncClient.request(object(), "GET", "/secret")
    asyncio.run(exercise())
    assert d.requests == 20 and d.events_dropped == 20 * 12
    assert d.details_dropped > 0
    assert all(len(r["trace_events"]) == 128 for r in d.details)
    target = tmp_path / "trace.json"
    d.write(target)
    assert target.stat().st_size <= 16384
    assert "secret" not in target.read_text()
    fast = {"endpoint": "/healthz", "status": 200, "elapsed_ms": 200,
            "trace_events": [], "trace_events_dropped": 0}
    d.finish(fast)
    assert not any(r["status"] == 200 for r in d.details)
    d.finish({**fast, "elapsed_ms": 200.001})
    assert d.groups[("/healthz", 200)]["slow_over_200ms"] == 1


def test_cancellation_and_custom_trace_error_propagate(monkeypatch):
    error = asyncio.CancelledError()
    async def original(client, *args, **kwargs):
        raise error
    monkeypatch.setattr(httpx.AsyncClient, "request", original)
    d = diag.Diagnostics()
    async def exercise():
        with diag.instrument_requests(d):
            with pytest.raises(asyncio.CancelledError) as caught:
                await httpx.AsyncClient.request(object(), "GET", "/healthz")
            assert caught.value is error
    asyncio.run(exercise())
    assert d.details[0]["status"] == 0

    sentinel = RuntimeError("secret")
    def callback(name, info):
        raise sentinel
    async def emitting(client, *args, **kwargs):
        await kwargs["extensions"]["trace"]("connection.connect_tcp.started", {})
    monkeypatch.setattr(httpx.AsyncClient, "request", emitting)
    async def exercise_callback():
        with diag.instrument_requests(d):
            with pytest.raises(RuntimeError) as caught:
                await httpx.AsyncClient.request(object(), "GET", "/healthz", extensions={"trace": callback})
            assert caught.value is sentinel
    asyncio.run(exercise_callback())


@pytest.mark.parametrize("exit_code", [0, 1])
def test_runpy_original_cli_status_and_evidence_preserved(monkeypatch, tmp_path, exit_code):
    original = Path(diag.__file__).with_name("launch_torture.py")
    before = hashlib.sha256(original.read_bytes()).digest()
    output = tmp_path / "original.json"
    argv = ["diagnose_launch_transport.py", "--output", str(output), "--concurrency", "100"]
    gates = {"strict_gates": {"no_status_mismatches": False, "loaded_error_max_below_200ms": False},
             "phases": [{"statuses": {"0": 3}}], "passed_requested_bounds": False}
    def fake_run(path, run_name):
        assert Path(path) == original and run_name == "__main__"
        assert sys.argv == argv
        output.write_text(json.dumps(gates))
        raise SystemExit(exit_code)
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(diag.runpy, "run_path", fake_run)
    request = httpx.AsyncClient.request
    with pytest.raises(SystemExit) as caught:
        diag.main()
    assert caught.value.code == exit_code
    assert httpx.AsyncClient.request is request
    assert json.loads(output.read_text()) == gates
    assert output.with_suffix(".transport.json").exists()
    assert hashlib.sha256(original.read_bytes()).digest() == before


def test_sync_custom_trace_retains_httpcore_type_error(monkeypatch):
    def callback(name, info):
        return None
    async def original(client, *args, **kwargs):
        await kwargs["extensions"]["trace"]("connection.connect_tcp.started", {})
    monkeypatch.setattr(httpx.AsyncClient, "request", original)
    d = diag.Diagnostics()
    async def exercise():
        with diag.instrument_requests(d):
            with pytest.raises(TypeError, match="asynchronous function"):
                await httpx.AsyncClient.request(object(), "GET", "/healthz", extensions={"trace": callback})
    asyncio.run(exercise())
    assert d.details[0]["exception_type"] == "builtins.TypeError"


def test_group_cardinality_bounded_and_omitted_extensions(monkeypatch):
    async def original(client, *args, **kwargs):
        assert callable(kwargs["extensions"]["trace"])
        return httpx.Response(200)
    monkeypatch.setattr(httpx.AsyncClient, "request", original)
    d = diag.Diagnostics()
    async def exercise():
        with diag.instrument_requests(d):
            await httpx.AsyncClient.request(object(), "GET", "/healthz")
    asyncio.run(exercise())
    assert d.requests == 1 and not d.details
    for status in range(100, 250):
        d.finish({"endpoint": "other", "status": status, "elapsed_ms": 1,
                  "trace_events": [], "trace_events_dropped": 0})
    assert len(d.groups) <= diag.MAX_GROUPS + 1


@pytest.mark.parametrize("budget", [diag.MAX_REPORT_BYTES, 16384])
def test_late_transport_trace_reserved_after_ordinary_overflow(tmp_path, budget):
    d = diag.Diagnostics(max_report_bytes=budget)
    ordinary = {"endpoint": "/correct", "status": 404, "elapsed_ms": 1,
                "trace_events": [], "trace_events_dropped": 0}
    for _ in range(diag.MAX_DETAILS + 100):
        d.finish(dict(ordinary))
    trace = [{"event": "http11.receive_response_headers.failed", "elapsed_ms": 220,
              "exception_type": "httpcore.ReadError", "cause_type": "builtins.OSError"}]
    failure = {"endpoint": "/api/source/{doc_id}", "status": 0, "elapsed_ms": 221,
               "exception_type": "httpx.ReadError", "cause_type": "httpcore.ReadError",
               "trace_events": trace, "trace_events_dropped": 0}
    d.finish(failure)
    output = tmp_path / "reserved.json"
    d.write(output)
    report = json.loads(output.read_bytes())
    assert output.stat().st_size <= budget
    assert report["failed_or_slow_requests"][0] == failure
    assert report["transport_details_dropped"] == 0
    assert report["details_dropped"] > 0
    assert report["exception_counts"] == [{"exception_type": "httpx.ReadError",
                                           "cause_type": "httpcore.ReadError", "requests": 1}]
    assert sum(g["requests"] for g in report["aggregates"]) == diag.MAX_DETAILS + 101


def test_priority_saturation_and_truncation_honest(tmp_path):
    d = diag.Diagnostics()
    failure = {"endpoint": "/healthz", "status": 0, "elapsed_ms": 1,
               "exception_type": "httpx.ReadError", "cause_type": "httpcore.ReadError",
               "trace_events": [], "trace_events_dropped": 0}
    for _ in range(diag.MAX_TRANSPORT_DETAILS + 3):
        d.finish(dict(failure))
    output = tmp_path / "bounded.json"
    d.write(output)
    report = json.loads(output.read_bytes())
    assert len(report["failed_or_slow_requests"]) == diag.MAX_TRANSPORT_DETAILS
    assert report["transport_details_dropped"] == report["details_dropped"] == 3
    assert report["exception_counts"][0]["requests"] == diag.MAX_TRANSPORT_DETAILS + 3


def test_defensive_cap_evicts_ordinary_before_priority(tmp_path):
    d = diag.Diagnostics(max_report_bytes=16384)
    ordinary = {"endpoint": "/correct", "status": 404, "elapsed_ms": 1,
                "trace_events": [], "trace_events_dropped": 0}
    for _ in range(diag.MAX_DETAILS + 1):
        d.finish(dict(ordinary))
    failure = {"endpoint": "/healthz", "status": 0, "elapsed_ms": 201,
               "exception_type": "httpx.ReadError", "cause_type": "httpcore.ReadError",
               "trace_events": [{"event": "connection.connect_tcp.failed", "elapsed_ms": 200}],
               "trace_events_dropped": 0}
    d.finish(failure)
    # Force defensive trimming independent of admission byte reservations.
    # Aggregates stay intact; transport remains while ordinary details shrink.
    report = d.report()
    report["aggregates"].append({"padding": "x" * 13000})
    d.report = lambda: report
    output = tmp_path / "trimmed.json"
    d.write(output)
    written = json.loads(output.read_bytes())
    assert output.stat().st_size <= 16384
    assert written["failed_or_slow_requests"][0] == failure
    assert written["transport_details_dropped"] == 0
    assert len(written["failed_or_slow_requests"]) < len(d.details)
    assert written["details_dropped"] > d.details_dropped


def test_tiny_cap_aggregates_bounded_without_losing_counts(tmp_path):
    d = diag.Diagnostics(max_report_bytes=16384)
    for i in range(100):
        d.finish({"endpoint": "other", "status": 400 + i, "elapsed_ms": 1,
                  "exception_type": f"httpx.Failure{i}", "cause_type": "httpcore.ReadError",
                  "trace_events": [], "trace_events_dropped": 0})
    output = tmp_path / "aggregates.json"
    d.write(output)
    report = json.loads(output.read_bytes())
    assert output.stat().st_size <= 16384
    assert sum(g["requests"] for g in report["aggregates"]) == 100
    assert sum(g["requests"] for g in report["exception_counts"]) == 100
