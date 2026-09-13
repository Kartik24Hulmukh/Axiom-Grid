"""Wave 7 hardening regressions: SEC-007 CORS, SEC-008 proxy-header trust,
rate-limit bucket hard cap, OPS-002 JSON logging, readyz error hygiene."""
import json
import logging
import threading

from fastapi.testclient import TestClient

from overlay import server as s
from overlay.server import JsonLogFormatter, app

client = TestClient(app)


def _reset_buckets():
    with s._rate_limit_lock:
        s._rate_limit_buckets.clear()


def test_xff_is_ignored_unless_proxy_trusted(monkeypatch):
    _reset_buckets()
    monkeypatch.setattr(s, "_TRUST_PROXY", False)
    for i in range(50):
        assert client.get("/metrics", headers={"x-forwarded-for": f"10.0.0.{i}"}).status_code == 200
    # Every spoofed source collapses onto the real socket peer: one bucket.
    assert len(s._rate_limit_buckets) == 1


def test_xff_spoof_cannot_bypass_limit(monkeypatch):
    _reset_buckets()
    monkeypatch.setattr(s, "_TRUST_PROXY", False)
    monkeypatch.setattr(s, "_RATE_LIMIT_PER_MIN", 5)
    codes = [client.get("/metrics", headers={"x-forwarded-for": f"10.1.0.{i}"}).status_code for i in range(8)]
    assert codes.count(429) == 3 and codes[:5] == [200] * 5
    r = client.get("/metrics")
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1


def test_xff_honoured_when_proxy_trusted(monkeypatch):
    _reset_buckets()
    monkeypatch.setattr(s, "_TRUST_PROXY", True)
    for i in range(5):
        client.get("/metrics", headers={"x-forwarded-for": f"10.2.0.{i}, 192.168.0.1"})
    assert {"10.2.0.0", "10.2.0.4"} <= set(s._rate_limit_buckets)
    # Over-long header values are not used as keys (cardinality / memory guard).
    client.get("/metrics", headers={"x-forwarded-for": "x" * 200})
    assert all(len(k) <= 64 for k in s._rate_limit_buckets)


def test_bucket_hard_cap_bounds_memory_under_rotating_flood(monkeypatch):
    _reset_buckets()
    monkeypatch.setattr(s, "_TRUST_PROXY", True)
    monkeypatch.setattr(s, "_RATE_LIMIT_BUCKET_HIGH_WATER", 10)
    monkeypatch.setattr(s, "_RATE_LIMIT_BUCKET_HARD_CAP", 20)
    for i in range(300):
        client.get("/metrics", headers={"x-forwarded-for": f"172.16.{i // 250}.{i % 250}"})
    assert len(s._rate_limit_buckets) <= 20


def test_bucket_hard_cap_is_thread_safe(monkeypatch):
    _reset_buckets()
    monkeypatch.setattr(s, "_TRUST_PROXY", True)
    monkeypatch.setattr(s, "_RATE_LIMIT_BUCKET_HIGH_WATER", 10)
    monkeypatch.setattr(s, "_RATE_LIMIT_BUCKET_HARD_CAP", 50)
    errors = []

    def worker(n):
        try:
            for i in range(60):
                assert client.get("/livez").status_code == 200
                assert client.get("/metrics", headers={"x-forwarded-for": f"10.{n}.{i // 250}.{i % 250}"}).status_code < 500
        except Exception as exc:  # noqa: BLE001 -- isolate optional engine or worker failure at boundary
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(16)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors and len(s._rate_limit_buckets) <= 50


def test_probes_exempt_from_rate_limit(monkeypatch):
    _reset_buckets()
    monkeypatch.setattr(s, "_RATE_LIMIT_PER_MIN", 1)
    for _ in range(20):
        assert client.get("/livez").status_code == 200
        assert client.get("/healthz").status_code == 200


def test_cors_default_deny():
    # No CORSMiddleware installed by default => no ACAO header ever leaks.
    r = client.get("/healthz", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}
    assert s._cors_origins() == []


def test_cors_wildcard_rejected(monkeypatch):
    monkeypatch.setenv("AXIOM_CORS_ORIGINS", "*, https://app.example")
    assert s._cors_origins() == ["https://app.example"]


def test_json_log_formatter_emits_single_line_json():
    rec = logging.LogRecord("overlay.server", logging.WARNING, __file__, 1, "hello %s", ("world",), None)
    rec.request_id = "abc"
    out = JsonLogFormatter().format(rec)
    assert "\n" not in out
    doc = json.loads(out)
    assert doc["msg"] == "hello world" and doc["level"] == "WARNING" and doc["request_id"] == "abc"
    assert doc["ts"].endswith("Z") and doc["service"] == "axiom-grid-overlay"


def test_json_logging_configured_on_root():
    assert any(isinstance(h.formatter, JsonLogFormatter) for h in logging.getLogger().handlers)


def test_readyz_failure_does_not_leak_internals(monkeypatch):
    monkeypatch.setattr(s, "_readyz_probe_ok", threading.Event())

    def boom(_path):
        raise RuntimeError("secret db password in traceback")

    monkeypatch.setattr(s, "_run_readyz_probe", boom)
    r = client.get("/readyz")
    assert r.status_code == 503
    assert r.json() == {"status": "not_ready", "error": "RuntimeError"}
    assert "password" not in r.text
