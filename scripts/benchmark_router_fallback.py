"""Local synthetic transport, real router backoff. Never calls a model API.
Compare a git revision to the working tree; 100 simultaneously admitted calls.
"""
import concurrent.futures
import json
import math
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kernel.sidecar import melious_router as current  # noqa: E402


def measure(module, status):
    gate = threading.Barrier(100)
    upstream_gate = threading.Barrier(100)
    first_attempts = set()
    counts = {"attempts": 0}
    guard = threading.Lock()
    def transport(model, payload, timeout):
        with guard:
            counts["attempts"] += 1
        if model == "bad":
            caller = threading.get_ident()
            with guard:
                first = caller not in first_attempts
                first_attempts.add(caller)
            if first:
                upstream_gate.wait(timeout=10)
            exc = module.RouterError("synthetic upstream failure")
            exc.status, exc.retry_after = status, 1
            raise exc
        return {"choices": [{"message": {"content": "OK"}}]}
    router = module.MeliousModelRouter(models=("bad", "good"),
                                      transport=transport, max_inflight=100)
    # Raise threshold so every concurrent caller exercises response handling,
    # not merely a warm OPEN-circuit skip. The normal threshold has its own tests.
    router.breakers["bad"].failure_threshold = 10000
    process = psutil.Process()
    rss = [process.memory_info().rss]
    stop = threading.Event()
    def sample():
        while not stop.wait(0.005):
            rss.append(process.memory_info().rss)
    monitor = threading.Thread(target=sample)
    monitor.start()
    def one(_):
        gate.wait(timeout=10)
        start = time.perf_counter()
        out = router.complete([{"role": "user", "content": "x"}], max_tokens=8)
        assert out["router"]["selected_model"] == "good"
        return (time.perf_counter() - start) * 1000
    start = time.perf_counter()
    try:
        with concurrent.futures.ThreadPoolExecutor(100) as pool:
            lat = sorted(pool.map(one, range(100)))
    finally:
        stop.set()
        monitor.join()
    wall = time.perf_counter() - start
    rss.append(process.memory_info().rss)
    return {"status": status, "requests": 100, "workers": 100,
            "throughput_rps": round(100 / wall, 2), "wall_s": round(wall, 4),
            "latency_ms": {f"p{n}": round(lat[math.ceil(n / 100 * len(lat)) - 1], 3) for n in (50, 95, 99)},
            "rss_min_mib": round(min(rss) / 2**20, 2), "rss_max_mib": round(max(rss) / 2**20, 2),
            "attempts": counts["attempts"], "max_latency_ms": round(max(lat), 3), "errors": 0}


def main():
    rev = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    old = types.ModuleType("baseline_router")
    sys.modules[old.__name__] = old
    source = subprocess.check_output(["git", "show", f"{rev}:kernel/sidecar/melious_router.py"], cwd=ROOT, text=True)
    exec(compile(source, "baseline_router.py", "exec"), old.__dict__)
    report = {"method": "100-worker barrier, real sleeps, synthetic 429/503 then healthy fallback; nearest-rank percentiles; process RSS sampled every 5ms; thread startup included in throughput", "baseline_revision": rev,
              "before": [measure(old, s) for s in (429, 503)],
              "after": [measure(current, s) for s in (429, 503)]}
    print(json.dumps(report, indent=2))
    (ROOT / "docs/axiom/evidence/session10-router-benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
    assert all(row["latency_ms"]["p99"] < 200 for row in report["after"])


if __name__ == "__main__":
    main()
