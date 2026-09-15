"""The Prometheus exposition must carry everything deploy/alerts.yml alerts on.

If this test fails, the SLO alerts are silently dead in production.
"""
import re
from fastapi.testclient import TestClient

from overlay import server


def test_prometheus_exposition_has_slo_series(monkeypatch):
    monkeypatch.setattr(server, "REQUIRE_AUTH", False, raising=False)
    client = TestClient(server.app)
    for _ in range(5):
        assert client.get("/healthz").status_code == 200
    body = client.get("/metrics", params={"format": "prometheus"}).text
    for series in (
        "axiom_requests_total", "axiom_errors_total", "axiom_extraction_shed_total",
        "axiom_request_latency_ms_count", "axiom_request_latency_ms_sum",
        "axiom_request_latency_ms_max", "axiom_uptime_seconds",
    ):
        assert re.search(rf"^{series} [0-9.]+$", body, re.M), f"missing {series}"
    for q in ("0.5", "0.9", "0.95", "0.99"):
        assert re.search(rf'^axiom_request_latency_ms\{{quantile="{q}"\}} [0-9.]+$', body, re.M), q
    assert re.search(r'^axiom_http_status_total\{code="200"\} [1-9][0-9]*$', body, re.M)
    assert "# TYPE axiom_request_latency_ms summary" in body
