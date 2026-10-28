#!/usr/bin/env python3
"""Deterministic synthetic regression evaluator; never release qualification.

Usage: python3 scripts/release_check.py [--output /explicit/path/report.md]
The synthetic-regression-only profile explicitly runs InvoicePack on held_out using the
benchmark's deterministic gateway test mode. Exit 0 means only these regression
checks passed. It is not evidence of model quality, network isolation, native
behavior, or production readiness. No persistent report is written by default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pathlib
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PROFILE = "synthetic-regression-only"
GROUNDED_ANSWER_MIN = 95.0
REFUSAL_ON_UNANSWERABLE_TARGET = 100.0
FALSE_REFUSAL_MAX = 5.0
UNGROUNDED_RENDERS_MAX = 0
class InsufficientCoverageError(ValueError):
    """Valid count evidence that cannot exercise every required rate gate."""

    def __init__(self, metrics: dict):
        super().__init__("Insufficient coverage: every rate requires a positive denominator")
        self.metrics = metrics


CHECK_NAMES = ("cloud_tier_policy_rejection", "synthetic_safety_audits", "ungrounded_sample_rejected")


def _run_isolated(command: list[str], directory: str) -> subprocess.CompletedProcess:
    """Keep legacy history, logs and scratch files outside the repository."""
    env = os.environ.copy()
    env.update({
        "KAIRO_GATEWAY_TEST_MODE": "true",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(REPO_ROOT),
        "AXIOM_STATE_DIR": str(pathlib.Path(directory) / "state"),
    })
    env.pop("KAIRO_PLANTED_PASS", None)
    env.pop("KAIRO_PLANTED_REGRESSION", None)
    return subprocess.run(command, cwd=directory, env=env, capture_output=True,
                          text=True, timeout=120)


def _run_bench(fixtures_dir: str, output_path: str) -> dict:
    """Explicit InvoicePack mapping; no dirname-based CLI pack inference."""
    fixtures = (REPO_ROOT / fixtures_dir).resolve()
    output = pathlib.Path(output_path).resolve()
    code = """import json, sys
from bench.harness import run_benchmark
from packs.invoice.pack import InvoicePack
report = run_benchmark([{'name': 'held_out-invoice', 'class': InvoicePack, 'dir': sys.argv[1]}])
with open(sys.argv[2], 'w', encoding='utf-8') as stream:
    json.dump(report, stream, allow_nan=False)
