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


def test_concurrent_demo_requests(client):
    """Concurrency: N parallel /demo requests must not corrupt the shared
    SQLite-backed memory store or raise interface errors, and all must
    complete with a well-formed structured response."""
    import concurrent.futures

    def _call():
        return client.post("/demo", json={"file": "sample_memo_01.txt"})

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(_call) for _ in range(5)]
        responses = [f.result(timeout=30) for f in futures]

    assert len(responses) == 5
    for r in responses:
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True, data.get("error")
        assert "document_text" in data


def test_extract_document_boundaries(client):
    """Boundary + injection guards on /api/extract-document."""
    for bad in ("", "   ", "a\x00b"):
        response = client.post("/api/extract-document", json={"file": bad})
        assert response.status_code == 422, (bad, response.status_code)

    response = client.post("/api/extract-document", json={"file": "definitely_missing_xyz.txt"})
    assert response.status_code == 404


def test_ask_document_boundaries(client):
    """Boundary checks on /api/ask-document: blank question/file rejected."""
    response = client.post("/api/ask-document", json={"file": "", "question": "who?"})
    assert response.status_code == 422

    response = client.post("/api/ask-document", json={"file": "axiom-grid/fixtures/wedge/sample_memo_01.txt", "question": ""})
    assert response.status_code == 422


def test_apply_and_correct_validation(client):
    """Boundary: empty ext_id must not be silently accepted."""
    response = client.post("/apply", json={"ext_id": "", "accept": True})
    assert response.status_code == 200
    assert response.json()["success"] is False


def test_graph_query_rejects_blank(client):
    """Boundary: blank keyword/query on /api/graph/query is rejected (400)."""
    response = client.post("/api/graph/query", json={"keyword": ""})
    assert response.status_code == 400


def test_figures_requires_file_param(client):
    """Boundary: missing file parameter on /api/figures is rejected (400)."""
    response = client.get("/api/figures/doc123")
    assert response.status_code == 400


def test_extract_document_logs_unexpected_exceptions(client, caplog, monkeypatch, tmp_path):
    """Degraded-state: unexpected pipeline exceptions on /api/extract-document
    are logged and fail closed with a 500, never a raw traceback leak."""
    from overlay import server

    def boom(*_a, **_k):
        raise RuntimeError("synthetic extraction failure")

    monkeypatch.setattr(server.OrchestratorImpl, "run", boom)
    doc_path = tmp_path / "sample_memo.txt"
    doc_path.write_text("CLASSIFICATION: SECRET\nSUBJECT: Synthetic test\n", encoding="utf-8")
    with caplog.at_level("ERROR", logger="overlay.server"):
        response = client.post("/api/extract-document", json={"file": str(doc_path)})
    assert response.status_code == 500
    assert any("extract-document" in r.message for r in caplog.records)


def test_sandbox_escape_rejected(client):
    """SEC-001 regression: directory traversal and absolute path leaks fail-closed with 404."""
    probes = [
        "/etc/passwd",
        ("../" * 4) + "etc/passwd",
        "fixtures/" + ("../" * 3) + "etc/passwd",
        "/proc/self/environ",
        "fixtures/" + ("../" * 3) + "etc/shadow",
    ]
    for probe in probes:
        r_ext = client.post("/api/extract-document", json={"file": probe})
        assert r_ext.status_code == 404, f"Failed for /api/extract-document with {probe}: {r_ext.status_code}"

        r_demo = client.post("/demo", json={"file": probe})
        assert r_demo.status_code == 404, f"Failed for /demo with {probe}: {r_demo.status_code}"

        r_fig = client.get(f"/api/figures/doc1?file={probe}")
        assert r_fig.status_code == 404, f"Failed for /api/figures with {probe}: {r_fig.status_code}"


def test_csrf_origin_gate_rejects_evil_origin(client):
    """SEC-002 regression: requests with non-local Origin headers are rejected with 403."""
    response = client.post(
        "/demo",
        json={"file": "sample_memo_01.txt"},
        headers={"Origin": "https://evil.example"}
    )
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]


