"""SEC-006 live-socket gauntlet: boots the real uvicorn server with API-key auth
enabled and bombards it with mixed hostile/legit traffic from N threads.
Usage: python scripts/stress_sec006_gauntlet.py [requests] [threads]"""
import json, os, subprocess, sys, time, threading, socket, collections
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 400
T = int(sys.argv[2]) if len(sys.argv) > 2 else 40
KEY = "ag_live_tenant_key_0123456789abcdef"
KEY2 = "ag_live_tenant_two_fedcba9876543210"
UP = chr(46) * 2 + "/"  # path traversal segment, built at runtime

s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
env = dict(os.environ, AXIOM_API_KEYS=f"{KEY},{KEY2}", AXIOM_REQUIRE_AUTH="1",
           AXIOM_RATE_LIMIT_PER_MIN="120", AXIOM_RATE_LIMIT_PER_MIN_AUTH="100000", PYTHONPATH=ROOT)
proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "overlay.server:app", "--host", "127.0.0.1",
                         "--port", str(PORT), "--log-level", "warning"], cwd=ROOT, env=env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
base = f"http://127.0.0.1:{PORT}"
for _ in range(100):
    try:
        urllib.request.urlopen(base + "/healthz", timeout=1); break
    except Exception: time.sleep(0.1)
else:
    print(proc.stderr.read().decode()); sys.exit("server did not boot")

def hit(method, path, headers=None, body=None):
    req = urllib.request.Request(base + path, method=method, headers=headers or {},
                                 data=json.dumps(body).encode() if body is not None else None)
    if body is not None: req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r: return r.status
    except urllib.error.HTTPError as e: return e.code
    except Exception as e: return f"ERR:{type(e).__name__}"

auth = {"Authorization": f"Bearer {KEY}"}
auth2 = {"X-API-Key": KEY2}
scenarios = [
    ("probe_healthz", lambda i: hit("GET", "/healthz")),
    ("probe_readyz", lambda i: hit("GET", "/readyz")),
    ("anon_metrics", lambda i: hit("GET", "/metrics")),
    ("bruteforce", lambda i: hit("GET", "/metrics", {"Authorization": f"Bearer guess_{i}_0123456789abcdef"})),
    ("tenant1_metrics", lambda i: hit("GET", "/metrics", auth)),
    ("tenant2_metrics", lambda i: hit("GET", "/metrics", auth2)),
    ("tenant1_traversal", lambda i: hit("POST", "/demo", auth, {"file": UP * 3 + "etc/passwd", "question": "x"})),
    ("anon_demo", lambda i: hit("POST", "/demo", None, {"file": "x.txt", "question": "x"})),
    ("tenant1_bad_schema", lambda i: hit("POST", "/api/extract-document", auth, {"nope": 1})),
    ("bad_origin", lambda i: hit("GET", "/metrics", {**auth, "Origin": "https://evil.example"})),
]
results = collections.defaultdict(collections.Counter)
lat = []
lock = threading.Lock()
def worker(i):
    name, fn = scenarios[i % len(scenarios)]
    t0 = time.perf_counter(); sc = fn(i); dt = (time.perf_counter() - t0) * 1000
    with lock: results[name][sc] += 1; lat.append(dt)
t0 = time.perf_counter()
with ThreadPoolExecutor(T) as ex: list(ex.map(worker, range(N)))
wall = time.perf_counter() - t0
proc.terminate(); proc.wait(5)
lat.sort()
report = {"requests": N, "threads": T, "wall_s": round(wall, 3), "rps": round(N / wall, 1),
          "p50_ms": round(lat[len(lat)//2], 2), "p99_ms": round(lat[int(len(lat)*0.99)], 2),
          "transport_errors": sum(v for c in results.values() for k, v in c.items() if isinstance(k, str)),
          "by_scenario": {k: dict(v) for k, v in results.items()}}
print(json.dumps(report, indent=2))
# invariants (fail the gauntlet if any auth leak is observed)
assert set(results["anon_metrics"]) <= {401, 429}, "anon reached protected route"
assert set(results["anon_demo"]) <= {401, 429}, "anon reached mutating route"
assert set(results["bruteforce"]) <= {401, 429}, "brute-force key accepted"
assert set(results["probe_healthz"]) == {200}, "probe throttled or gated"
assert set(results["tenant1_metrics"]) == {200}, "valid tenant denied"
assert set(results["tenant2_metrics"]) == {200}, "second tenant denied"
assert set(results["tenant1_traversal"]) <= {404, 422}, "traversal not rejected"
assert set(results["bad_origin"]) == {403}, "origin gate bypassed by valid key"
assert report["transport_errors"] == 0
print("GAUNTLET PASS: all SEC-006 invariants held under concurrency")
