"""Real SDK in-memory export verifies telemetry without network egress."""
import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_spans_and_logs_do_not_capture_query_or_headers(monkeypatch):
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    from overlay.server import JsonLogFormatter
    from overlay.telemetry import install_tracing
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(trace, "get_tracer", provider.get_tracer)
    monkeypatch.setenv("AXIOM_OTEL_ENABLED", "1")
    app = FastAPI()
    logs = []
    @app.get("/items/{item_id}")
    def item(item_id: str):
        logs.append(json.loads(JsonLogFormatter().format(logging.LogRecord("test", 20, "", 0, "safe", (), None))))
        return {"ok": True}
    install_tracing(app)
    try:
        with TestClient(app) as client:
            assert client.get("/items/PRIVATE?token=SECRET", headers={"Authorization": "Bearer SECRET"}).status_code == 200
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.name == "GET /items/{item_id}"
        assert span.attributes["http.response.status_code"] == 200
        assert "PRIVATE" not in str(span.attributes) and "SECRET" not in str(span.attributes)
        assert logs[0]["trace_id"] == format(span.context.trace_id, "032x")
    finally:
        provider.shutdown()
