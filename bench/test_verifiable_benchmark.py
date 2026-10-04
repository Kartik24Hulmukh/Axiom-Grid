"""Test the Verifiable Agent-Action Benchmark end-to-end."""
import json
from pathlib import Path

from bench.verifiable_benchmark import run_benchmark, verify_report


def test_benchmark_runs_and_signs(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    report = run_benchmark(tasks=3, out=str(out))
    assert report["tasks_run"] == 3
    assert report["metrics"]["all_actions_signed"] is True
    assert report["metrics"]["correctness"] == 1.0
    assert report["metrics"]["citation_coverage"] == 1.0
    # Every task carries a real entry hash and latency
    for r in report["results"]:
        assert r["entry_hash"]
        assert r["latency_ms"] >= 0
    assert Path(report["receipts_file"]).exists()


def test_benchmark_report_verifies(tmp_path: Path) -> None:
    out = tmp_path / "report2.json"
    report = run_benchmark(tasks=2, out=str(out))
    # Chain verification against the emitted public key passes
    assert verify_report(out, ".keys/bench_ed25519.pub.pem") is True
    # The report JSON itself is loadable and well-formed
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["benchmark"].startswith("Verifiable Agent-Action Benchmark")
