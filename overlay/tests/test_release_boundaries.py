"""Release-boundary regressions: private artifacts and streamed body limits."""
import httpx
import pytest
from fastapi.testclient import TestClient
from overlay import server


def test_runtime_database_is_never_public(monkeypatch):
    monkeypatch.setattr(server, "_AUTH_REQUIRED", False)
    monkeypatch.setattr(server, "_API_KEY_DIGESTS", {})
    with TestClient(server.app) as client:
        assert client.get("/static/overlay_store.db").status_code == 404


def test_page_images_require_auth(monkeypatch):
    monkeypatch.setattr(server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(server, "_API_KEY_DIGESTS", {"a" * 64: "tenant"})
    with TestClient(server.app) as client:
        assert client.get("/static/page_images/missing.png").status_code == 401


@pytest.mark.asyncio
async def test_chunked_body_cannot_bypass_limit(monkeypatch):
    monkeypatch.setattr(server, "MAX_UPLOAD_BYTES", 64)
    async def chunks():
        yield b'{"file":"'
        yield b'x' * 80
        yield b'"}'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://testserver") as client:
        response = await client.post("/demo", content=chunks(), headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_negative_content_length_rejected():
    with TestClient(server.app) as client:
        assert client.post("/demo", content=b"{}", headers={"Content-Length": "-1"}).status_code == 400


@pytest.mark.asyncio
async def test_small_chunked_request_is_preserved():
    async def chunks():
        yield b'{"file":"sample_'
        yield b'memo_01.txt"}'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://testserver") as client:
        response = await client.post("/demo", content=chunks(), headers={"Content-Type": "application/json"})
    assert response.status_code == 200
    assert response.json()["success"]


@pytest.mark.asyncio
async def test_body_limit_accepts_exact_boundary_and_stops_reading():
    from overlay.body_limit import BodyLimitMiddleware
    called = []
    async def app(scope, receive, send):
        called.append((await receive())["body"])
    pending = [{"type": "http.request", "body": b"1234", "more_body": False}]
    async def receive():
        return pending.pop(0)
    sent = []
    middleware = BodyLimitMiddleware(app, limit=lambda: 4)
    await middleware({"type": "http", "headers": []}, receive, sent.append)
    assert called == [b"1234"]


@pytest.mark.asyncio
async def test_body_limit_rejects_duplicate_length():
    from overlay.body_limit import BodyLimitMiddleware
    async def unexpected(*args):
        raise AssertionError("application/body reader must not run")
    sent = []
    async def send(message):
        sent.append(message)
    middleware = BodyLimitMiddleware(unexpected, limit=lambda: 4)
    await middleware({"type": "http", "headers": [(b"content-length", b"1"), (b"content-length", b"1")]}, unexpected, send)
    assert sent[0]["status"] == 400


@pytest.mark.asyncio
async def test_very_long_length_is_413_not_integer_conversion_failure():
    from overlay.body_limit import BodyLimitMiddleware
    async def unexpected(*args):
        raise AssertionError("body reader/application must not run")
    sent = []
    async def send(message):
        sent.append(message)
    await BodyLimitMiddleware(unexpected, lambda: 64)(
        {"type": "http", "headers": [(b"content-length", b"9" * 5000)]}, unexpected, send)
    assert sent[0]["status"] == 413
