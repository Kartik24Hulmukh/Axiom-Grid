"""Pure-ASGI origin and request governor guards without body or task wrappers."""

from __future__ import annotations

import time
from collections.abc import Callable

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class OriginGateMiddleware:
    """Reject disallowed HTTP origins before invoking the inner application."""

    def __init__(
        self,
        app: ASGIApp,
        allowed: Callable[[str], bool],
        response_class: type[Response],
    ) -> None:
        self.app = app
        self.allowed = allowed
        self.response_class = response_class

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        origin = Request(scope).headers.get("origin")
        if origin is not None and not self.allowed(origin):
            response = self.response_class(status_code=403, content={"detail": "Forbidden: invalid origin"})
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class RequestGovernorMiddleware:
    """Validate declared HTTP length and report completion at the first response start."""

    def __init__(
        self,
        app: ASGIApp,
        limit: Callable[[], int],
        response_class: type[Response],
        on_response_start: Callable[[Request, int, float], None],
    ) -> None:
        self.app = app
        self.limit = limit
        self.response_class = response_class
        self.on_response_start = on_response_start

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        t0 = time.perf_counter()
        request = Request(scope)
        content_length = request.headers.get("content-length")
        if content_length is not None:
            response = None
            try:
                if not content_length.isascii() or not content_length.isdecimal():
                    raise ValueError("invalid length")
                if int(content_length) > self.limit():
                    response = self.response_class(status_code=413, content={"detail": "Payload too large"})
            except ValueError:
                response = self.response_class(status_code=400, content={"detail": "Invalid Content-Length"})
            if response is not None:
                # Early governor rejections never entered the old completion block.
                await response(scope, receive, send)
                return

        started = False

        async def send_with_completion(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start" and not started:
                started = True
                self.on_response_start(request, message["status"], (time.perf_counter() - t0) * 1000)
            await send(message)

        await self.app(scope, receive, send_with_completion)
