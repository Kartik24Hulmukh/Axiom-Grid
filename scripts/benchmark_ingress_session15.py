"""Bounded real loopback extraction benchmark, no provider traffic."""
import concurrent.futures
import json
import os
import socket
import subprocess
import sys
import tempfile
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
    key = "session15-loopback-only"
    with tempfile.TemporaryDirectory() as state, tempfile.TemporaryFile() as logs:
        env = dict(os.environ, AXIOM_STATE_DIR=state, AXIOM_REQUIRE_AUTH="1",
                   AXIOM_API_KEYS=key, AXIOM_RATE_LIMIT_PER_MIN_AUTH="100000")
        proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "overlay.server:app",
                                 "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
                                cwd=ROOT, env=env, stdout=logs, stderr=logs)
        base = f"http://127.0.0.1:{port}"
        def hit(_):
            start = time.perf_counter()
            req = urllib.request.Request(base + "/api/extract-document",
                data=json.dumps({"file": "fixtures/wedge/sample_memo_01.txt"}).encode(),
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=20) as response:
                    response.read()
                    status = response.status
            except urllib.error.HTTPError as exc:
                status = exc.code
                exc.close()
            except (OSError, TimeoutError):
                status = "transport_error"
            return status, (time.perf_counter() - start) * 1000
        output = {"scope": "Same text fixture, one local uvicorn worker, fresh private state; 100 clients vs 1 is not 100x production load", "batches": []}
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(base + "/readyz", timeout=1):
                        break
                except OSError:
                    if proc.poll() is not None:
                        raise RuntimeError("server exited") from None
                    time.sleep(.1)
            else:
                raise RuntimeError("readiness timeout")
            process = psutil.Process(proc.pid)
            for clients, count in [(1, 60), (100, 100)]:
                rss = [process.memory_info().rss]
                start = time.perf_counter()
                results = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=clients) as pool:
                    futures = [pool.submit(hit, i) for i in range(count)]
                    for future in concurrent.futures.as_completed(futures):
                        results.append(future.result())
                        rss.append(process.memory_info().rss)
                wall = time.perf_counter() - start
                latency = sorted(value for _, value in results)
                statuses = Counter(str(status) for status, _ in results)
                output["batches"].append({"clients": clients, "requests": count,
                    "statuses": dict(statuses), "wall_s": round(wall, 3),
                    "p50_ms": round(latency[int(count*.5)], 3),
                    "p95_ms": round(latency[int(count*.95)], 3),
                    "p99_ms": round(latency[min(count-1, int(count*.99))], 3),
                    "throughput_rps": round(count/wall, 3),
                    "useful_rps": round(statuses["200"]/wall, 3),
                    "rss_floor_bytes": min(rss), "rss_ceiling_bytes": max(rss)})
        finally:
            start = time.perf_counter()
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            output["shutdown_s"] = round(time.perf_counter()-start, 3)
            output["exit_code"] = proc.returncode
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
