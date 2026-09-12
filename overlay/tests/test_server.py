"""
Tests for overlay FastAPI server.
"""

import hashlib
import pathlib

import pytest
from fastapi.testclient import TestClient

from overlay.server import app


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


def test_serve_index_html(client):
    """Test that GET / returns the index.html page."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Kairo Phantom" in response.text


def test_demo_endpoint_not_found(client):
    """Test that POST /demo returns 404 for missing file."""
    response = client.post("/demo", json={"file": "missing_file.txt"})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_demo_and_actions_endpoints(client):
    """Test full flow: run demo on fixture -> apply action -> correct."""
    # 1. Run demo
    response = client.post("/demo", json={"file": "sample_memo_01.txt"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"], f"Demo endpoint failed: {data.get('error')}"
    assert "document_text" in data
    assert len(data["suggestions"]) > 0, f"No suggestions. Suggestions: {data['suggestions']}. Trace: {data['trace']}"
    assert len(data["trace"]["stages"]) > 0

    ext_id = data["suggestions"][0]["ext_id"]

    # 2. Apply CUA action
    app_response = client.post("/apply", json={"ext_id": ext_id, "accept": True})
    assert app_response.status_code == 200
    app_data = app_response.json()
    assert app_data["success"]
    assert app_data["post_state"]["status"] == "verified"

    # 3. Record correction (flywheel)
    corr_response = client.post("/correct", json={
        "ext_id": ext_id,
        "field_name": "author",
        "original": "Dr. Margaret Chen",
        "corrected": "Margaret Chen",
        "reason": "Test correction"
    })
    assert corr_response.status_code == 200
    assert corr_response.json()["success"]


def test_demo_uses_real_sha256_provenance_digest(client):
    """Regression: the demo path must hash the real file bytes, never a placeholder."""
    fixture = pathlib.Path(__file__).resolve().parents[2] / "fixtures" / "wedge" / "sample_memo_01.txt"
    if not fixture.exists():
        pytest.skip("fixture missing")
    expected = hashlib.sha256(fixture.read_bytes()).hexdigest()
    from overlay import server

    seen = {}
    original = server.Document

    def capture(**kwargs):
        seen.update(kwargs)
        return original(**kwargs)

    server.Document = capture
    try:
        response = client.post("/demo", json={"file": "sample_memo_01.txt"})
    finally:
        server.Document = original
    assert response.status_code == 200
    assert seen["sha256"] == expected
    assert len(seen["sha256"]) == 64 and seen["sha256"] != "mock-sha256"


def test_demo_rejects_empty_file_name(client):
    """Boundary: empty file name is rejected, not resolved to a directory."""
    for bad in ("", "   ", ".", "fixtures"):
        response = client.post("/demo", json={"file": bad})
        assert response.status_code in (404, 422), (bad, response.status_code)


def test_demo_logs_unexpected_exceptions(client, caplog):
    """Unhandled errors on /demo are logged (not silently swallowed) and still
    return a fail-closed structured error, never a raw traceback to the client."""
    from overlay import server

    def boom(_doc):
        raise RuntimeError("synthetic failure for logging regression test")

    original_run = server.orchestrator.run
    server.orchestrator.run = boom
    try:
        with caplog.at_level("ERROR", logger="overlay.server"):
            response = client.post("/demo", json={"file": "sample_memo_01.txt"})
    finally:
        server.orchestrator.run = original_run
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "synthetic failure" in data["error"]
    assert any("unhandled error in overlay endpoint" in r.message for r in caplog.records)
