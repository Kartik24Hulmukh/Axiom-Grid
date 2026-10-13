"""Opt-in OpenTelemetry spans; never record bodies, credentials or query strings.

SDK/provider/exporter configuration belongs to the deployment (e.g. the
opentelemetry-instrument launcher). No unsolicited external exporter is enabled.
"""
import os


class TracingMiddleware:
    """Pure ASGI tracing: no extra request task or intercepted body stream."""

    def __init__(self, app):
        from opentelemetry import trace
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )
        self.app = app
        self.tracer = trace.get_tracer("axiom-grid.overlay")
        self.propagator = TraceContextTextMapPropagator()

    async def __call__(self, scope, receive, send):
        from opentelemetry.trace import SpanKind, Status, StatusCode
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        # Continue W3C tracing without importing untrusted baggage or recording headers.
        carrier = {name.decode("latin-1"): value.decode("latin-1")
                   for name, value in scope.get("headers", ())
                   if name.lower() == b"traceparent" or name.lower() == b"tracestate"}
        parent = self.propagator.extract(carrier=carrier)
        with self.tracer.start_as_current_span(
            "HTTP request", context=parent, kind=SpanKind.SERVER,
            record_exception=False, set_status_on_exception=False,
        ) as span:
            span.set_attribute("http.request.method", scope["method"])

            async def traced_send(message):
                if message["type"] == "http.response.start":
                    code = message["status"]
                    span.set_attribute("http.response.status_code", code)
                    if code >= 500:
                        span.set_status(Status(StatusCode.ERROR))
                await send(message)

            try:
                await self.app(scope, receive, traced_send)
            except Exception:
                span.set_status(Status(StatusCode.ERROR))
                raise
            finally:
                route = getattr(scope.get("route"), "path", "unmatched")
                span.update_name(f"{scope['method']} {route}")
                span.set_attribute("http.route", route)


def install_tracing(app):
    if os.getenv("AXIOM_OTEL_ENABLED", "0") != "1":
        return
    # Explicit opt-in must fail startup if the tracing dependency is absent.
    from opentelemetry import trace  # noqa: F401 -- validate declared dependency
    app.add_middleware(TracingMiddleware)


def log_context():
    if os.getenv("AXIOM_OTEL_ENABLED", "0") != "1":
        return {}
    from opentelemetry import trace
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return {}
    return {"trace_id": format(context.trace_id, "032x"),
            "span_id": format(context.span_id, "016x")}
