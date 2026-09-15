"""Local router bookkeeping benchmark; NOT provider/API/100x certification.
Run baseline and candidate in separate processes with --router pointing at source.
"""
import argparse
import importlib.util
import json
import math
import platform
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import psutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--router", default="kernel/sidecar/melious_router.py")
    parser.add_argument("--requests", type=int, default=20000)
    parser.add_argument("--concurrency", type=int, default=100)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("requests and concurrency must be positive")
    spec = importlib.util.spec_from_file_location("bench_router", args.router)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    def transport(*unused):
        return {"choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}

    router = module.MeliousModelRouter(models=("local",), transport=transport,
                                       max_retries=0, max_inflight=args.concurrency)
    process = psutil.Process()
    rss = [process.memory_info().rss]
    fd_before = process.num_fds()
    stopped = threading.Event()

    def monitor():
        while not stopped.wait(0.005):
            rss.append(process.memory_info().rss)

    thread = threading.Thread(target=monitor)
    thread.start()

    def hit(_):
        start = time.perf_counter()
        try:
            router.complete([{"role": "user", "content": "x"}], max_tokens=8)
            outcome = "success"
        except module.RouterError:
            outcome = "router_error"
        except Exception:  # noqa: BLE001 -- benchmark must count unexpected failures
            outcome = "unexpected_exception"
        return (time.perf_counter() - start) * 1000, outcome

    started = time.perf_counter()
    try:
        with ThreadPoolExecutor(args.concurrency) as pool:
            results = list(pool.map(hit, range(args.requests)))
    finally:
        stopped.set()
        thread.join()
    duration = time.perf_counter() - started
    rss.append(process.memory_info().rss)
    latencies = sorted(row[0] for row in results)
    counts = dict(Counter(row[1] for row in results))
    print(json.dumps({
        "scope": "in-process deterministic transport; bookkeeping only; no network or model inference",
        "python": platform.python_version(), "requests": args.requests,
        "concurrency": args.concurrency, "outcomes": counts,
        "throughput_rps": round(args.requests / duration, 2),
        "latency_ms": {f"p{p}": round(latencies[math.ceil(p / 100 * len(latencies)) - 1], 4)
                       for p in (50, 95, 99)},
        "rss_sample_floor_mib": round(min(rss) / 2**20, 2),
        "rss_sample_peak_mib": round(max(rss) / 2**20, 2),
        "rss_sample_interval_ms": 5,
        "fd_before": fd_before, "fd_after": process.num_fds(),
        "metrics": router.get_metrics(),
    }, indent=2))
    return int(counts.get("success", 0) != args.requests)


if __name__ == "__main__":
    raise SystemExit(main())
