"""Single pure-ASGI request policy; no BaseHTTPMiddleware task/stream ladders."""
from __future__ import annotations

import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.requests import Request

from overlay.admission import AdmissionTiming, admission_timing
from overlay.tenant_context import tenant_context


class RequestPolicyMiddleware:
    def __init__(self, app, server):
        self.app = app
        # Keep operator settings and monkeypatchable test hooks authoritative.
        self.server = server

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        timing = AdmissionTiming()
        token = admission_timing.set(timing)
        try:
            return await self._http_call(scope, receive, send, timing)
        finally:
            admission_timing.reset(token)

    async def _http_call(self, scope, receive, send, timing):
        server = self.server
        request = Request(scope, receive=receive)
        rid = request.headers.get("x-request-id", "").strip()
        if not rid or len(rid) > server._REQUEST_ID_MAX_LEN:
            rid = uuid.uuid4().hex
        rid = "".join(ch for ch in rid if ch.isascii() and (ch.isalnum() or ch in "-_.")) or uuid.uuid4().hex
        request.state.request_id = rid
        started = time.perf_counter()

        async def policy_send(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Request-Id"] = rid
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                if scope["path"] == "/" or scope["path"].endswith(".html"):
                    headers["Content-Security-Policy"] = (
                        "default-src 'self'; script-src 'self'; "
                        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
                    )
                dt_ms = (time.perf_counter() - started) * 1000
                # app includes queueing after ASGI policy entry. admission is
                # a subset: gate enqueue -> grant/cancel, not executor waiting,
                # native handler execution, event-loop lag or wire latency.
                headers.append("Server-Timing", (
                    f"app;dur={dt_ms:.3f}, admission;dur={timing.queue_wait_ms:.3f}"
                ))
                status = message["status"]
                metrics = server.OPS_METRICS
                metrics["requests_total"] += 1
                metrics["latency_ms_total"] += dt_ms
                metrics["latency_samples"].append(dt_ms)
                metrics["latency_ms_max"] = max(metrics["latency_ms_max"], round(dt_ms, 2))
                key = str(status)
                metrics["status_counts"][key] = metrics["status_counts"].get(key, 0) + 1
                if status >= 500:
                    metrics["errors_total"] += 1
                server.logger.info("request completed", extra={
                    "request_id": rid, "path": scope["path"], "status": status,
                    "latency_ms": round(dt_ms, 2),
                    "admission_wait_ms": round(timing.queue_wait_ms, 3),
                    "client": request.client.host if request.client else "unknown",
                })
            await send(message)

        async def accepted(_request):
            return None

        # Preserve existing quota -> auth -> origin precedence while applying
        # security headers and correlation to their rejected responses too.
        for check in (server.rate_limit_middleware, server.api_key_auth_middleware,
                      server.enforce_origin_gate):
            response = await check(request, accepted)
            if response is not None:
                return await response(scope, receive, policy_send)
        if scope["path"].startswith("/static/page_images") and server._auth_enabled():
            from starlette.responses import JSONResponse
            return await JSONResponse({"detail": "Legacy images are not credential-scoped"}, status_code=404)(scope, receive, policy_send)
        token = tenant_context.set(getattr(request.state, "tenant", "local"))
        try:
            await self.app(scope, receive, policy_send)
        finally:
            tenant_context.reset(token)