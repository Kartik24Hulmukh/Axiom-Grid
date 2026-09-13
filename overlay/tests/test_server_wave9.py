"""Wave 9 regressions: OPS-006 non-blocking structured logging.

Root cause of the 2026-09-13 focused-runtime CI failure: JsonLogFormatter was
attached to a plain logging.StreamHandler writing synchronously to stderr.
When stderr is an undrained pipe (CI harness, `cmd | head`, supervisors) the
64 KiB pipe buffer fills and every request thread blocks in write(): the
serving path stalls on log I/O and SIGTERM graceful shutdown never runs
(proc.wait(5) -> subprocess.TimeoutExpired in scripts/stress_sec006_gauntlet.py).
Fix: bounded queue.Queue + daemon QueueListener; saturation sheds (counted),
never blocks.
"""
import logging
import os
import queue
import socket
import subprocess
import sys
import time
import urllib.request

from fastapi.testclient import TestClient

from overlay.server import LOG_DROPPED_TOTAL, _NonBlockingQueueHandler, app

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _rec(msg="x"):
    return logging.LogRecord("overlay.server", logging.INFO, __file__, 1, msg, None, None)


def test_root_logging_is_non_blocking_and_bounded():
    handlers = [h for h in logging.getLogger().handlers if isinstance(h, _NonBlockingQueueHandler)]
    assert handlers, "structured logging must route through the non-blocking queue handler"
    assert isinstance(handlers[0].queue, queue.Queue)
    assert handlers[0].queue.maxsize >= 1


def test_log_saturation_sheds_without_blocking_request_path():
    before = LOG_DROPPED_TOTAL["count"]
    h = _NonBlockingQueueHandler(queue.Queue(maxsize=1))
    h.queue.put_nowait(_rec("filler"))  # saturate the bounded queue
    t0 = time.perf_counter()
    for _ in range(200):
        h.emit(_rec("hot-path record"))
    dt = time.perf_counter() - t0
    assert dt < 0.5, "emit() blocked on a saturated log queue"
    assert LOG_DROPPED_TOTAL["count"] - before == 200


def test_metrics_expose_log_dropped_total():
    c = TestClient(app)
    data = c.get("/metrics").json()
    assert "log_dropped_total" in data
    prom = c.get("/metrics?format=prometheus").text
    assert "axiom_log_dropped_total" in prom


def test_log_io_never_blocks_serving_path_or_sigterm_shutdown():
    """Regression for the focused-runtime CI hang: undrained stderr pipe."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    env = dict(os.environ, PYTHONPATH=ROOT)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "overlay.server:app", "--host", "127.0.0.1",
         "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        for _ in range(100):
            try:
                urllib.request.urlopen(base + "/healthz", timeout=1).close()
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.1)
        else:
            raise AssertionError("server did not boot")
        statuses = set()
        for _ in range(400):  # >64 KiB of JSON log lines into an undrained pipe
            with urllib.request.urlopen(base + "/healthz", timeout=5) as r:
                statuses.add(r.status)
        assert statuses == {200}
        proc.terminate()
        proc.wait(5)  # precondition of the gauntlet harness; used to TimeoutExpired
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        if proc.stderr is not None:
            proc.stderr.close()
