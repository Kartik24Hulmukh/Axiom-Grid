"""Worker trace propagation and conservative native-parser ownership."""
import threading

import pytest
from overlay import server


@pytest.mark.asyncio
async def test_worker_inherits_request_context_without_leaking(monkeypatch):
    from contextvars import ContextVar
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider

    request_id = ContextVar("test_request_id", default=None)
    original = server.OrchestratorImpl.run
    observed = []
    def observe(self, doc):
        observed.append((request_id.get(), trace.get_current_span().get_span_context().trace_id))
        return original(self, doc)
    monkeypatch.setattr(server.OrchestratorImpl, "run", observe)
    provider = TracerProvider()
    try:
        async with server.app.router.lifespan_context(server.app):
            with provider.get_tracer(__name__).start_as_current_span("request") as span:
                token = request_id.set("request-123")
                try:
                    await server.extract_document(server.ExtractDocumentRequest(file="sample_memo_01.txt"))
                finally:
                    request_id.reset(token)
            await server.extract_document(server.ExtractDocumentRequest(file="sample_memo_01.txt"))
        assert observed == [("request-123", span.get_span_context().trace_id), (None, 0)]
    finally:
        provider.shutdown()


@pytest.mark.asyncio
async def test_optional_native_engines_keep_serialization(monkeypatch, tmp_path):
    from kernel.core.data_model import Trace
    entered = threading.Event()
    class Guard:
        def __enter__(self):
            entered.set()
        def __exit__(self, *args):
            entered.clear()
    def native_run(self, doc):
        assert entered.is_set(), "native parser executed without guard"
        return Trace(stages=())
    def native_ingest(self, path):
        assert entered.is_set(), "classification parser executed without guard"
        return [], None, []
    monkeypatch.setattr(server.IngestorImpl, "ingest", native_ingest)
    monkeypatch.setattr(server, "orchestrator_lock", Guard())
    monkeypatch.setattr(server.OrchestratorImpl, "run", native_run)
    path = tmp_path / "guard.pdf"
    path.write_bytes(b"%PDF-1.4")
    async with server.app.router.lifespan_context(server.app):
        await server.extract_document(server.ExtractDocumentRequest(file=str(path)))
    assert not entered.is_set()
