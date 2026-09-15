"""Offline paired router microbenchmark; no provider calls or capacity claims.
Run from repository root: python3 scripts/benchmark_router_accounting.py
"""
import concurrent.futures
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import threading
import time

import psutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kernel.sidecar import melious_router as current


def load_baseline():
    source = subprocess.check_output(
        ["git", "show", "8c315ed:kernel/sidecar/melious_router.py"], cwd=ROOT)
    with tempfile.TemporaryDirectory() as folder:
        path = pathlib.Path(folder) / "baseline.py"
        path.write_bytes(source)
        spec = importlib.util.spec_from_file_location("router_baseline", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module


def bench(module, fault, concurrency):
    calls = 0
    guard = threading.Lock()
    def transport(model, payload, timeout):
        nonlocal calls
        with guard:
            calls += 1
        if model == "bad":
            exc = module.RouterError("injected fault")
            exc.status = fault
            raise exc
        return {"choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}}
    router = module.MeliousModelRouter(models=["bad", "good"], max_retries=0,
                                      max_inflight=100, transport=transport)
    process = psutil.Process()
    rss = [process.memory_info().rss]
    latencies = []
    errors = []
    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        for _ in range(10):
            barrier = threading.Barrier(concurrency, timeout=10)
            def worker(_, barrier=barrier):
                barrier.wait()
                t0 = time.perf_counter()
                try:
                    router.complete([{"role": "user", "content": "hi"}], max_tokens=4)
                    return (time.perf_counter() - t0) * 1000, None
                except Exception as exc:  # noqa: BLE001 -- report arbitrary benchmark failures
                    return (time.perf_counter() - t0) * 1000, type(exc).__name__
            for latency, error in pool.map(worker, range(concurrency)):
                latencies.append(latency)
                if error:
                    errors.append(error)
            rss.append(process.memory_info().rss)
    duration = time.perf_counter() - start
    latencies.sort()
    result = {"fault": fault, "concurrency": concurrency, "requests": len(latencies),
              "errors": errors, "transport_calls": calls,
              "p50_ms": latencies[int(len(latencies) * .50)],
              "p95_ms": latencies[int(len(latencies) * .95)],
              "p99_ms": latencies[min(len(latencies)-1, int(len(latencies) * .99))],
              "throughput_rps": len(latencies) / duration,
              "rss_floor_bytes": min(rss), "rss_ceiling_bytes": max(rss),
              "committed": router.spend.snapshot()["spend_committed"],
              "reserved": router.spend.snapshot()["spend_reserved"]}
    assert not errors and result["reserved"] == 0
    assert result["committed"] == 8 * len(latencies)
    return result


if __name__ == "__main__":
    baseline = load_baseline()
    output = {"scope": "Injected 429/503, synchronous transport, 10 barrier bursts; RSS sampled between bursts in shared process; not ingress or live provider throughput",
              "baseline": "8c315ed", "results": []}
    for label, module in [("baseline", baseline), ("candidate", current)]:
        for fault in (429, 503):
            for concurrency in (1, 100):
                output["results"].append({"version": label, **bench(module, fault, concurrency)})
    print(json.dumps(output, indent=2))
