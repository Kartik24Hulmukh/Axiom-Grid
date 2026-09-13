"""v1.0-PROD load harness: P50/P95/P99, throughput, RSS, SIGTERM time.

Usage: python3 scripts/bench_v1_prod.py [requests] [threads]
Boots uvicorn on a free port, hammers the probe + API surface with a
thread pool, prints a JSON report. Deterministic, no network egress.
"""
from __future__ import annotations

import argparse
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


def _hit(base: str, i: int, paths=PATHS) -> tuple[float, int]:
    path = paths[i % len(paths)]
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(base + path, timeout=5) as r:
            status = r.status
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
    except OSError:
        status = 0
    return (time.perf_counter() - t) * 1000.0, status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("requests", nargs="?", type=int, default=2000)
    parser.add_argument("threads", nargs="?", type=int, default=100)
    parser.add_argument("--paths", default=",".join(PATHS), help="Comma-separated paths; all must return 2xx")
    args = parser.parse_args()
    n, threads = args.requests, args.threads
    if n < 2 or not 1 <= threads <= 1000:
        parser.error("requests >= 2 and threads in 1..1000 required")
    paths = tuple(args.paths.split(","))
    if not paths or any(not p.startswith("/") or p.startswith("//") for p in paths):
        parser.error("paths must be local absolute paths")
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
            samples = list(pool.map(lambda i: _hit(base, i, paths), range(n)))
        wall = time.perf_counter() - t0
        rss1 = _rss_bytes(proc.pid)
        lat = sorted(s[0] for s in samples)
        codes: dict[int, int] = {}
        for _, c in samples:
            codes[c] = codes.get(c, 0) + 1
        t1 = time.perf_counter()
        proc.terminate()
        proc.wait(10)
        successes = sum(count for code, count in codes.items() if 200 <= code < 300)
        p95 = statistics.quantiles(lat, n=100)[94]
        p99 = statistics.quantiles(lat, n=100)[98]
        report = {
            "requests": n, "threads": threads, "paths": paths,
            "http_successes": successes, "http_errors": n - successes - codes.get(0, 0),
            "request_success_ratio": successes / n,
            "slo_pass": successes / n >= 0.9999 and p95 <= 120 and p99 <= 250,
            "scope": "short local HTTP workload, NOT uptime or 100x certification",
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
        return 0 if report["slo_pass"] else 1
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    raise SystemExit(main())
