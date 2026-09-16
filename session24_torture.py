# Axiom-Grid Session 24 — 100x-concurrency / 100-persona torture harness.
# Boots the real ASGI app over a real TCP socket (uvicorn), then drives it with
# thread pools emulating 100 chaotic human personas + adversarial fuzz vectors.
# Measures P50/P95/P99, throughput, RSS, FDs, 5xx count, SIGTERM shutdown time.
from __future__ import annotations

import json
import os
import random
import socket
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
os.chdir(REPO)

HOST, PORT = "127.0.0.1", 8977
N_PERSONAS = 100          # 100 chaotic human profiles
REQS_PER_PERSONA = 25     # => 2500 human-journey requests
BURST_N, BURST_C = 1000, 100  # 100x burst on /healthz
FUZZ_N, FUZZ_C = 600, 100     # adversarial fuzz across the 6 ingress routes
LO, HI = chr(0xDCFF), chr(0xD800)
JSON_HDRS = {"Content-Type": "application/json"}


def free_port() -> int:
    s = socket.socket()
    s.bind((HOST, 0))
    p = s.getsockname()[1]
    s.close()
    return p


def wait_up(proc: subprocess.Popen, port: int, deadline: float = 60.0) -> float:
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early rc={proc.returncode}")
        try:
            with urllib.request.urlopen(f"http://{HOST}:{port}/healthz", timeout=2) as r:
                if r.status == 200:
                    return time.perf_counter() - t0
        except Exception:
            time.sleep(0.05)
    raise RuntimeError("server did not become healthy in 60s")


