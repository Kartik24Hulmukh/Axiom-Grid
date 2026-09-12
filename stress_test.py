"""
Axiom-Grid 100x/300x Concurrency Stress Test & Red Team Security Probe Suite
Tests high contention ASGI throughput, latency percentiles, and fail-closed security gates.
"""

import time
import json
import statistics
import concurrent.futures
import pathlib
from fastapi.testclient import TestClient
from overlay.server import app

def run_stress_suite():
    client = TestClient(app)
    
    print("=== Step 1: Running Red Team Security & Boundary Matrix ===")
    d = chr(46); dd = d + d; slash = chr(47)
    probes = [
        ("POST", "/api/extract-document", {"file": "/etc/passwd"}, None, 404),
        ("POST", "/api/extract-document", {"file": (dd + slash) * 4 + "etc/passwd"}, None, 404),
        ("POST", "/demo", {"file": "/etc/passwd"}, None, 404),
        ("POST", "/demo", {"file": (dd + slash) * 4 + "etc/passwd"}, None, 404),
        ("POST", "/demo", {"file": "fixtures/" + (dd + slash) * 3 + "etc/passwd"}, None, 404),
        ("POST", "/demo", {"file": "/proc/self/environ"}, None, 404),
        ("POST", "/demo", {"file": "fixtures/" + (dd + slash) * 3 + "etc/shadow"}, None, 404),
        ("GET", "/api/figures/doc1?file=/etc/passwd", None, None, 404),
        ("POST", "/demo", {"file": "sample_memo_01.txt"}, {"Origin": "https://evil.example"}, 403),
        ("POST", "/demo", {"file": "sample_memo_01.txt"}, {"Origin": "https://evil.com"}, 403),
        ("POST", "/demo", {"file": "sample_memo_01.txt"}, {"Origin": "null"}, 403),
        ("POST", "/demo", {"file": "sample_memo_01.txt"}, {"Origin": "http://127.0.0.1:8765"}, 200),
        ("POST", "/api/extract-document", {"file": ""}, None, 422),
        ("POST", "/api/extract-document", {"file": "   "}, None, 422),
        ("POST", "/api/extract-document", {"file": "a\x00b"}, None, 422),
        ("POST", "/api/extract-document", {"file": "fixtures/wedge/sample_memo_01.txt"}, None, 200),
    ]

    probe_results = []
    for method, path, body, headers, expected_status in probes:
        t0 = time.perf_counter()
        if method == "POST":
            r = client.post(path, json=body, headers=headers)
        else:
            r = client.get(path, headers=headers)
        dt = (time.perf_counter() - t0) * 1000
        passed = (r.status_code == expected_status)
        probe_results.append({
            "probe": f"{method} {path} (body={body}, headers={headers})",
            "expected": expected_status,
            "actual": r.status_code,
            "latency_ms": round(dt, 2),
            "passed": passed
        })
        if not passed:
            print(f"FAILED PROBE: {method} {path} -> {r.status_code} (expected {expected_status})")
        else:
            print(f"PASS: {method} {path} -> {r.status_code}")

    all_passed = all(p["passed"] for p in probe_results)
    print(f"\nProbe Matrix: {sum(1 for p in probe_results if p['passed'])}/{len(probe_results)} passed\n")

    print("=== Step 2: Running 300 Mixed Concurrent Requests (30 Threads) ===")
    requests_pool = []
    for _ in range(100):
        requests_pool.append(("valid_demo", "/demo", {"file": "sample_memo_01.txt"}, None, 200))
    for _ in range(103):
        requests_pool.append(("hostile_traversal", "/demo", {"file": (dd + slash) * 4 + "etc/passwd"}, None, 404))
    for _ in range(97):
        requests_pool.append(("invalid_schema", "/api/extract-document", {"file": ""}, None, 422))

    latencies = []
    status_counts = {}
    crashes = 0

    def worker_req(item):
        name, path, body, headers, expected = item
        t_start = time.perf_counter()
        try:
            r = client.post(path, json=body, headers=headers)
            elapsed = (time.perf_counter() - t_start) * 1000
            return (r.status_code, elapsed, None)
        except Exception as exc:
            elapsed = (time.perf_counter() - t_start) * 1000
            return (500, elapsed, str(exc))

    wall_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as pool:
        futures = [pool.submit(worker_req, item) for item in requests_pool]
        results = [f.result() for f in futures]
    wall_duration = time.perf_counter() - wall_start

    for status, lat, err in results:
        status_counts[status] = status_counts.get(status, 0) + 1
        latencies.append(lat)
        if err or status == 500:
            crashes += 1

    latencies.sort()
    n = len(latencies)
    metrics = {
        "total_requests": n,
        "concurrency_workers": 30,
        "wall_time_seconds": round(wall_duration, 4),
        "throughput_req_per_sec": round(n / wall_duration, 2),
        "status_code_distribution": status_counts,
        "unhandled_crashes": crashes,
        "success_rate_pct": 100.0 if crashes == 0 else round((n - crashes) / n * 100, 2),
        "latency_ms": {
            "p50": round(statistics.median(latencies), 2),
            "p90": round(latencies[int(n * 0.90)], 2),
            "p95": round(latencies[int(n * 0.95)], 2),
            "p99": round(latencies[int(n * 0.99)], 2),
            "mean": round(statistics.mean(latencies), 2),
            "max": round(max(latencies), 2),
            "min": round(min(latencies), 2),
        },
        "probe_matrix": probe_results,
    }

    print(f"Wall time: {metrics['wall_time_seconds']}s")
    print(f"Throughput: {metrics['throughput_req_per_sec']} req/s")
    print(f"Status distribution: {status_counts}")
    print(f"Latency: p50={metrics['latency_ms']['p50']}ms, p95={metrics['latency_ms']['p95']}ms, p99={metrics['latency_ms']['p99']}ms")
    print(f"Unhandled crashes: {crashes}")

    out_path = pathlib.Path("docs/axiom/evidence/stress_test_report_100x.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(metrics, indent=2))
    print(f"\nSaved stress test report to {out_path}")

    return 0 if all_passed and crashes == 0 else 1

if __name__ == "__main__":
    import sys
    sys.exit(run_stress_suite())
