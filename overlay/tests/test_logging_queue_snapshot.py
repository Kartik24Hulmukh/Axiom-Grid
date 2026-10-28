"""JSON formatting runs on the listener; queued context is producer-local."""
import contextvars
import io
import json
import logging
import logging.handlers
import queue
import sys
import threading

import pytest

from overlay import server


def _record(msg="hello %s", args=("world",), exc_info=None):
    return logging.LogRecord("overlay.server", logging.WARNING, __file__, 1, msg, args, exc_info)


def test_json_formatting_runs_on_listener_not_prepare(monkeypatch):
    monkeypatch.setattr(server, "log_context", lambda: {})
    producer = threading.get_ident()
    calls = []

    class ObservedFormatter(server.JsonLogFormatter):
        def format(self, record):
            calls.append(threading.get_ident())
            return super().format(record)

    formatter = ObservedFormatter()
    output = io.StringIO()
    sink = logging.StreamHandler(output)
    sink.setFormatter(formatter)
    handler = server._NonBlockingQueueHandler(queue.Queue(maxsize=2))
    handler.setFormatter(formatter)  # Retained for existing direct-call users.
    original = _record()
    prepared = handler.prepare(original)
    assert calls == []
    assert prepared is not original
    assert prepared.msg == "hello world" and prepared.args is None
    assert original.msg == "hello %s" and original.args == ("world",)
    listener = logging.handlers.QueueListener(handler.queue, sink)
    listener.start()
    try:
        handler.enqueue(prepared)
        handler.queue.join()
    finally:
        listener.stop()
        handler.close()
        sink.close()
    assert len(calls) == 1 and calls[0] != producer
    assert json.loads(output.getvalue())["msg"] == "hello world"


def test_context_snapshot_survives_mutation_and_context_reset(monkeypatch):
    context = contextvars.ContextVar("queue_test_context", default={})
    reads = []

    def capture_context():
        reads.append(threading.get_ident())
        return context.get()

    monkeypatch.setattr(server, "log_context", capture_context)
    handler = server._NonBlockingQueueHandler(queue.Queue(maxsize=1))
    values = {"request_id": "request-before", "trace_id": "trace-before", "span_id": "span-before"}
    token = context.set(values)
    try:
        prepared = handler.prepare(_record())
        values["request_id"] = "request-after"
        values["span_id"] = "span-after"
    finally:
        context.reset(token)
    assert isinstance(prepared._queued_log_context, tuple)
    # This thread has no producer context; formatting must use the snapshot.
    docs = []
    thread = threading.Thread(target=lambda: docs.append(json.loads(server.JsonLogFormatter().format(prepared))))
    thread.start()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert docs[0]["request_id"] == "request-before"
    assert docs[0]["trace_id"] == "trace-before"
    assert docs[0]["span_id"] == "span-before"
    assert len(reads) == 1
    handler.close()


def test_empty_snapshot_does_not_read_listener_context(monkeypatch):
    monkeypatch.setattr(server, "log_context", lambda: {})
    handler = server._NonBlockingQueueHandler(queue.Queue(maxsize=1))
    prepared = handler.prepare(_record())
    monkeypatch.setattr(server, "log_context", lambda: {"trace_id": "listener-only"})
    doc = json.loads(server.JsonLogFormatter().format(prepared))
    assert "trace_id" not in doc
    handler.close()


def test_exception_type_survives_without_exception_or_traceback(monkeypatch):
    monkeypatch.setattr(server, "log_context", lambda: {})
    try:
        raise ValueError("SYNTHETIC_EXCEPTION_MESSAGE_DO_NOT_LOG")
    except ValueError:
        original = _record(exc_info=sys.exc_info())
    original.exc_text = "SYNTHETIC_CACHED_TRACEBACK_DO_NOT_LOG"
    original.stack_info = "SYNTHETIC_STACK_DO_NOT_LOG"
    handler = server._NonBlockingQueueHandler(queue.Queue(maxsize=1))
    handler.setFormatter(server.JsonLogFormatter())
    prepared = handler.prepare(original)
    assert prepared.exc_info is None and prepared.exc_text is None
    assert prepared.stack_info is None and prepared.args is None
    assert prepared._queued_exc_type == "ValueError"
    assert original.exc_info is not None and original.exc_text is not None
    doc = json.loads(server.JsonLogFormatter().format(prepared))
    assert doc["exc_type"] == "ValueError"
    assert "SYNTHETIC_" not in json.dumps(doc)
    # Direct formatter calls retain their original behavior as well.
    assert json.loads(handler.format(original))["exc_type"] == "ValueError"
    handler.close()


