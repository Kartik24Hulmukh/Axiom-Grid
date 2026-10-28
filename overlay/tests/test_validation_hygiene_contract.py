"""Synthetic validation disclosure/logging contracts; no files or model calls."""
import json
import logging

import pytest
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.requests import Request

from overlay import server


@pytest.mark.asyncio
async def test_fastapi_validation_errors_keep_exception_context_sanitized():
    # FastAPI's errors() differs from Pydantic's keyword-taking API. Exercise
    # the real exception class so a TypeError fallback cannot bypass hygiene.
    marker = "SYNTHETIC_PRIVATE_CONTEXT_DO_NOT_REFLECT"
    exc = RequestValidationError([{
        "type": "value_error", "loc": ("body", "file"),
        "msg": "invalid synthetic value", "input": b"x" * 4096,
        "ctx": {"error": ValueError(marker)},
    }])
    request = Request({"type": "http", "method": "POST", "path": "/api/extract-document",
                       "headers": [], "query_string": b""})
    response = await server._validation_exception_handler(request, exc)
    assert response.status_code == 422
    body = json.loads(response.body)
    assert body["detail"][0]["ctx"]["error"] == "ValueError"
    assert marker.encode() not in response.body
    assert "truncated 3840 bytes" in body["detail"][0]["input"]
    assert len(response.body) < 1024


def test_completion_and_validation_records_remain_visible_at_info(caplog):
    with caplog.at_level(logging.INFO, logger="overlay.server"):
        with TestClient(server.app) as client:
            response = client.post("/api/extract-document", json={"file": ""})
    assert response.status_code == 422
    records = [r for r in caplog.records if r.name == "overlay.server"]
    completed = [r for r in records if r.getMessage() == "request completed"]
    rejected = [r for r in records if r.getMessage() == "request validation rejected"]
    assert completed and completed[-1].levelno == logging.INFO
    assert rejected and rejected[-1].levelno == logging.WARNING
    assert completed[-1].path == rejected[-1].path == "/api/extract-document"
    assert completed[-1].status == rejected[-1].status == 422