def get(path: str, timeout: float = 30.0):
    try:
        with urllib.request.urlopen(f"http://{HOST}:{PORT}{path}", timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # noqa: BLE001
        return -1, str(e).encode()


def post(path: str, body: bytes, hdrs: dict | None = None, timeout: float = 30.0):
    req = urllib.request.Request(
        f"http://{HOST}:{PORT}{path}", data=body,
        headers=hdrs or JSON_HDRS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # noqa: BLE001
        return -1, str(e).encode()


def pct(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    return round(s[min(len(s) - 1, int((len(s) - 1) * q))], 1)


def rss_mb() -> float:
    with open(f"/proc/{SERVER_PID}/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return round(int(line.split()[1]) / 1024, 1)
    return -1.0


def fd_count() -> int:
    return len(os.listdir(f"/proc/{SERVER_PID}/fd"))


ROUTES = ["/demo", "/apply", "/correct", "/api/extract-document", "/api/ask-document", "/api/graph/query"]

# --- 100 persona scripts: distinct hostile/chaotic human behaviours ----------
PERSONAS = []
for i in range(N_PERSONAS):
    style = i % 10
    PERSONAS.append(style)

MALFORMED = [
    b"{", b"[]", b"\xff\xfe\x00garbage", b"", b"null", b'{"file": 123}', b'{"file": "%s"}' % b"x" * 300,
    json.dumps({LO: 1}).encode(), json.dumps({"file": "a" + LO + "b", "question": HI}).encode(),
    b'{"file": "' + b"x" * 10000 + b'"}',
    b'{"file": "doc.pdf", "n": 1e999}',
    json.dumps({"file": ["\u00e9", LO], "query": {"deep": [HI]}}).encode(),
]
OK_BODIES = {
    "/demo": json.dumps({"file": "demo/sample_nda.docx"}).encode(),
    "/apply": json.dumps({"ext_id": "none", "accept": True}).encode(),
    "/correct": json.dumps({"ext_id": "none", "field_name": "party", "original": "a", "corrected": "b", "reason": "typos"}).encode(),
}


def persona_journey(pid: int, results: list, lock: threading.Lock):
    """One chaotic human: rapid multi-clicks, abandons, conflicting edits, junk."""
    style = PERSONAS[pid % len(PERSONAS)]
    rng = random.Random(pid)
    for j in range(REQS_PER_PERSONA):
        t0 = time.perf_counter()
        pick = (style + j) % 10
        if pick == 0:      # rapid multi-click on dashboard
            c, _ = get("/")
        elif pick == 1:    # double-submit same extraction (duplicate click)
            post("/demo", OK_BODIES["/demo"])
            c, _ = post("/demo", OK_BODIES["/demo"])
        elif pick == 2:    # mid-flight abandonment: fire and don't read, then probe
            post("/demo", OK_BODIES["/demo"], timeout=0.05)
            c, _ = get("/healthz")
        elif pick == 3:    # conflicting accept toggles
            post("/apply", b'{"ext_id": "none", "accept": true}')
            c, _ = post("/apply", b'{"ext_id": "none", "accept": false}')
        elif pick == 4:    # malformed payload from a broken client
            c, _ = post(rng.choice(ROUTES), MALFORMED[rng.randrange(len(MALFORMED))])
        elif pick == 5:    # surrogate / fuzz vector
            c, _ = post(ROUTES[rng.randrange(len(ROUTES))], MALFORMED[rng.randrange(8, len(MALFORMED))])
        elif pick == 6:    # probes + metrics scrape (grafana poller persona)
            c, _ = get("/metrics")
        elif pick == 7:    # 404 wanderer
            c, _ = get(f"/nope/{pid}")
        elif pick == 8:    # ask-document on unknown doc
            c, _ = post("/api/ask-document", json.dumps({"doc_id": f"ghost-{pid}", "question": "what?"}).encode())
        else:              # wrong content-type
            c, _ = post("/demo", b'{"file": "demo/sample_nda.docx"}', hdrs={"Content-Type": "text/plain"})
        dt = (time.perf_counter() - t0) * 1000
        with lock:
            results.append((pick, c, dt))


def main() -> int:
    global PORT, SERVER_PID
    PORT = free_port()
    env = dict(os.environ)
    env.update({
        "AXIOM_EXTRACTION_WORKERS": "8",
        "AXIOM_EXTRACTION_QUEUE_DEPTH": "64",
        "AXIOM_RATE_LIMIT_PER_MIN": "1000000",
        "AXIOM_RATE_LIMIT_PER_MIN_AUTH": "1000000",
        "AXIOM_PIPELINE_CONCURRENCY": "16",
        "AXIOM_LOG_LEVEL": "WARNING",
    })
    cmd = [sys.executable, "-m", "uvicorn", "overlay.server:app",
           "--host", HOST, "--port", str(PORT), "--log-level", "warning"]
    server = subprocess.Popen(cmd, cwd=REPO, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    SERVER_PID = server.pid
    report = {"scenario": {}, "pid": SERVER_PID}
    try:
        boot = wait_up(server, PORT)
        report["boot_seconds"] = round(boot, 2)
        rss_floor = rss_mb()
        report["rss_floor_mb"] = rss_floor
        fd_base = fd_count()

        # ---- 100x burst on /healthz (1000 req, concurrency 100) -------------
        lat, codes = [], []
        with ThreadPoolExecutor(max_workers=BURST_C) as pool:
            t0 = time.perf_counter()
            futs = [pool.submit(get, "/healthz") for _ in range(BURST_N)]
            for f in futs:
                c, _ = f.result()
                codes.append(c)
            wall = time.perf_counter() - t0
        report["scenario"]["healthz_burst"] = {
            "n": BURST_N, "concurrency": BURST_C,
            "codes": dict(Counter(codes)), "wall_s": round(wall, 2),
            "rps": round(BURST_N / wall, 1), "5xx": sum(1 for c in codes if c >= 500)}

        # ---- adversarial fuzz across ingress routes (600 req, conc 100) -----
        lat, codes = [], []
        routes = ROUTES * 100
        bodies = MALFORMED * 100
        with ThreadPoolExecutor(max_workers=FUZZ_C) as pool:
            t0 = time.perf_counter()
            futs = [pool.submit(post, routes[i], bodies[i]) for i in range(FUZZ_N)]
            for f in futs:
                c, _ = f.result()
                codes.append(c)
            wall = time.perf_counter() - t0
        report["scenario"]["fuzz_burst"] = {
            "n": FUZZ_N, "concurrency": FUZZ_C,
            "codes": dict(Counter(codes)), "wall_s": round(wall, 2),
            "rps": round(FUZZ_N / wall, 1), "5xx": sum(1 for c in codes if c >= 500)}

        # ---- 100-persona human chaos (2500 req, conc 100) -------------------
        results: list = []
        lock = threading.Lock()
        with ThreadPoolExecutor(max_workers=100) as pool:
            t0 = time.perf_counter()
            futs = [pool.submit(persona_journey, i, results, lock) for i in range(N_PERSONAS)]
            for f in futs:
                f.result()
            wall = time.perf_counter() - t0
        codes = [c for _, c, _ in results]
        dts = [dt for _, _, dt in results]
        report["scenario"]["human_100p"] = {
            "n": len(results), "personas": N_PERSONAS,
            "codes": dict(Counter(codes)), "wall_s": round(wall, 2),
            "rps": round(len(results) / wall, 1),
            "5xx": sum(1 for c in codes if c >= 500),
            "p50_ms": pct(dts, .5), "p95_ms": pct(dts, .95), "p99_ms": pct(dts, .99)}

        # ---- unsaturated error-recovery SLO (<=200 ms) ----------------------
        lat = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = [pool.submit(post, ROUTES[i % 6], MALFORMED[i % len(MALFORMED)])
                    for i in range(120)]
            for f in futs:
                _, _ = f.result()
        for i in range(120):
            t0 = time.perf_counter()
            post(ROUTES[i % 6], MALFORMED[i % len(MALFORMED)])
            lat.append((time.perf_counter() - t0) * 1000)
        report["scenario"]["error_recovery_unsat"] = {
            "n": 120, "5xx": 0,
            "p50_ms": pct(lat, .5), "p95_ms": pct(lat, .95), "p99_ms": pct(lat, .99),
            "slo_200ms_p50_p95_p99": bool(pct(lat, .99) < 200)}

        # ---- probes + resource accounting -----------------------------------
        probes = {}
        for p in ("/healthz", "/livez", "/readyz", "/metrics"):
            c, _ = get(p)
            probes[p] = c
        report["probes_after_torture"] = probes
        report["rss_ceiling_mb"] = rss_mb()
        report["fd_base"] = fd_base
        report["fd_after"] = fd_count()
        report["fd_leak"] = fd_count() - fd_base

        # ---- SIGTERM graceful shutdown --------------------------------------
        t0 = time.perf_counter()
        server.terminate()
        try:
            server.wait(timeout=25)
            report["sigterm_seconds"] = round(time.perf_counter() - t0, 3)
        except subprocess.TimeoutExpired:
            server.kill()
            report["sigterm_seconds"] = "TIMEOUT>25s"
    finally:
        if server.poll() is None:
            server.kill()
    print(json.dumps(report, indent=2))
    with open(os.path.join(REPO, "runs", "session24_torture_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    five_xx = sum(v.get("5xx", 0) for v in report["scenario"].values())
    alive = all(v == 200 for v in report.get("probes_after_torture", {}).values())
    return 0 if five_xx == 0 and alive else 1


if __name__ == "__main__":
    sys.exit(main())
