"""The benchmark must never certify an HTTP failure as availability."""
import io
import json
from urllib.error import HTTPError

import pytest

from scripts import bench_v1_prod as bench


@pytest.mark.parametrize("status, expected_exit", [(200, 0), (404, 1), (429, 1), (503, 1), (0, 1)])
def test_benchmark_gate_checks_http_success(monkeypatch, capsys, status, expected_exit):
    class Process:
        pid = 1
        def terminate(self):
            pass
        def wait(self, timeout=None):
            pass
        def poll(self):
            return 0
    monkeypatch.setattr(bench.subprocess, "Popen", lambda *a, **kw: Process())
    monkeypatch.setattr(bench, "_rss_bytes", lambda pid: 1000)
    monkeypatch.setattr(bench.sys, "argv", ["bench", "10", "1"])
    monkeypatch.setattr(bench, "_hit", lambda base, i, *paths: (1.0, status if paths else 200))
    assert bench.main() == expected_exit
    report = json.loads(capsys.readouterr().out)
    assert report["slo_pass"] == (status == 200)


def test_http_error_response_closed(monkeypatch):
    body = io.BytesIO(b"denied")
    error = HTTPError("http://localhost", 429, "limited", {}, body)
    def fail(*a, **kw):
        raise error
    monkeypatch.setattr(bench.urllib.request, "urlopen", fail)
    assert bench._hit("http://localhost", 0)[1] == 429
    assert body.closed
