"""Pure-ASGI adapters for synchronous request rejection gates."""

from __future__ import annotations

from collections.abc import Callable

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send


class _RequestGateMiddleware:
    def __init__(self, app: ASGIApp, gate: Callable[[Request], Response | None]) -> None:
        self.app = app
        self.gate = gate

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response = self.gate(Request(scope))
        if response is not None:
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class ApiKeyAuthMiddleware(_RequestGateMiddleware):
    """Run the injected API-key gate before the inner ASGI application."""


class RateLimitMiddleware(_RequestGateMiddleware):
    """Run the injected rate-limit gate before the inner ASGI application."""