"""
    with tempfile.TemporaryDirectory(prefix="kairo-regression-bench-") as directory:
        result = _run_isolated([sys.executable, "-c", code, str(fixtures), str(output)], directory)
        if result.returncode != 0:
            raise ValueError("Deterministic benchmark failed")
        with output.open(encoding="utf-8") as stream:
            return json.load(stream)


def _compute_gate_metrics(report: dict) -> dict:
    """Require measured values and consistent counts with positive rate coverage."""
    if not isinstance(report, dict) or not isinstance(report.get("gates"), dict):
        raise ValueError("Missing or malformed gates")
    metrics = {"rate_counts": {}}
    for source, target in (
        ("grounded_answer_rate", "grounded_answer_rate"),
        ("refusal_on_unanswerable", "refusal_on_unanswerable"),
        ("false_refusal_rate", "false_refusal_rate"),
        ("ungrounded_render_count", "ungrounded_renders"),
    ):
        gate = report["gates"].get(source)
        if not isinstance(gate, dict) or "measured" not in gate:
            raise ValueError(f"Missing measured metric: {source}")
        value = gate["measured"]
        if source == "ungrounded_render_count":
            valid = type(value) is int and value >= 0
        else:
            valid = (type(value) in (int, float) and 0 <= value <= 100
                     and math.isfinite(value))
        if not valid:
            raise ValueError(f"Invalid measured metric: {source}")
        metrics[target] = value
        if source != "ungrounded_render_count":
            numerator, denominator = gate.get("numerator"), gate.get("denominator")
            if (type(numerator) is not int or type(denominator) is not int
                    or denominator < 0 or not 0 <= numerator <= denominator):
                raise ValueError(f"Invalid rate counts: {source}")
            metrics["rate_counts"][source] = {"numerator": numerator, "denominator": denominator}
            if denominator > 0 and value != round(numerator / denominator * 100, 4):
                raise ValueError(f"Measured rate disagrees with counts: {source}")
    if any(counts["denominator"] == 0 for counts in metrics["rate_counts"].values()):
        raise InsufficientCoverageError(metrics)
    if (metrics["rate_counts"]["grounded_answer_rate"]["denominator"]
            != metrics["rate_counts"]["false_refusal_rate"]["denominator"]):
        raise ValueError("Grounded and false-refusal rates require the same answerable denominator")
    return metrics


def _check_cloud_tier_policy_rejection() -> bool:
    """Test disabled-cloud-tier policy rejection, NOT absence of network egress."""
    code = '''from kernel.core.contracts import InferenceTier
from kernel.sidecar.inference_gateway import TieredInferenceGateway, AirGapViolationError
gateway = TieredInferenceGateway(tier3_enabled=False)
try:
    gateway.complete(role="extractor", prompt="synthetic policy probe", tier=InferenceTier.TIER3_CLOUD)
except AirGapViolationError:
    raise SystemExit(0)
raise SystemExit(1)
'''
    with tempfile.TemporaryDirectory(prefix="kairo-policy-") as directory:
        return _run_isolated([sys.executable, "-c", code], directory).returncode == 0


def _check_verifier_adversarial() -> bool:
    """Run legacy synthetic safety audits; not a native/model qualification suite."""
    with tempfile.TemporaryDirectory(prefix="kairo-safety-") as directory:
        return _run_isolated([sys.executable, "-m", "bench.safety"], directory).returncode == 0


def _check_trust_collapse_list() -> bool:
    """Check one ungrounded sample, not an exhaustive trust-collapse proof."""
    code = '''from kernel.core.contracts import GateVerdict
from kernel.core.data_model import Extraction, GroundingMethod
from kernel.sidecar.memory_store import MemoryStoreImpl
from kernel.sidecar.quality_gate import LocalQualityGate
gate = LocalQualityGate(MemoryStoreImpl(":memory:"))
ext = Extraction(field_name="test", value="ungrounded value", confidence=0.99, chunk_id="", method=GroundingMethod.BLOCK)
raise SystemExit(0 if gate.check(ext).verdict == GateVerdict.BLOCK else 1)
'''
    with tempfile.TemporaryDirectory(prefix="kairo-grounding-") as directory:
        return _run_isolated([sys.executable, "-c", code], directory).returncode == 0


def _evaluate(metrics: dict, checks: dict) -> dict:
    if set(checks) != set(CHECK_NAMES) or any(type(v) is not bool for v in checks.values()):
        raise ValueError("Missing or invalid regression checks")
    counts = metrics["rate_counts"]
    if any(c["denominator"] <= 0 for c in counts.values()):
        raise InsufficientCoverageError(metrics)
    grounded = counts["grounded_answer_rate"]
    refusal = counts["refusal_on_unanswerable"]
    false_refusal = counts["false_refusal_rate"]
    return {
        "grounded_answer": grounded["numerator"] * 100 >= grounded["denominator"] * 95,
        "refusal_on_unanswerable": refusal["numerator"] == refusal["denominator"],
        "false_refusal": false_refusal["numerator"] * 100 < false_refusal["denominator"] * 5,
        "ungrounded_renders": metrics["ungrounded_renders"] == UNGROUNDED_RENDERS_MAX,
        **checks,
    }


def _generate_report(metrics: dict | None, checks: dict, error: str | None = None) -> str:
    results = _evaluate(metrics, checks) if metrics is not None and error is None else {}
    payload = {
        "profile": PROFILE,
        "benchmark": "bench.harness.run_benchmark: held_out-invoice / InvoicePack / fixtures/held_out",
        "gateway_mode": "deterministic synthetic test responses",
        "production_qualified": False,
        "release_cleared": False,
        "regression_passed": bool(results) and all(results.values()),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics, "checks": checks, "results": results, "error": error,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    checksum = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    status = "PASS" if payload["regression_passed"] else "FAIL"
    return f'''# Kairo — Synthetic Regression Report

**Profile:** {PROFILE}
**Synthetic regression status:** {status}
production_qualified=false
release_cleared=false

This report NEVER clears release or production. Passing means only that the
listed deterministic regression checks passed; fixtures are not live-model evidence.
Every rate requires positive coverage; numerator/denominator counts are retained.
Rate thresholds use exact count comparisons, not rounded displayed percentages.
Cloud-tier policy rejection is not network or air-gap proof. The legacy safety
audits and one ungrounded sample do not prove exhaustive adversarial resistance.
No native UI, target-device, offline operation or backend provenance qualification.

**SHA-256 checksum:** `{checksum}`
Checksum covers the exact UTF-8 canonical JSON line below (excluding its newline).
This is a checksum, not a cryptographic signature or proof of authenticity.

```json
{canonical}
```
'''


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=[PROFILE], default=PROFILE)
    parser.add_argument("--output", type=pathlib.Path, help="Explicit new Markdown report path; default: stdout only")
    args = parser.parse_args(argv)
    # Reject the former approval bypass BEFORE subprocesses, temp files or output.
    if os.environ.get("KAIRO_PLANTED_PASS", "").strip().lower() == "true":
        print("ERROR: KAIRO_PLANTED_PASS=true is rejected; no evidence was written.", file=sys.stderr)
        return 2
    if args.output is not None and args.output.exists():
        print("ERROR: output already exists; choose a new explicit path.", file=sys.stderr)
        return 2
    metrics = None
    checks = {}
    error = None
    try:
        with tempfile.TemporaryDirectory(prefix="kairo-regression-") as directory:
            report = _run_bench("fixtures/held_out", str(pathlib.Path(directory) / "benchmark.json"))
        metrics = _compute_gate_metrics(report)
        checks = {
            "cloud_tier_policy_rejection": _check_cloud_tier_policy_rejection(),
            "synthetic_safety_audits": _check_verifier_adversarial(),
            "ungrounded_sample_rejected": _check_trust_collapse_list(),
        }
        results = _evaluate(metrics, checks)
        passed = all(results.values())
    except InsufficientCoverageError as exc:
        metrics = exc.metrics
        error = str(exc)
        passed = False
    except Exception as exc:
        # Do not turn missing or invalid evidence into default passing metrics.
        error = f"Regression evaluation failed ({type(exc).__name__})"
        passed = False
    text = _generate_report(metrics, checks, error)
    print(text, end="")
    if args.output is not None:
        try:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(text)
        except OSError as exc:
            print(f"ERROR: report write failed ({type(exc).__name__})", file=sys.stderr)
            return 2
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