@pytest.mark.parametrize("level", [logging.INFO, logging.WARNING])
def test_queue_preserves_level_message_and_request_extras(monkeypatch, level):
    monkeypatch.setattr(server, "log_context", lambda: {"trace_id": "trace-producer"})
    handler = server._NonBlockingQueueHandler(queue.Queue(maxsize=1))
    original = _record()
    original.levelno = level
    original.levelname = logging.getLevelName(level)
    original.request_id = "request-extra"
    original.path = "/healthz"
    original.status = 200
    original.latency_ms = 1.25
    original.client = "synthetic-client"
    prepared = handler.prepare(original)
    doc = json.loads(server.JsonLogFormatter().format(prepared))
    assert doc["level"] == logging.getLevelName(level)
    assert doc["msg"] == "hello world"
    for field in ("request_id", "path", "status", "latency_ms", "client"):
        assert doc[field] == getattr(original, field)
    assert doc["trace_id"] == "trace-producer"
    assert doc["service"] == "axiom-grid-overlay" and doc["ts"].endswith("Z")
    handler.close()


def test_configured_sink_formats_json_and_configuration_is_idempotent(monkeypatch):
    root = logging.Logger("queue-config-test")
    loggers = {name: logging.Logger(name) for name in
               ("uvicorn", "uvicorn.error", "uvicorn.access", "httpx", "httpcore")}
    real_listener = logging.handlers.QueueListener
    listeners = []
    sinks = []

    def listener_factory(q, sink, **kwargs):
        listener = real_listener(q, sink, **kwargs)
        listeners.append(listener)
        sinks.append(sink)
        return listener

    monkeypatch.setenv("AXIOM_LOG_FORMAT", "json")
    monkeypatch.delenv("AXIOM_LOG_LEVEL", raising=False)
    monkeypatch.setenv("AXIOM_LOG_QUEUE_MAX", "3")
    monkeypatch.setattr(server.logging, "getLogger", lambda name=None: root if name is None else loggers[name])
    monkeypatch.setattr(server.logging.handlers, "QueueListener", listener_factory)
    try:
        server.configure_structured_logging()
        server.configure_structured_logging()
        assert len(root.handlers) == len(listeners) == 1
        handler = root.handlers[0]
        assert isinstance(handler.formatter, server.JsonLogFormatter)
        assert isinstance(sinks[0].formatter, server.JsonLogFormatter)
        assert handler.queue.maxsize == 3
        assert root.level == logging.INFO
        assert loggers["uvicorn.access"].level == logging.WARNING
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            assert loggers[name].handlers == [handler]
            assert loggers[name].propagate is False
    finally:
        for listener in listeners:
            listener.stop()
        for handler in root.handlers:
            handler.close()
        for sink in sinks:
            sink.close()


def test_saturated_queue_sheds_and_counts_without_waiting(monkeypatch):
    monkeypatch.setattr(server, "log_context", lambda: {})
    monkeypatch.setattr(server, "LOG_DROPPED_TOTAL", {"count": 0})
    handler = server._NonBlockingQueueHandler(queue.Queue(maxsize=1))
    handler.enqueue(_record("already full", None))
    handler.emit(_record("shed this", None))
    assert handler.queue.qsize() == 1
    assert handler.queue.get_nowait().msg == "already full"
    assert server.LOG_DROPPED_TOTAL["count"] == 1
    handler.close()


def test_real_span_context_is_preserved_after_span_reset(monkeypatch):
    trace = pytest.importorskip("opentelemetry.trace")
    monkeypatch.setenv("AXIOM_OTEL_ENABLED", "1")
    handler = server._NonBlockingQueueHandler(queue.Queue(maxsize=1))
    span_context = trace.SpanContext(
        trace_id=int("12345678901234567890123456789012", 16),
        span_id=int("1234567890123456", 16),
        is_remote=False,
    )
    with trace.use_span(trace.NonRecordingSpan(span_context), end_on_exit=False):
        record = _record()
        record.request_id = "request-with-real-span"
        prepared = handler.prepare(record)
    doc = json.loads(server.JsonLogFormatter().format(prepared))
    assert doc["trace_id"] == "12345678901234567890123456789012"
    assert doc["span_id"] == "1234567890123456"
    assert doc["request_id"] == "request-with-real-span"
    handler.close()
