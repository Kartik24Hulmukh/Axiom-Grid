"""Bounded loopback capacity comparison; no external model traffic."""
import concurrent.futures
import json
import math
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]


def main():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, AXIOM_API_KEYS="local-benchmark-only", AXIOM_REQUIRE_AUTH="1",
               AXIOM_RATE_LIMIT_PER_MIN_AUTH="100000", AXIOM_LOG_LEVEL="WARNING")
    server_log = tempfile.TemporaryFile(mode="w+t")  # noqa: SIM115 -- retained through child shutdown
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "overlay.server:app", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"], cwd=ROOT, env=env, stdout=server_log, stderr=server_log)
    base = f"http://127.0.0.1:{port}"
    def hit(_):
        start = time.perf_counter()
        req = urllib.request.Request(base + "/api/extract-document", data=json.dumps({"file": "fixtures/wedge/sample_memo_01.txt"}).encode(), headers={"Authorization": "Bearer local-benchmark-only", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                r.read()
                status = r.status
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
        except OSError:
            status = 0
        return status, (time.perf_counter() - start) * 1000
    report = {"method": "same process, 300 real document extraction requests per phase; loopback; 1 then 100 workers; nearest-rank percentiles; RSS sampled 5ms; no production capacity claim", "phases": []}
    try:
        deadline = time.monotonic() + 15
        while True:
            try:
                with urllib.request.urlopen(base + "/readyz", timeout=0.2) as r:
                    assert r.status == 200
                break
            except OSError:
                if proc.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("readiness deadline") from None
                threading.Event().wait(0.05)
        server = psutil.Process(proc.pid)
        for workers in (1, 100):
            rss = [server.memory_info().rss]
            stop = threading.Event()
            def sample(stop=stop, rss=rss):
                while not stop.wait(0.005):
                    rss.append(server.memory_info().rss)
            monitor = threading.Thread(target=sample)
            monitor.start()
            start = time.perf_counter()
            try:
                with concurrent.futures.ThreadPoolExecutor(workers) as pool:
                    results = list(pool.map(hit, range(300)))
            finally:
                stop.set()
                monitor.join()
            wall = time.perf_counter() - start
            counts = Counter(s for s, _ in results)
            lat = sorted(t for _, t in results)
            report["phases"].append({"workers": workers, "requests": 300, "status_counts": dict(counts), "throughput_rps": round(300/wall, 2), "useful_rps": round(counts[200]/wall, 2), "latency_ms": {f"p{n}": round(lat[math.ceil(n/100*len(lat))-1], 2) for n in (50,95,99)}, "rss_min_mib": round(min(rss)/2**20, 2), "rss_max_mib": round(max(rss)/2**20, 2)})
            assert counts[0] == 0 and all(s in (200, 503) for s in counts), counts
            assert counts[200] > 0
        with urllib.request.urlopen(base + "/readyz", timeout=2) as r:
            assert r.status == 200
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            raise
    server_log.seek(0)
    shutdown_log = server_log.read()
    server_log.close()
    report["shutdown_exit"] = proc.returncode
    report["shutdown_completed"] = "Application shutdown complete" in shutdown_log
    report["shutdown_note"] = "Uvicorn 0.51 re-raises SIGTERM after graceful lifespan shutdown; -15 is expected on POSIX. Require shutdown-complete log as independent evidence."
    print(json.dumps(report, indent=2))
    (ROOT / "docs/axiom/evidence/session10-ingress-benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
    assert proc.returncode in (0, -signal.SIGTERM)
    assert report["shutdown_completed"], "lifespan shutdown did not complete"


if __name__ == "__main__":
    main()
