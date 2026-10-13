"""Offline operator gates and two small real loopback boundary oracles."""
import json
import http.client
from concurrent.futures import ThreadPoolExecutor
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scripts.gateway_operator_preflight import catalog_matches, evaluate, main, safe_origin
from kernel.sidecar.melious_router import MeliousModelRouter, RouterError


def configured():
    return {"MELIOUS_BASE_URL": "https://provider.example/v1", "MELIOUS_MODELS": "exact-a,exact-b",
            "MELIOUS_PREFLIGHT_ALLOWED_ORIGINS": "https://provider.example",
            "MELIOUS_API_KEY": "fixture-private-sentinel", "MELIOUS_TOKEN_CEILING": "100"}


@pytest.mark.parametrize("url", ["http://provider.example/v1", "https://localhost/v1",
    "https://127.0.0.1/v1", "https://10.1.1.1/v1", "https://169.254.169.254/v1",
    "https://user:secret@provider.example/v1", "https://provider.example/v1?secret=x",
    "https://provider.example/v1#x", "https://provider.example:444/v1",
    "https://provider.example/%2e%2e", "https://provider.example/../v1",
    "https://provider.example\\@evil.example/v1", "https://provider.example/\n"])
def test_url_screen_rejects_unsafe_forms(url):
    with pytest.raises(ValueError):
        safe_origin(url)


def test_offline_and_live_never_resolve_or_dispatch(monkeypatch, tmp_path):
    def forbidden(*a, **kw):
        raise AssertionError("network operation forbidden")
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"data": [{"id": "exact-a"}, {"id": "exact-b"}]}))
    for live in (False, True):
        report = evaluate(configured(), live=live, catalog_file=str(path))
        assert report["local_catalog_exact_match"]
        assert report["decision"] == "BLOCKED"
        assert report["outbound_call_limit"] == report["outbound_calls"] == report["maximum_script_spend"] == 0
        assert "fixture-private-sentinel" not in json.dumps(report)
        assert "provider.example" not in json.dumps(report)


@pytest.mark.parametrize("catalog", [{"data": [{"id": "exact-a"}, {"id": "alias-b"}]},
    {"data": [{"id": "exact-a"}, {"id": "exact-a"}]}, {"data": [{"id": 7}]},
    {"data": []}, [], None])
def test_catalog_does_not_translate_aliases_or_accept_malformed(tmp_path, catalog):
    path = tmp_path / "catalog"
    path.write_text(json.dumps(catalog))
    assert not catalog_matches(str(path), ("exact-a", "exact-b"))


def test_catalog_is_bounded_regular_file_without_symlinks(tmp_path):
    path = tmp_path / "catalog"
    path.write_text("x" * 65537)
    assert not catalog_matches(str(path), ("a",))
    link = tmp_path / "link"
    link.symlink_to(path)
    assert not catalog_matches(str(link), ("a",))
    assert not catalog_matches(str(tmp_path), ("a",))


@pytest.mark.parametrize("change,gate", [({"MELIOUS_MODELS": "glm-5.3, kimi-k3"}, "explicit_exact_model_ids_required"),
    ({"MELIOUS_BASE_URL": "https://unapproved.example/v1"}, "https_destination_and_exact_origin_allowlist_required"),
    ({"HTTPS_PROXY": "http://fixture-secret@proxy.example"}, "ambient_proxy_configuration_requires_operator_review"),
    ({"MELIOUS_TOKEN_CEILING": "10001"}, "bounded_local_token_admission_required"),
    ({"MELIOUS_TOKEN_CEILING": "nan"}, "bounded_local_token_admission_required")])
def test_env_gate_is_failclosed_and_redacted(change, gate):
    env = configured()
    env.update(change)
    report = evaluate(env)
    assert gate in report["gates"]
    assert "fixture-secret" not in json.dumps(report)


def test_cli_does_not_echo_bad_argument(capsys):
    with pytest.raises(SystemExit):
        main(["--fixture-private-sentinel"])
    output = capsys.readouterr()
    assert "fixture-private-sentinel" not in output.err + output.out


@pytest.mark.parametrize("mode", ["redirect", "missing_usage"])
def test_actual_loopback_redirect_and_unknown_billing(monkeypatch, mode):
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            calls.append(self.path)
            body = json.dumps({"model": "exact-a", "choices": [{"message": {"content": "ok"}}]}).encode()
            self.send_response(302 if mode == "redirect" else 200)
            self.send_header("Location", "/must-not-follow")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    monkeypatch.setenv("MELIOUS_API_KEY", "loopback-only-fixture")
    for key in ("MELIOUS_SPEND_LEDGER", "MELIOUS_MODEL_TIMEOUTS", "MELIOUS_TOKEN_CEILING"):
        monkeypatch.delenv(key, raising=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        router = MeliousModelRouter(models=("exact-a",), max_retries=0, spend_ceiling=10,
                                    base_url=f"http://127.0.0.1:{server.server_port}/v1")
        if mode == "redirect":
            with pytest.raises(RouterError):
                router.complete([{"role": "user", "content": "x"}], max_tokens=4)
        else:
            router.complete([{"role": "user", "content": "x"}], max_tokens=4)
        assert calls == ["/v1/chat/completions"]
        # Missing usage and HTTP error bodies give no billable evidence. Zero
        # local accounting here MUST NOT be promoted into a free-call claim.
        assert router.spend.snapshot()["spend_committed"] == 0
        assert router.spend.snapshot()["spend_reserved"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
        assert not thread.is_alive()


def test_duplicate_catalog_json_keys_are_not_accepted(tmp_path):
    path = tmp_path / "catalog"
    path.write_text('{"data": [], "data": [{"id": "a"}]}')
    assert not catalog_matches(str(path), ("a",))


@pytest.mark.parametrize("phase", ["dns", "connect"])
def test_pre_watchdog_work_is_not_hard_interrupted(monkeypatch, phase):
    """Injected bounded hold, NOT a real stalled resolver/TCP/TLS experiment."""
    entered, release, cancel = threading.Event(), threading.Event(), threading.Event()
    def held(*args, **kw):
        entered.set()
        assert release.wait(2)
        raise TimeoutError("fixture-only hold")
    if phase == "dns":
        monkeypatch.setattr(socket, "getaddrinfo", held)
    else:
        monkeypatch.setattr(http.client.HTTPConnection, "connect", held)
    monkeypatch.setenv("MELIOUS_API_KEY", "loopback-only-fixture")
    for key in ("MELIOUS_SPEND_LEDGER", "MELIOUS_MODEL_TIMEOUTS", "MELIOUS_TOKEN_CEILING"):
        monkeypatch.delenv(key, raising=False)
    router = MeliousModelRouter(models=("a",), base_url="http://127.0.0.1:1/v1",
                                timeout=.03, total_timeout=.03, max_retries=0)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(router.complete, [{"role": "user", "content": "x"}],
                             max_tokens=4, cancel_event=cancel)
        try:
            assert entered.wait(1)
            cancel.set()
            # The call remains held past its total deadline because the socket
            # watchdog starts only AFTER connect returns. No credentials sent.
            assert not release.wait(.08)
            assert not future.done()
            assert router.spend.snapshot()["spend_reserved"] > 0
        finally:
            release.set()
        with pytest.raises(RouterError, match="cancel"):
            future.result(timeout=1)
    assert router.spend.snapshot()["spend_reserved"] == 0
