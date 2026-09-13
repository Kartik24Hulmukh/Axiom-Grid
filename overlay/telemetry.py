"""Opt-in OpenTelemetry spans; never record bodies, credentials or query strings.

SDK/provider/exporter configuration belongs to the deployment (e.g. the
opentelemetry-instrument launcher). No unsolicited external exporter is enabled.
"""
import os


def install_tracing(app):
    if os.getenv("AXIOM_OTEL_ENABLED", "0") != "1":
        return
    # Explicit opt-in must fail startup if the tracing dependency is absent.
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind, Status, StatusCode
    tracer = trace.get_tracer("axiom-grid.overlay")

    @app.middleware("http")
    async def traced_request(request, call_next):
        with tracer.start_as_current_span("HTTP request", kind=SpanKind.SERVER,
                                          record_exception=False,
                                          set_status_on_exception=False) as span:
            span.set_attribute("http.request.method", request.method)
            try:
                response = await call_next(request)
            except Exception:
                span.set_status(Status(StatusCode.ERROR))
                raise
            route = getattr(request.scope.get("route"), "path", "unmatched")
            span.update_name(f"{request.method} {route}")
            span.set_attribute("http.route", route)
            span.set_attribute("http.response.status_code", response.status_code)
            if response.status_code >= 500:
                span.set_status(Status(StatusCode.ERROR))
            return response


def log_context():
    if os.getenv("AXIOM_OTEL_ENABLED", "0") != "1":
        return {}
    from opentelemetry import trace
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return {}
    return {"trace_id": format(context.trace_id, "032x"),
            "span_id": format(context.span_id, "016x")}
