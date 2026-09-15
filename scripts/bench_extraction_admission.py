"""Real loopback extraction contention; synthetic fixtures, no provider egress.
100 clients is NOT 100x business load. Client/server share a host.
"""
import concurrent.futures
import json
import os
import socket
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter

import psutil


def main():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "AXIOM_REQUIRE_AUTH": "1", "AXIOM_API_KEYS": "admission-local-only-key",
           "AXIOM_RATE_LIMIT_PER_MIN": "100000", "AXIOM_RATE_LIMIT_PER_MIN_AUTH": "100000"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "overlay.server:app", "--host", "127.0.0.1",
                             "--port", str(port), "--no-access-log"], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    stop = threading.Event()
    rss = []
    monitor = None
    shutdown_timed_out = False
    def sample_memory():
        process = psutil.Process(proc.pid)
        while not stop.is_set():
            try:
                value = process.memory_info().rss
                if value > 0:  # exited/zombie processes report zero, not a RAM floor
                    rss.append(value)
            except psutil.NoSuchProcess:
                return
            stop.wait(0.02)
    def hit(i):
        case = i % 10
        payload = {"file": "sample_memo_01.txt"} if case < 8 else {"file": "" if case == 8 else "missing-probe.txt"}
        request = urllib.request.Request(base + "/api/extract-document", json.dumps(payload).encode(),
                  {"Content-Type": "application/json", "Authorization": "Bearer admission-local-only-key"})
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                status, body = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, body = error.code, error.read()
            error.close()
        except OSError:
            status, body = 0, b""
        valid = status != 200 or bool(json.loads(body).get("fields"))
        shed = status == 503 and b"Extraction capacity saturated" in body
        return status, (time.perf_counter()-started)*1000, valid, shed
    try:
        deadline = time.monotonic()+15
        while True:
            try:
                with urllib.request.urlopen(base+"/readyz", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                if proc.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("startup failed") from None
                stop.wait(0.05)
        monitor = threading.Thread(target=sample_memory)
        monitor.start()
        started = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(100) as pool:
            samples = list(pool.map(hit, range(1000)))
        duration = time.perf_counter()-started
        try:
            with urllib.request.urlopen(base+"/healthz", timeout=2) as response:
                healthy = response.status == 200
        except OSError:
            healthy = False
        started = time.perf_counter()
        proc.terminate()
        try:
            exit_code = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            shutdown_timed_out = True
            proc.kill()
            exit_code = proc.wait()
        shutdown = time.perf_counter()-started
    finally:
        stop.set()
        if monitor:
            monitor.join(2)
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    def percentiles(rows):
        lat = sorted(rows)
        return {f"p{p}_ms": round(lat[min(len(lat)-1, int(len(lat)*p/100))],2) for p in [50,95,99]} if lat else {}
    statuses = dict(Counter(s[0] for s in samples))
    unexpected = sum(s[0] not in (200,404,422,503) or (s[0] == 503 and not s[3]) or not s[2] for s in samples)
    result = {"scope": "co-located real HTTP/extraction, one uvicorn worker; not a 100x certification",
        "requests":1000,"concurrency":100,"statuses":statuses,
        "unexpected":unexpected,"healthy_after":healthy,"shutdown_timed_out":shutdown_timed_out,"server_exit":exit_code,"shutdown_seconds":round(shutdown,3),
        "throughput_rps":round(len(samples)/duration,2),"successful_extractions_rps":round(statuses.get(200,0)/duration,2),
        "latency_all":percentiles([s[1] for s in samples]),"latency_success":percentiles([s[1] for s in samples if s[0]==200]),
        "latency_shed":percentiles([s[1] for s in samples if s[3]]),
        "rss_sample_floor_mib":round(min(rss)/2**20,2),"rss_sample_peak_mib":round(max(rss)/2**20,2),"rss_sample_interval_ms":20}
    print(json.dumps(result,indent=2))
    return int(unexpected != 0 or not healthy or exit_code not in (0, -signal.SIGTERM) or shutdown_timed_out or statuses.get(200,0) == 0)


if __name__ == "__main__":
    raise SystemExit(main())
