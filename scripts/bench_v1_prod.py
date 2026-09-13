"""v1.0-PROD load harness: P50/P95/P99, throughput, RSS, SIGTERM time.

Usage: python3 scripts/bench_v1_prod.py [requests] [threads]
Boots uvicorn on a free port, hammers the probe + API surface with a
thread pool, prints a JSON report. Deterministic, no network egress.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATHS = ("/healthz", "/livez", "/readyz", "/metrics", "/api/health")


def _rss_bytes(pid: int) -> int:
    with open(f"/proc/{pid}/status", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    return 0


def _hit(base: str, i: int) -> tuple[float, int]:
    path = PATHS[i % len(PATHS)]
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(base + path, timeout=5) as r:
            status = r.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except OSError:
        status = 0
    return (time.perf_counter() - t) * 1000.0, status


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    threads = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    env = dict(os.environ, PYTHONPATH=ROOT)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "overlay.server:app", "--host", "127.0.0.1",
         "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(200):
            if _hit(base, 0)[1] == 200:
                break
            time.sleep(0.05)
        else:
            raise SystemExit("server did not boot")
        rss0 = _rss_bytes(proc.pid)
        t0 = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as pool:
            samples = list(pool.map(lambda i: _hit(base, i), range(n)))
        wall = time.perf_counter() - t0
        rss1 = _rss_bytes(proc.pid)
        lat = sorted(s[0] for s in samples)
        codes: dict[int, int] = {}
        for _, c in samples:
            codes[c] = codes.get(c, 0) + 1
        t1 = time.perf_counter()
        proc.terminate()
        proc.wait(10)
        report = {
            "requests": n, "threads": threads,
            "p50_ms": round(statistics.quantiles(lat, n=100)[49], 2),
            "p95_ms": round(statistics.quantiles(lat, n=100)[94], 2),
            "p99_ms": round(statistics.quantiles(lat, n=100)[98], 2),
            "throughput_rps": round(n / wall, 1),
            "status_codes": codes,
            "transport_errors": codes.get(0, 0),
            "rss_start_mib": round(rss0 / 2**20, 1),
            "rss_end_mib": round(rss1 / 2**20, 1),
            "sigterm_seconds": round(time.perf_counter() - t1, 3),
        }
        print(json.dumps(report, indent=2))
        return 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    raise SystemExit(main())
