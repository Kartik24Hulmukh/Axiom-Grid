import json
from pathlib import Path

from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from overlay import server


def test_policy_has_no_basehttp_task_ladder():
    assert not any(issubclass(layer.cls, BaseHTTPMiddleware) for layer in server.app.user_middleware)


def test_policy_headers_and_metrics_include_origin_rejection():
    with TestClient(server.app) as client:
        result = client.get("/healthz", headers={"Origin": "https://evil.example", "X-Request-Id": "policy-check"})
    assert result.status_code == 403
    assert result.headers["X-Request-Id"] == "policy-check"
    assert result.headers["X-Content-Type-Options"] == "nosniff"
    assert result.headers["Server-Timing"].startswith("app;dur=")


def test_lifecycle_marker_is_not_stale_and_requires_completed_shutdown(tmp_path, monkeypatch):
    marker = tmp_path / "lifecycle.json"
    marker.write_text('{"stale":true}')
    monkeypatch.setenv("AXIOM_LIFECYCLE_FILE", str(marker))
    with TestClient(server.app) as client:
        assert not marker.exists()
        assert client.get("/readyz").status_code == 200
    assert json.loads(marker.read_text()) == {"workers_joined": True, "state_closed": True}


def test_candidate_deployment_never_forces_test_mode_or_unisolated_parsing():
    root = Path(__file__).resolve().parents[2]
    docker = (root / "docker/Dockerfile.overlay").read_text()
    compose = (root / "deploy/docker-compose.prod.yml").read_text()
    assert "KAIRO_GATEWAY_TEST_MODE=true" not in docker
    assert "AXIOM_EXTRACTION_ISOLATION=process" in docker
    assert "AXIOM_EXTRACTION_ISOLATION: process" in compose
    assert "WEB_CONCURRENCY=1" in docker
    assert 'WEB_CONCURRENCY: "1"' in compose
    assert "--scale api=2" not in compose