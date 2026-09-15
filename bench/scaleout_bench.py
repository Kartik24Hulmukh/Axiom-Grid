#!/usr/bin/env python3
"""Honest scale-out benchmark: identical workload against N uvicorn workers.

Usage: python3 bench/scaleout_bench.py --workers 1 4 --requests 2000 --threads 100
Reports P50/P95/P99, RPS, errors and peak RSS (VmHWM summed over worker processes).
No mocks: real TCP, real uvicorn processes, real probe routes.
"""
import argparse, json, os, subprocess, sys, time, threading, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROUTES = ["/healthz", "/livez", "/readyz", "/metrics"]

def wait_ready(port, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1).status == 200:
                return True
        except Exception:
            time.sleep(0.2)
    return False

def peak_rss_mib(pid):
    total = 0.0
    kids = subprocess.run(["ps", "-o", "pid=", "--ppid", str(pid)], capture_output=True, text=True).stdout.split()
    for p in [pid] + [int(k) for k in kids]:
        try:
            for line in open(f"/proc/{p}/status"):
                if line.startswith("VmHWM"):
                    total += int(line.split()[1]) / 1024.0
        except Exception:
            pass
    return round(total, 1)

def run(workers, requests, threads, port):
    env = dict(os.environ, KAIRO_GATEWAY_TEST_MODE="true", KAIRO_AIR_GAP="true", AXIOM_REQUIRE_AUTH="0", PYTHONPATH=os.getcwd())
    cmd = [sys.executable, "-m", "uvicorn", "overlay.server:app", "--host", "127.0.0.1", "--port", str(port), "--workers", str(workers), "--log-level", "error"]
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_ready(port):
            return {"workers": workers, "error": "server never became ready"}
        lat, errs, lock = [], [0], threading.Lock()
        def one(i):
            url = f"http://127.0.0.1:{port}{ROUTES[i % len(ROUTES)]}"
            t = time.perf_counter()
            try:
                ok = 200 <= urllib.request.urlopen(url, timeout=10).status < 300
            except Exception:
                ok = False
            d = (time.perf_counter() - t) * 1000
            with lock:
                lat.append(d)
                if not ok:
                    errs[0] += 1
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=threads) as ex:
            list(ex.map(one, range(requests)))
        wall = time.perf_counter() - t0
        lat.sort()
        q = lambda p: round(lat[min(len(lat) - 1, int(p * len(lat)))], 2)
        return {"workers": workers, "requests": requests, "threads": threads, "p50_ms": q(0.50), "p95_ms": q(0.95), "p99_ms": q(0.99), "max_ms": round(lat[-1], 2), "rps": round(requests / wall, 1), "errors": errs[0], "peak_rss_mib_total": peak_rss_mib(proc.pid)}
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", nargs="+", type=int, default=[1, 4])
    ap.add_argument("--requests", type=int, default=2000)
    ap.add_argument("--threads", type=int, default=100)
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    results = [run(w, a.requests, a.threads, a.port + i) for i, w in enumerate(a.workers)]
    out = json.dumps({"cpu_count": os.cpu_count(), "python": sys.version.split()[0], "results": results}, indent=2)
    print(out)
    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        open(a.out, "w").write(out + "\n")
