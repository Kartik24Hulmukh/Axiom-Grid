"""Tracing-enabled production path: pure ASGI and real loopback OTLP wire."""
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from overlay.telemetry import TracingMiddleware, install_tracing


@pytest.fixture
def telemetry(monkeypatch):
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(trace, "get_tracer", provider.get_tracer)
    monkeypatch.setenv("AXIOM_OTEL_ENABLED", "1")
    try:
        yield provider, exporter
    finally:
        provider.shutdown()


def test_enabled_tracing_keeps_pure_asgi_topology_and_correlation(telemetry):
    app = FastAPI()

    @app.get("/private/{identifier}")
    async def handle(identifier: str):
        return {"ok": True}

    install_tracing(app)
    assert not any(issubclass(layer.cls, BaseHTTPMiddleware) for layer in app.user_middleware)
    with TestClient(app) as client:
        response = client.get("/private/SECRET?credential=SECRET", headers={
            "authorization": "Bearer SECRET", "baggage": "private=SECRET",
            "traceparent": "00-12345678901234567890123456789012-1234567890123456-01",
        })
    assert response.status_code == 200
    spans = telemetry[1].get_finished_spans()
    assert len(spans) == 1 and spans[0].name == "GET /private/{identifier}"
    assert "SECRET" not in str(spans[0].attributes)
    assert format(spans[0].context.trace_id, "032x") == "12345678901234567890123456789012"


@pytest.mark.asyncio
async def test_stream_and_private_exception_are_not_rewritten_or_exported(telemetry):
    messages = []
    body = [{"type": "http.request", "body": b"PRIVATE-BODY", "more_body": False}]

    async def receive():
        return body.pop()

    async def send(message):
        messages.append(message)

    async def downstream(scope, original_receive, original_send):
        assert original_receive is receive
        assert (await original_receive())["body"] == b"PRIVATE-BODY"
        await original_send({"type": "http.response.start", "status": 200, "headers": []})
        await original_send({"type": "http.response.body", "body": b"one", "more_body": True})
        await asyncio.sleep(0)  # yield is a streaming test stimulus, not production delay
        await original_send({"type": "http.response.body", "body": b"two", "more_body": False})
        raise RuntimeError("PRIVATE-EXCEPTION")

    scope = {"type": "http", "method": "GET", "headers": [], "path": "/sensitive-id"}
    with pytest.raises(RuntimeError, match="PRIVATE-EXCEPTION"):
        await TracingMiddleware(downstream)(scope, receive, send)
    assert [m.get("body") for m in messages[1:]] == [b"one", b"two"]
    span = telemetry[1].get_finished_spans()[0]
    assert span.status.status_code.name == "ERROR"
    assert not span.events and "PRIVATE" not in str(span.attributes)
    assert span.name == "GET unmatched"


def test_real_otlp_http_protobuf_export_to_loopback_receiver(monkeypatch):
    """Actual SDK/exporter wire test; this receiver is NOT a deployed collector."""
    pytest.importorskip("opentelemetry.exporter.otlp.proto.http.trace_exporter")
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
        ExportTraceServiceRequest,
    )
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    received = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = self.rfile.read(int(self.headers["Content-Length"]))
            decoded = ExportTraceServiceRequest()
            decoded.ParseFromString(payload)
            received.append((self.path, self.headers["Content-Type"], decoded))
            self.send_response(200)
            self.send_header("Content-Type", "application/x-protobuf")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    receiver = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    thread = threading.Thread(target=receiver.serve_forever)
    thread.start()
    provider = TracerProvider()
    # Explicit loopback endpoint/empty headers: no environment-configured exporter egress.
    exporter = OTLPSpanExporter(endpoint=f"http://127.0.0.1:{receiver.server_port}/v1/traces", headers={}, timeout=2)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(trace, "get_tracer", provider.get_tracer)
    monkeypatch.setenv("AXIOM_OTEL_ENABLED", "1")
    app = FastAPI()

    @app.get("/probe/{id}")
    async def probe(id: str):
        return {"ok": True}

    install_tracing(app)
    try:
        with TestClient(app) as client:
            assert client.get("/probe/PRIVATE?key=PRIVATE", headers={"Authorization": "Bearer PRIVATE"}).status_code == 200
        assert provider.force_flush(timeout_millis=2000)
        assert len(received) == 1
        path, content_type, decoded = received[0]
        assert path == "/v1/traces" and content_type == "application/x-protobuf"
        spans = [s for resource in decoded.resource_spans for scope in resource.scope_spans for s in scope.spans]
        assert len(spans) == 1 and spans[0].name == "GET /probe/{id}"
        assert "PRIVATE" not in str(decoded)
    finally:
        provider.shutdown()
        receiver.shutdown()
        receiver.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive()