def test_csrf_origin_gate_rejects_null_origin(client):
    """SEC-002 regression: requests with opaque Origin (null) are rejected with 403."""
    response = client.post(
        "/demo",
        json={"file": "sample_memo_01.txt"},
        headers={"Origin": "null"}
    )
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]


def test_csrf_origin_gate_allows_local_origin(client):
    """SEC-002 regression: local desktop and overlay UI origins are permitted."""
    response = client.post(
        "/demo",
        json={"file": "sample_memo_01.txt"},
        headers={"Origin": "http://127.0.0.1:8765"}
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_security_headers_present(client):
    """SEC-003 regression: all responses carry defense-in-depth security headers."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "Content-Security-Policy" in response.headers

    api_response = client.post("/demo", json={"file": "missing.txt"})
    assert api_response.status_code == 404
    assert api_response.headers["X-Content-Type-Options"] == "nosniff"
    assert api_response.headers["X-Frame-Options"] == "DENY"


def test_oversized_body_rejected(client):
    """SEC-004 regression: oversized payloads are rejected with 413 before parsing."""
    response = client.post(
        "/api/extract-document",
        json={"file": "sample_memo_01.txt"},
        headers={"Content-Length": str(10 * 1024 * 1024)},
    )
    assert response.status_code == 413
    assert "too large" in response.json()["detail"].lower()


def test_healthz_endpoint(client):
    """OPS-001: liveness probe always returns ok when process is serving."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readyz_endpoint(client):
    """OPS-001: readiness probe verifies the real extraction pipeline end-to-end."""
    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["pipeline"] == "ok"
    assert data["fields_extracted"] >= 1


def test_metrics_endpoint(client):
    """OPS-001: metrics endpoint reports counters and latency after traffic."""
    client.get("/healthz")
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["requests_total"] >= 1
    assert "200" in data["status_counts"]
    assert data["uptime_seconds"] >= 0



def test_rate_limit_enforced_and_healthz_exempt(client, monkeypatch):
    """SEC-005: exceeding the per-IP rate budget yields 429 with Retry-After,
    while /healthz stays exempt so liveness probes are never throttled."""
    import overlay.server as srv

    monkeypatch.setattr(srv, "_RATE_LIMIT_PER_MIN", 5)
    srv._rate_limit_buckets.clear()

    statuses = [client.get("/healthz").status_code for _ in range(20)]
    assert all(s == 200 for s in statuses)

    srv._rate_limit_buckets.clear()
    results = [client.get("/api/traces").status_code for _ in range(10)]
    assert 429 in results
    resp = client.get("/api/traces")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers



# ------------------------------------------------------------------
# SEC-006: bearer / API-key authentication
# ------------------------------------------------------------------

_GOOD_KEY = "ag_test_key_0123456789abcdef"
_GOOD_KEY_2 = "ag_second_tenant_fedcba9876543210"


def _enable_auth(monkeypatch, *keys):
    import hashlib

    import overlay.server as srv

    digests = {hashlib.sha256(k.encode()).hexdigest(): hashlib.sha256(k.encode()).hexdigest()[:12] for k in keys}
    monkeypatch.setattr(srv, "_API_KEY_DIGESTS", digests)
    monkeypatch.setattr(srv, "_AUTH_REQUIRED", True)
    srv._rate_limit_buckets.clear()
    return srv


def test_auth_disabled_by_default_local_first(client):
    """No AXIOM_API_KEYS => same-origin desktop mode: API stays open and
    /healthz reports auth_enabled=false so operators can see the posture."""
    import overlay.server as srv

    if srv._API_KEY_DIGESTS or srv._AUTH_REQUIRED:
        pytest.skip("auth configured in this environment")
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["auth_enabled"] is False
    assert client.get("/metrics").status_code == 200


def test_auth_rejects_missing_and_wrong_key(client, monkeypatch):
    _enable_auth(monkeypatch, _GOOD_KEY)
    r = client.get("/api/traces")
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"].startswith("Bearer")
    assert client.get("/api/traces", headers={"Authorization": "Bearer nope_nope_nope_nope"}).status_code == 401
    assert client.get("/api/traces", headers={"X-API-Key": _GOOD_KEY + "x"}).status_code == 401
    # a prefix of the real key must never pass (constant-time digest compare)
    assert client.get("/api/traces", headers={"Authorization": f"Bearer {_GOOD_KEY[:-1]}"}).status_code == 401
    # mutating endpoints are gated too
    assert client.post("/demo", json={"file": "x.txt", "question": "q"}).status_code == 401
    assert client.post("/api/extract-document", json={"file": "x.txt"}).status_code == 401


def test_auth_accepts_bearer_and_x_api_key(client, monkeypatch):
    _enable_auth(monkeypatch, _GOOD_KEY, _GOOD_KEY_2)
    assert client.get("/api/traces", headers={"Authorization": f"Bearer {_GOOD_KEY}"}).status_code == 200
    assert client.get("/api/traces", headers={"Authorization": f"bearer {_GOOD_KEY_2}"}).status_code == 200
    assert client.get("/api/traces", headers={"X-API-Key": _GOOD_KEY}).status_code == 200


def test_auth_probes_and_landing_exempt(client, monkeypatch):
    """Orchestrator probes and the landing page must never require a key,
    otherwise k8s/Docker would kill a perfectly healthy, correctly locked-down pod."""
    _enable_auth(monkeypatch, _GOOD_KEY)
    assert client.get("/healthz").status_code == 200
    assert client.get("/healthz").json()["auth_enabled"] is True
    assert client.get("/readyz").status_code in (200, 503)
    assert client.get("/").status_code in (200, 404)


def test_auth_required_without_keys_fails_closed(client, monkeypatch):
    """AXIOM_REQUIRE_AUTH=1 with no keys must return 503, never silently run open."""
    import overlay.server as srv

    monkeypatch.setattr(srv, "_API_KEY_DIGESTS", {})
    monkeypatch.setattr(srv, "_AUTH_REQUIRED", True)
    r = client.get("/api/traces", headers={"Authorization": f"Bearer {_GOOD_KEY}"})
    assert r.status_code == 503
    assert client.get("/healthz").status_code == 200


def test_auth_rejections_are_rate_limited(client, monkeypatch):
    """Brute-forcing keys must still hit the SEC-005 per-IP limiter (429)."""
    srv = _enable_auth(monkeypatch, _GOOD_KEY)
    monkeypatch.setattr(srv, "_RATE_LIMIT_PER_MIN", 5)
    results = [client.get("/api/traces", headers={"X-API-Key": f"guess_{i}_0123456789"}).status_code for i in range(12)]
    assert 401 in results and 429 in results
    assert results.index(401) < results.index(429)


def test_authenticated_tenant_gets_own_rate_tier(client, monkeypatch):
    """Valid tenants are bucketed by key (not IP) with the larger authenticated
    quota, so anonymous flooding from the same IP cannot starve a paying tenant."""
    srv = _enable_auth(monkeypatch, _GOOD_KEY, _GOOD_KEY_2)
    monkeypatch.setattr(srv, "_RATE_LIMIT_PER_MIN", 3)
    monkeypatch.setattr(srv, "_RATE_LIMIT_PER_MIN_AUTH", 8)
    # exhaust the anonymous per-IP budget
    anon = [client.get("/api/traces").status_code for _ in range(6)]
    assert 429 in anon
    # tenant A still has its own budget of 8
    a = [client.get("/api/traces", headers={"Authorization": f"Bearer {_GOOD_KEY}"}).status_code for _ in range(8)]
    assert a == [200] * 8
    assert client.get("/api/traces", headers={"Authorization": f"Bearer {_GOOD_KEY}"}).status_code == 429
    # tenant B is isolated from tenant A's exhaustion
    assert client.get("/api/traces", headers={"Authorization": f"Bearer {_GOOD_KEY_2}"}).status_code == 200


def test_livez_and_prometheus_metrics(client):
    live = client.get("/livez")
    assert live.status_code == 200 and live.json()["status"] == "alive"
    metrics = client.get("/metrics?format=prometheus")
    assert metrics.status_code == 200
    assert "axiom_requests_total" in metrics.text

def test_metrics_include_percentiles(client):
    body = client.get("/metrics").json()
    assert set(body["latency_percentiles"]) == {"p50", "p90", "p95", "p99"}
