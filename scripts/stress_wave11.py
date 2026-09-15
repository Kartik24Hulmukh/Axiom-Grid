"""Bounded loopback spike/short-memory observation; no external model calls.
Run: python3 scripts/stress_wave11.py
This is not a production capacity or long-duration leak certification.
"""
import concurrent.futures
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from collections import Counter

import psutil


def main():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "AXIOM_REQUIRE_AUTH": "1", "AXIOM_API_KEYS": "wave11-local-test-only", "AXIOM_LOG_QUEUE_MAX": "32"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "overlay.server:app", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    base = f"http://127.0.0.1:{port}"
    results = []
    dropped = None
    shutdown_timed_out = False
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(base + "/healthz", timeout=0.2):
                    break
            except OSError:
                if proc.poll() is not None:
                    raise RuntimeError("server exited before readiness") from None
                time.sleep(0.05)
        else:
            raise RuntimeError("server start deadline exceeded")
        monitor = psutil.Process(proc.pid)
        def request(_):
            start = time.perf_counter()
            try:
                with urllib.request.urlopen(base + "/healthz", timeout=3) as response:
                    status = response.status
                    response.read()
            except OSError:
                status = 0
            return status, (time.perf_counter() - start) * 1000
        for batch in range(4):
            start = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=40) as pool:
                measurements = list(pool.map(request, range(500)))
            elapsed = time.perf_counter() - start
            latencies = sorted(latency for _, latency in measurements)
            results.append({"batch": batch, "requests": 500, "concurrency": 40, "rps": round(500/elapsed, 2), "p50_ms": round(latencies[249], 2), "p95_ms": round(latencies[474], 2), "p99_ms": round(latencies[494], 2), "statuses": dict(Counter(status for status, _ in measurements)), "rss_bytes": monitor.memory_info().rss})
        req = urllib.request.Request(base + "/metrics", headers={"Authorization": "Bearer wave11-local-test-only"})
        with urllib.request.urlopen(req, timeout=3) as response:
            dropped = json.load(response).get("log_dropped_total")
    finally:
        start = time.perf_counter()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            shutdown_timed_out = True
        shutdown = time.perf_counter() - start
        proc.stderr.close()
        proc.stdout.close()
    output = {"workload": "healthz only, undrained stdout and stderr, 4x500 requests; batch0 warmup", "batches": results, "shutdown_s": round(shutdown, 3), "shutdown_timed_out": shutdown_timed_out, "log_dropped_total": dropped, "rss_growth_after_warmup_bytes": results[-1]["rss_bytes"]-results[0]["rss_bytes"]}
    print(json.dumps(output, indent=2))
    # Provisional LOCAL gates only; not a substitute for workload-specific SLOs.
    assert not shutdown_timed_out, "shutdown exceeded 5 seconds"
    assert all(row["statuses"] == {200: 500} and row["p99_ms"] < 500 for row in results)
    assert output["rss_growth_after_warmup_bytes"] < 32 * 1024 * 1024


if __name__ == "__main__":
    main()
