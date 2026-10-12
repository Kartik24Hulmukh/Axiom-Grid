"""Diagnostic-only wrapper for the unchanged launch_torture CLI.

Usage: python scripts/diagnose_launch_transport.py --output /data/tcp.json [...]
Writes a separate tcp.transport.json; original evidence and exit status are
untouched. No retries, transport replacement, request bodies or exception text.
Tracing adds overhead: this is attribution evidence, not an untraced benchmark.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import inspect
import json
from pathlib import Path
import runpy
import sys
import time
from urllib.parse import urlsplit

import httpx

MAX_EVENTS = 128
MAX_REPORT_BYTES = 2 * 1024 * 1024
MAX_GROUPS = 64
MAX_DETAILS = 512
MAX_TRANSPORT_DETAILS = 64
_ENDPOINTS = frozenset({"/", "/healthz", "/livez", "/readyz", "/metrics",
                       "/demo", "/apply", "/correct", "/api/extract-document",
                       "/api/ask-document", "/api/graph/query"})
_TRACE_OPERATIONS = frozenset({
    "connection.connect_tcp", "connection.connect_unix_socket",
    "connection.start_tls", "connection.close", "http11.send_request_headers",
    "http11.send_request_body", "http11.receive_response_headers",
    "http11.receive_response_body", "http11.response_closed",
    "http2.send_connection_init", "http2.send_request_headers",
    "http2.send_request_body", "http2.receive_response_headers",
    "http2.receive_response_body", "http2.response_closed",
})


def endpoint(url):
    """Never persist arbitrary path components, host, query or fragment."""
    try:
        path = url.path if isinstance(url, httpx.URL) else urlsplit(str(url)).path
    except (TypeError, ValueError):
        return "other"
    if path in _ENDPOINTS:
        return path
    if path.startswith("/api/source/"):
        return "/api/source/{doc_id}"
    return "other"


def exception_types(exc):
    def name(value):
        if value is None:
            return None
        cls = type(value)
        # Class identifiers only; never repr(), str(), args or traceback.
        return f"{cls.__module__}.{cls.__qualname__}"[:160]
    return {"exception_type": name(exc), "cause_type": name(exc.__cause__)}


class Diagnostics:
    def __init__(self, *, clock=time.perf_counter, max_report_bytes=MAX_REPORT_BYTES):
        if max_report_bytes < 16384:
            raise ValueError("report budget must be at least 16384 bytes")
        self.clock = clock
        self.max_report_bytes = min(max_report_bytes, MAX_REPORT_BYTES)
        # Smaller test/report budgets also bound aggregate cardinality; otherwise
        # aggregates alone could exceed a tiny cap after all details are evicted.
        self.max_groups = min(MAX_GROUPS, self.max_report_bytes // 1024)
        self.groups = {}
        self.exceptions = Counter()
        self.ordinary_details = []
        self.transport_details = []
        self.ordinary_bytes = self.transport_bytes = 0
        self.requests = self.details_dropped = self.events_dropped = 0
        self.transport_details_dropped = 0

    @property
    def details(self):
        # Stable external shape, priority first so hard-cap trimming drops the
        # tail of ordinary details before any transport exception trace.
        return self.transport_details + self.ordinary_details

    def finish(self, record):
        self.requests += 1
        key = (record["endpoint"], record["status"])
        if key not in self.groups and len(self.groups) >= self.max_groups:
            key = ("other", "overflow")
        group = self.groups.setdefault(key, {"requests": 0, "elapsed_ms_total": 0,
                                            "elapsed_ms_max": 0, "failed": 0,
                                            "slow_over_200ms": 0})
        group["requests"] += 1
        group["elapsed_ms_total"] += record["elapsed_ms"]
        group["elapsed_ms_max"] = max(group["elapsed_ms_max"], record["elapsed_ms"])
        group["failed"] += record["status"] == 0 or record["status"] >= 400
        group["slow_over_200ms"] += record["elapsed_ms"] > 200
        self.events_dropped += record["trace_events_dropped"]
        if record.get("exception_type"):
            pair = (record["exception_type"], record["cause_type"])
            if pair not in self.exceptions and len(self.exceptions) >= self.max_groups:
                pair = ("overflow", None)
            self.exceptions[pair] += 1
        if record["status"] == 0 or record["status"] >= 400 or record["elapsed_ms"] > 200:
            size = len(json.dumps(record, separators=(",", ":"), ensure_ascii=True).encode())
            size += 1  # include the separating comma in the memory budget
            if record["status"] == 0:
                # Independent count/byte reservation cannot be consumed by the
                # hostile phase's expected 4xx responses or ordinary slow calls.
                if (len(self.transport_details) < MAX_TRANSPORT_DETAILS
                        and self.transport_bytes + size <= self.max_report_bytes // 2):
                    self.transport_details.append(record)
                    self.transport_bytes += size
                else:
                    self.details_dropped += 1
                    self.transport_details_dropped += 1
            elif (len(self.ordinary_details) < MAX_DETAILS
                    and self.ordinary_bytes + size <= self.max_report_bytes // 4):
                self.ordinary_details.append(record)
                self.ordinary_bytes += size
            else:
                self.details_dropped += 1

    def report(self):
        return {"scope": "diagnostic-only; unchanged producer, no retries; tracing overhead",
                "requests": self.requests, "max_events_per_request": MAX_EVENTS,
                "max_report_bytes": self.max_report_bytes,
                "details_dropped": self.details_dropped,
                "transport_details_dropped": self.transport_details_dropped,
                "max_transport_details": MAX_TRANSPORT_DETAILS,
                "trace_events_dropped": self.events_dropped,
                "aggregates": [{"endpoint": key[0], "status": key[1], **value}
                               for key, value in sorted(self.groups.items(), key=lambda item: str(item[0]))],
                "exception_counts": [{"exception_type": pair[0], "cause_type": pair[1], "requests": count}
                                     for pair, count in self.exceptions.items()],
                "failed_or_slow_requests": self.details}

    def write(self, path):
        report = self.report()
        # Defensive final hard cap, with honest truncation accounting.
        while True:
            encoded = json.dumps(report, separators=(",", ":"), ensure_ascii=True).encode()
            if len(encoded) <= self.max_report_bytes:
                break
            if not report["failed_or_slow_requests"]:
                raise ValueError("aggregate report exceeds diagnostic budget")
            removed = report["failed_or_slow_requests"].pop()
            report["details_dropped"] += 1
            if removed["status"] == 0:
                report["transport_details_dropped"] += 1
        Path(path).write_bytes(encoded)


@contextmanager
def instrument_requests(diagnostics):
    original = httpx.AsyncClient.request

    async def traced(client, *args, **kwargs):
        url = args[1] if len(args) > 1 else kwargs.get("url", "")
        started = diagnostics.clock()
        record = {"endpoint": endpoint(url), "status": 0, "elapsed_ms": 0,
                  "trace_events": [], "trace_events_dropped": 0}
        # Copy only extensions; preserve all other method kwargs and objects.
        # Explicit extensions=None is supported; caller mappings are untouched.
        extensions = dict(kwargs.get("extensions") or {})
        previous_trace = extensions.get("trace")

        async def trace(name, info):
            operation, _, stage = name.rpartition(".")
            safe_name = name if operation in _TRACE_OPERATIONS and stage in {"started", "complete", "failed"} else "other"
            if len(record["trace_events"]) < MAX_EVENTS:
                event = {"event": safe_name,
                         "elapsed_ms": (diagnostics.clock() - started) * 1000}
                exc = info.get("exception") if stage == "failed" else None
                if isinstance(exc, BaseException):
                    event.update(exception_types(exc))
                record["trace_events"].append(event)
            else:
                record["trace_events_dropped"] += 1
            if previous_trace is not None:
                result = previous_trace(name, info)
                if not inspect.iscoroutine(result):
                    # Match httpcore's async trace-extension contract exactly.
                    raise TypeError(
                        "If you're using an asynchronous interface, "
                        "the callback of the `trace` extension should "
                        "be an asynchronous function rather than a normal function."
                    )
                await result

        extensions["trace"] = trace
        forwarded = {**kwargs, "extensions": extensions}
        try:
            response = await original(client, *args, **forwarded)
            record["status"] = response.status_code
            return response
        except BaseException as exc:
            record.update(exception_types(exc))
            raise  # same object/type/cause; original producer owns status-0 handling
        finally:
            record["elapsed_ms"] = (diagnostics.clock() - started) * 1000
            diagnostics.finish(record)

    httpx.AsyncClient.request = traced
    try:
        yield
    finally:
        httpx.AsyncClient.request = original


def main():
    # Pass the original argv unchanged; no additional wrapper CLI switches.
    args = sys.argv[1:]
    output = None
    for index, arg in enumerate(args):
        if arg == "--output" and index + 1 < len(args):
            output = args[index + 1]
        elif arg.startswith("--output="):
            output = arg.partition("=")[2]
    diagnostics = Diagnostics()
    try:
        with instrument_requests(diagnostics):
            runpy.run_path(str(Path(__file__).with_name("launch_torture.py")), run_name="__main__")
    finally:
        if output is not None:
            # Never overwrite or rewrite the original producer's evidence.
            try:
                diagnostics.write(Path(output).with_suffix(".transport.json"))
            except OSError:
                # Do not mask the producer's SystemExit/gate result with I/O errors.
                print("Diagnostic sidecar write failed (OSError)", file=sys.stderr)


if __name__ == "__main__":
    main()
