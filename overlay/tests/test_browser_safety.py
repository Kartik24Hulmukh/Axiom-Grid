"""Public script, safe rendering and error-detail regression gates."""
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from overlay import server


ROOT = Path(__file__).resolve().parents[2]


def test_public_script_is_available_without_production_credentials(monkeypatch):
    monkeypatch.setenv("AXIOM_REQUIRE_AUTH", "1")
    monkeypatch.setenv("AXIOM_API_KEYS", "test-only")
    with TestClient(server.app) as client:
        response = client.get("/assets/overlay.js")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/javascript")
        assert client.get("/assets/../server.py").status_code != 200
        assert client.get("/").headers["content-security-policy"].split("script-src ")[1].split(";")[0] == "'self'"


def test_browser_script_parses_and_never_interpolates_untrusted_html():
    script = ROOT / "overlay/templates/overlay.js"
    result = subprocess.run(["node", "--check", str(script)], capture_output=True, timeout=10)
    assert result.returncode == 0
    source = script.read_text()
    for forbidden in ("innerHTML", "outerHTML", "onclick=", "eval(", "new Function"):
        assert forbidden not in source
    html = (ROOT / "overlay/templates/index.html").read_text()
    assert "<script>" not in html
    assert "fonts.googleapis.com" not in html


@pytest.mark.parametrize("route,payload", [
    ("/demo", {"file": "sample_memo_01.txt"}),
    ("/correct", {"ext_id": "test", "field_name": "test", "original": "a",
                  "corrected": "b", "reason": "test"}),
])
def test_internal_errors_are_not_exposed(monkeypatch, route, payload):
    def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE_INTERNAL_PATH_AND_SECRET")
    if route == "/demo":
        monkeypatch.setattr(server, "_run_document_preview", fail)
    else:
        monkeypatch.setattr(server.evidence_store, "review", fail)
    with TestClient(server.app) as client:
        response = client.post(route, json=payload)
    assert response.status_code == 500
    assert "PRIVATE_INTERNAL" not in response.text