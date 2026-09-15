#!/usr/bin/env python3
"""Multi-process load generator (defeats client-side GIL) for scaleout_bench servers.

Usage: python3 bench/scaleout_bench_mp.py --workers 1 4 --procs 8 --threads 16 --requests 4000
Each client process runs its own thread pool; results are merged. Same server harness as scaleout_bench.
"""
import argparse, json, os, sys, time, threading, urllib.request
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from scaleout_bench import ROUTES, wait_ready, peak_rss_mib
import subprocess

def client(args):
    port, n, threads, seed = args
    lat, errs, lock = [], [0], threading.Lock()
    def one(i):
        url = f"http://127.0.0.1:{port}{ROUTES[(i + seed) % len(ROUTES)]}"
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
    with ThreadPoolExecutor(max_workers=threads) as ex:
        list(ex.map(one, range(n)))
    return lat, errs[0]

def run(workers, procs, threads, requests, port):
    env = dict(os.environ, KAIRO_GATEWAY_TEST_MODE="true", KAIRO_AIR_GAP="true", AXIOM_REQUIRE_AUTH="0", PYTHONPATH=os.getcwd())
    cmd = [sys.executable, "-m", "uvicorn", "overlay.server:app", "--host", "127.0.0.1", "--port", str(port), "--workers", str(workers), "--log-level", "error"]
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_ready(port):
            return {"workers": workers, "error": "server never became ready"}
        per = requests // procs
        t0 = time.perf_counter()
        with Pool(procs) as pool:
            parts = pool.map(client, [(port, per, threads, i) for i in range(procs)])
        wall = time.perf_counter() - t0
        lat = sorted(x for p in parts for x in p[0]); errs = sum(p[1] for p in parts)
        q = lambda p: round(lat[min(len(lat) - 1, int(p * len(lat)))], 2)
        return {"workers": workers, "client_procs": procs, "threads_per_proc": threads, "concurrency": procs * threads, "requests": len(lat), "p50_ms": q(0.5), "p95_ms": q(0.95), "p99_ms": q(0.99), "max_ms": round(lat[-1], 2), "rps": round(len(lat) / wall, 1), "errors": errs, "peak_rss_mib_total": peak_rss_mib(proc.pid)}
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", nargs="+", type=int, default=[1, 4])
    ap.add_argument("--procs", type=int, default=8)
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--requests", type=int, default=4000)
    ap.add_argument("--port", type=int, default=8801)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    res = [run(w, a.procs, a.threads, a.requests, a.port + i) for i, w in enumerate(a.workers)]
    out = json.dumps({"cpu_count": os.cpu_count(), "python": sys.version.split()[0], "results": res}, indent=2)
    print(out)
    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        open(a.out, "w").write(out + "\n")
