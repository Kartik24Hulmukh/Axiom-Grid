"""Compare telemetry retention and snapshot costs against a git revision."""
import json
import math
import subprocess
import sys
import time
import tracemalloc
import types
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kairo.context import compressor


def measure(module):
    module._global_stats.clear()
    process = psutil.Process()
    rss = [process.memory_info().rss]
    tracemalloc.start()
    started = time.perf_counter()
    for _ in range(20000):
        module.record_compression(module.CompressionStats(tokens_before=10, tokens_after=6, tokens_saved=4))
    write_seconds = time.perf_counter() - started
    retained, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rss.append(process.memory_info().rss)
    latencies = []
    for _ in range(200):
        start = time.perf_counter()
        snapshot = module.get_compression_stats()
        latencies.append((time.perf_counter() - start) * 1000)
        assert snapshot["total_runs"] == 20000
    rss.append(process.memory_info().rss)
    latencies.sort()
    return {"runs": 20000, "snapshot_samples": 200,
            "record_rps": round(20000 / write_seconds, 2),
            "snapshot_latency_ms": {f"p{n}": round(latencies[math.ceil(n / 100 * 200)-1], 6) for n in (50, 95, 99)},
            "retained_python_bytes": retained, "peak_python_bytes": peak,
            "rss_floor_mib": round(min(rss)/2**20, 2), "rss_ceiling_mib": round(max(rss)/2**20, 2)}


def main():
    revision = sys.argv[1] if len(sys.argv) > 1 else "0800f13"
    old = types.ModuleType("baseline_compressor")
    sys.modules[old.__name__] = old
    source = subprocess.check_output(["git", "show", f"{revision}:kairo/context/compressor.py"], cwd=ROOT, text=True)
    exec(compile(source, "baseline_compressor.py", "exec"), old.__dict__)
    report = {"baseline_revision": revision,
              "method": "same-process sequential 20k records then 200 snapshots; tracemalloc around writes; RSS at phase boundaries, not sampled process extremes; no end-to-end capacity claim", "before": measure(old), "after": measure(compressor)}
    print(json.dumps(report, indent=2))
    (ROOT / "docs/axiom/evidence/session11-compression-benchmark.json").write_text(json.dumps(report, indent=2)+"\n")
    assert report["after"]["retained_python_bytes"] < report["before"]["retained_python_bytes"] / 10


if __name__ == "__main__":
    main()
