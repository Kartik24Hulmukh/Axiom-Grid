"""Actual loopback HTTP gateway faults; no mocked transport or paid provider."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from kernel.sidecar.melious_router import MeliousModelRouter, RouterError


@pytest.fixture
def gateway(monkeypatch):
    monkeypatch.setenv("MELIOUS_API_KEY", "local-network-test-only")
    calls = []
    redirect_hits = []
    lock = threading.Lock()
    mode = {"redirect": False, "all_fail": False}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            redirect_hits.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()
        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            with lock:
                calls.append(data["model"])
            assert self.headers["Authorization"] == "Bearer local-network-test-only"
            if mode["redirect"]:
                self.send_response(302)
                self.send_header("Location", "/credential-sink")
                self.end_headers()
                return
            model = data["model"]
            status = 503 if mode["all_fail"] else 429 if model == "glm-5.3" else 503 if model == "glm-5.3-flash" else 200
            body = json.dumps({"choices": [{"message": {"content": "local HTTP answer"}}],
                               "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            if status == 429:
                self.send_header("Retry-After", "60")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", calls, redirect_hits, mode
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        assert not worker.is_alive()


def test_real_http_429_503_failover_and_route_cooldown(gateway):
    base, calls, _, _ = gateway
    router = MeliousModelRouter(base_url=base, max_retries=0)
    result = router.complete([{"role": "user", "content": "test"}], max_tokens=16)
    assert result["router"]["selected_model"] == "kimi-k3"
    assert calls == ["glm-5.3", "glm-5.3-flash", "kimi-k3"]
    router.complete([{"role": "user", "content": "test"}], max_tokens=16)
    assert calls.count("glm-5.3") == 1  # cooldown does not sleep scarce workers
    assert router.get_metrics()["total_tokens"] == 10


def test_real_http_qwen_route(gateway):
    base, calls, _, _ = gateway
    router = MeliousModelRouter(models=("qwen3.8-27b",), base_url=base)
    assert router.complete([{"role": "user", "content": "test"}], max_tokens=16)["router"]["selected_model"] == "qwen3.8-27b"
    assert calls == ["qwen3.8-27b"]


def test_bearer_never_follows_redirect(gateway):
    base, _, hits, mode = gateway
    mode["redirect"] = True
    router = MeliousModelRouter(models=("kimi-k3",), base_url=base, max_retries=0)
    with pytest.raises(RouterError):
        router.complete([{"role": "user", "content": "test"}], max_tokens=16)
    assert hits == []
    assert router.get_metrics()["spend_reserved"] == 0


def test_100_callers_failure_cascade_returns_all_permits(gateway):
    base, _, _, mode = gateway
    mode["all_fail"] = True
    router = MeliousModelRouter(base_url=base, max_retries=0, timeout=1,
                               total_timeout=2, max_inflight=16)
    def call(_):
        try:
            router.complete([{"role": "user", "content": "test"}], max_tokens=16)
        except RouterError:
            return "refused"
        return "unexpected_success"
    with ThreadPoolExecutor(max_workers=100) as pool:
        outcomes = list(pool.map(call, range(200)))
    assert set(outcomes) == {"refused"}
    assert router.get_metrics()["spend_reserved"] == 0
    permits = [router._slots.acquire(blocking=False) for _ in range(16)]
    assert all(permits)
    assert not router._slots.acquire(blocking=False)
    for _ in permits:
        router._slots.release()


@pytest.mark.parametrize("url", ["http://remote.example/v1", "https://user:secret@example.com/v1",
                                "https://example.com/v1?token=bad", "file:///etc/passwd",
                                "https://example.com/v1#fragment"])
def test_credential_destination_configuration_fails_closed(url):
    with pytest.raises(RouterError, match="gateway URL"):
        MeliousModelRouter(base_url=url)