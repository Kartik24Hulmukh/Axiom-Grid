"""Pure-ASGI request correlation and response security header middleware."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestIdMiddleware:
    """Set correlation state and replace the response header without body/task wrappers."""

    def __init__(self, app: ASGIApp, max_len: int | Callable[[], int] = 64) -> None:
        self.app = app
        self.max_len = max_len

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        rid = request.headers.get("x-request-id", "").strip()
        max_len = self.max_len() if callable(self.max_len) else self.max_len
        if not rid or len(rid) > max_len:
            rid = uuid.uuid4().hex
        rid = "".join(ch for ch in rid if ch.isascii() and (ch.isalnum() or ch in "-_.")) or uuid.uuid4().hex
        request.state.request_id = rid

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Request-Id"] = rid
            await send(message)

        await self.app(scope, receive, send_with_request_id)


class SecurityHeadersMiddleware:
    """Apply security headers at response start, leaving the ASGI stream untouched."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                if request.url.path == "/" or request.url.path.endswith(".html"):
                    headers["Content-Security-Policy"] = (
                        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
                    )
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
