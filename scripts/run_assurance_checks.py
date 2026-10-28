#!/usr/bin/env python3
"""Run bounded assurance regressions; never build/deploy or certify the full product."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".assurance-results")
    parser.add_argument("--document-service", action="store_true",
                        help="also run selected single-parse/admission/context service regressions (pytest dependencies required)")
    args = parser.parse_args()
    destination = args.output.absolute()
    destination.mkdir(parents=True, exist_ok=True)
    python = sys.executable
    frontend = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "phantom-overlay/tests").glob("*.test.cjs"))
    commands = [
        ("python-assurance", [python, "-B", "-m", "unittest", "discover", "-s", "tests/assurance", "-p", "test_*.py", "-v"]),
        ("dsse-compatibility", [python, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_legal_v3_dsse_envelope.py", "-v"]),
        ("benchmark-compatibility", [python, "-B", "-m", "unittest", "discover", "-s", "bench", "-p", "test_verifiable_benchmark.py", "-v"]),
        ("claim-guard-logic", [python, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_claim_guard_logic.py", "-v"]),
        ("release-regression-contract", [python, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_release_check.py"]),
        ("release-tool-error-lint", [python, "-m", "ruff", "check", "--select", "E9,F", "scripts/release_evidence.py", "scripts/verify_production_gate.py", "scripts/generate_certification.py", "scripts/verify_launch_checklist.py", "scripts/release_check.py", "scripts/ci/sbom_gate.py", "tests/assurance/test_release_evidence.py", "tests/assurance/test_sbom_gate_fail_closed.py", "tests/test_release_check.py"]),
        ("invoice-evidence-contract", [python, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "packs/tests/test_invoice_pack.py", "packs/tests/test_invoice_semantic_evidence.py"]),
        ("frontend", ["node", "--test", *frontend]),
        ("preview-source-guard", [python, "-B", "scripts/check_authorized_preview.py"]),
        ("diff-whitespace", ["git", "diff", "--check"]),
        ("python-error-lint", [python, "-m", "ruff", "check", "--select", "E9,F", "overlay", "kernel", "kairo/context/compressor.py", "scripts/stress_sec006_gauntlet.py", "stress_test.py"]),
        ("wave11-python-lint", [python, "-m", "ruff", "check", "overlay/server.py", "kernel/sidecar/melious_router.py", "overlay/tests/test_server_wave11.py", "kernel/tests/test_melious_router_wave11.py", "scripts/stress_wave11.py"]),
    ]
    if args.document_service:
        commands.append(("document-service", [
            python, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "-o", "asyncio_default_fixture_loop_scope=function",
            "overlay/tests/test_single_parse_boundary.py",
            "overlay/tests/test_worker_lifecycle.py",
            "overlay/tests/test_logging_queue_snapshot.py",
            "overlay/tests/test_validation_hygiene_contract.py",
            "overlay/tests/test_response_middleware_contract.py",
            "overlay/tests/test_request_guard_contract.py",
            "overlay/tests/test_auth_rate_gate_contract.py",
            "kernel/tests/test_launch_hardening_ag07_08_09.py::test_extraction_deadline_returns_504_and_releases_slot",
            "overlay/tests/test_extraction_admission.py",
            "overlay/tests/test_extraction_context.py",
            "overlay/tests/test_server_wave11.py",
            "kernel/tests/test_session21_isolation_and_timeouts.py",
        ]))
    results = []
    for name, command in commands:
        start = time.monotonic()
        try:
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=120)
            code, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
        except (OSError, subprocess.TimeoutExpired) as exc:
            code, stdout, stderr = 1, b"", f"Execution unavailable or timed out: {type(exc).__name__}".encode()
        logfile = destination / f"{name}.log"
        logfile.write_bytes(stdout + b"\n--- STDERR ---\n" + stderr)
        results.append({"name": name, "command": command, "exit_code": code,
                        "duration_seconds": round(time.monotonic() - start, 3),
                        "log": logfile.name, "log_sha256": hashlib.sha256(logfile.read_bytes()).hexdigest()})
        print(f"{'PASS' if code == 0 else 'FAIL'}: {name}")
    try:
        base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        base = "unavailable"
    report = {"scope": "selected authentication/benchmark/parser and frontend/source regressions" +
                        (" plus selected document-service regressions" if args.document_service else " only"),
              "document_service_profile": args.document_service,
              "source_head": base, "working_tree_may_be_modified": True,
              "all_scoped_checks_passed": all(row["exit_code"] == 0 for row in results),
              "checks": results,
              "native_toolchain_present": bool(shutil.which("cargo")),
              "not_run": ["native Rust build/test/clippy", "compiled Tauri app", "real local model E2E",
                          "full repository suite", "packet/network certification", "independent external security review",
                          "native installer lifecycle", "customer/learning/traction validation"],
              "release_verdict": "not production-qualified"}
    (destination / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Result applies only to listed checks; production qualification remains open.")
    return 0 if report["all_scoped_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
