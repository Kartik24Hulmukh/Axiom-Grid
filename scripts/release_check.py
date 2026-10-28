#!/usr/bin/env python3
"""Deterministic synthetic regression evaluator; never release qualification.

Usage: python3 scripts/release_check.py [--output /explicit/path/report.md]
The synthetic-regression-only profile explicitly runs InvoicePack on held_out and
held_out_negative with complete indexed-document coverage using the
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
import re
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


# Fixed reviewed profile: no directory-name inference and no caller-selected corpus.
PROFILE_PACKS = (("held_out-invoice", "fixtures/held_out"),
                 ("held_out-negative-invoice", "fixtures/held_out_negative"))
INVOICE_FIELDS = ("vendor_name", "invoice_number", "invoice_date", "due_date",
                  "total_amount", "currency", "line_items", "tax_amount", "payment_terms")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate fixture-index key")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError("Non-finite fixture-index value")


def _answerable(value):
    return value is not None and not (isinstance(value, str) and not value.strip()) and not (
        isinstance(value, (list, dict)) and not value)


def _validate_truth(truth):
    if type(truth) is not dict or set(truth) != set(INVOICE_FIELDS):
        raise ValueError("Fixture must declare all and only invoice fields")
    for field, value in truth.items():
        if value is None:
            continue
        if field in {"total_amount", "tax_amount"}:
            if type(value) not in (int, float) or not 0 <= value < 1e100 or not math.isfinite(value):
                raise ValueError("Invalid fixture amount")
        elif field == "line_items":
            if type(value) is not list:
                raise ValueError("Invalid fixture line items")
            for item in value:
                if type(item) is not dict or set(item) != {"description", "quantity", "unit_price", "total"}:
                    raise ValueError("Invalid fixture line item")
                if type(item["description"]) is not str or not item["description"].strip():
                    raise ValueError("Invalid fixture description")
                for name in ("quantity", "unit_price", "total"):
                    v = item[name]
                    if type(v) not in (int, float) or not 0 <= v < 1e100 or not math.isfinite(v):
                        raise ValueError("Invalid fixture line-item number")
        elif type(value) is not str or not value.strip():
            raise ValueError("Invalid fixture text field")


def _load_profile_manifest(fixtures_dir: str = "fixtures/held_out") -> dict:
    """Validate the fixed profile before running; snapshot index and source bytes."""
    root = REPO_ROOT.resolve()
    if fixtures_dir != PROFILE_PACKS[0][1]:
        raise ValueError("Unsupported fixture profile")
    documents, packs, ids, paths = [], [], set(), set()
    hasher = hashlib.sha256()
    # Same ordered corpus-byte convention as bench.harness.compute_corpus_hash.
    for name, relative in sorted(PROFILE_PACKS):
        directory = root / relative
        if directory.resolve() != directory or not directory.is_dir():
            raise ValueError("Missing or redirected fixture directory")
        index = directory / "ground_truth.json"
        if index.is_symlink() or not index.is_file() or index.stat().st_size > 1024 * 1024:
            raise ValueError("Missing or invalid fixture index")
        raw = index.read_bytes()
        if len(raw) > 1024 * 1024:
            raise ValueError("Fixture index exceeds limit")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant)
        if type(data) is not dict or type(data.get("fixtures")) is not list or not data["fixtures"]:
            raise ValueError("Fixture dataset must be a nonempty indexed list")
        hasher.update(name.encode()); hasher.update(b"\0"); hasher.update(raw); hasher.update(b"\0")
        filenames = set()
        for record in data["fixtures"]:
            if type(record) is not dict or not {"fixture_id", "file", "ground_truth"} <= set(record):
                raise ValueError("Malformed fixture record")
            fid, filename = record["fixture_id"], record["file"]
            if type(fid) is not str or not fid.strip() or fid in ids:
                raise ValueError("Missing or duplicate fixture identifier")
            if (type(filename) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*\.txt", filename)
                    or filename in filenames):
                raise ValueError("Invalid or duplicate fixture filename")
            source = directory / filename
            if source.is_symlink() or source.resolve() != source or not source.is_file():
                raise ValueError("Missing or redirected indexed document")
            if source in paths or source.stat().st_size > 1024 * 1024:
                raise ValueError("Duplicate or oversized fixture document")
            content = source.read_bytes()
            if len(content) > 1024 * 1024 or not content.decode("utf-8").strip():
                raise ValueError("Empty or oversized fixture document")
            _validate_truth(record["ground_truth"])
            answerable = [field for field in INVOICE_FIELDS if _answerable(record["ground_truth"][field])]
            documents.append({"pack": name, "fixture_id": fid, "file": filename,
                              "answerable": answerable})
            ids.add(fid); filenames.add(filename); paths.add(source)
            hasher.update(content); hasher.update(b"\0")
        if {p.name for p in directory.glob("*.txt")} != filenames:
            raise ValueError("Unindexed fixture documents require review")
        packs.append({"name": name, "dir": str(directory)})
    return {"packs": packs, "documents": documents, "corpus_hash": hasher.hexdigest()}


def _validate_report_coverage(report: dict, manifest: dict) -> dict:
    """Reject missing/duplicate/stale document populations and inconsistent counts.

    This checks reported deterministic coverage, not execution authenticity.
    """
    if type(report) is not dict or report.get("corpus_hash") != manifest["corpus_hash"]:
        raise ValueError("Benchmark corpus does not match the indexed profile")
    docs, packs = report.get("per_document"), report.get("packs")
    if type(docs) is not list or type(packs) is not dict or set(packs) != {p["name"] for p in manifest["packs"]}:
        raise ValueError("Missing or unexpected benchmark document/pack population")
    expected = {(d["pack"], d["fixture_id"], d["file"]): d for d in manifest["documents"]}
    seen = set()
    columns = ("answerable_fields", "unanswerable_fields", "grounded_answers",
               "correct_refusals", "false_refusals", "ungrounded_renders")
    sums = {p: dict.fromkeys(columns, 0) for p in packs}
    for doc in docs:
        if type(doc) is not dict:
            raise ValueError("Invalid per-document record")
        key = tuple(doc.get(k) for k in ("pack", "fixture_id", "file"))
        if any(type(v) is not str for v in key) or key not in expected or key in seen:
            raise ValueError("Missing, unexpected or duplicate document identity")
        seen.add(key)
        truth = expected[key]
        answerable = set(truth["answerable"])
        counts = {c: doc.get(c) for c in columns}
        if any(type(v) is not int or not 0 <= v <= len(INVOICE_FIELDS) for v in counts.values()):
            raise ValueError("Invalid per-document counts")
        if counts["answerable_fields"] != len(answerable) or counts["unanswerable_fields"] != 9-len(answerable):
            raise ValueError("Document answerability does not match source index")
        details = doc.get("field_details")
        if type(details) is not list or len(details) != len(INVOICE_FIELDS):
            raise ValueError("Missing document field coverage")
        fields, derived = set(), dict.fromkeys(columns, 0)
        derived.update(answerable_fields=len(answerable), unanswerable_fields=9-len(answerable))
        for detail in details:
            if type(detail) is not dict or type(detail.get("field")) is not str:
                raise ValueError("Invalid field detail")
            field, status = detail["field"], detail.get("status")
            if field not in INVOICE_FIELDS or field in fields:
                raise ValueError("Duplicate or unexpected field detail")
            fields.add(field)
            grounded, rendered = detail.get("grounded"), detail.get("rendered")
            if type(grounded) is not bool or type(rendered) is not bool:
                raise ValueError("Invalid field rendering/grounding evidence")
            allowed = {"grounded", "false_refusal", "ungrounded_render"} if field in answerable else {"correct_refusal", "incorrect_answer"}
            if type(status) is not str or status not in allowed:
                raise ValueError("Field status disagrees with indexed answerability")
            if ((status == "grounded" and (not grounded or not rendered))
                    or (status in {"false_refusal", "correct_refusal"} and (grounded or rendered))
                    or (status == "ungrounded_render" and (grounded or not rendered))
                    or (status == "incorrect_answer" and not rendered)):
                raise ValueError("Field status disagrees with rendering evidence")
            counter = {"grounded": "grounded_answers", "false_refusal": "false_refusals",
                       "correct_refusal": "correct_refusals"}.get(status)
            if counter:
                derived[counter] += 1
            if rendered and not grounded:
                derived["ungrounded_renders"] += 1
        if counts != derived:
            raise ValueError("Document summary disagrees with field details")
        for c in columns:
            sums[key[0]][c] += counts[c]
    if seen != set(expected):
        raise ValueError("Indexed document coverage is incomplete")
    for pack, totals in sums.items():
        row = packs[pack]
        if type(row) is not dict or type(row.get("total_documents")) is not int or row["total_documents"] != sum(d["pack"] == pack for d in manifest["documents"]):
            raise ValueError("Pack document count is stale or incomplete")
        for column, value in totals.items():
            name = "ungrounded_render_count" if column == "ungrounded_renders" else column
            if type(row.get(name)) is not int or row[name] != value:
                raise ValueError("Pack summary disagrees with document counts")
    totals = {c: sum(p[c] for p in sums.values()) for c in columns}
    rates = {"grounded_answer_rate": (totals["grounded_answers"], totals["answerable_fields"]),
             "refusal_on_unanswerable": (totals["correct_refusals"], totals["unanswerable_fields"]),
             "false_refusal_rate": (totals["false_refusals"], totals["answerable_fields"])}
    gates = report.get("gates")
    if type(gates) is not dict:
        raise ValueError("Missing global gate counts")
    for name, pair in rates.items():
        row = gates.get(name)
        if (type(row) is not dict or any(type(row.get(c)) is not int for c in ("numerator", "denominator"))
                or (row["numerator"], row["denominator"]) != pair):
            raise ValueError("Global gate counts disagree with document coverage")
    renders = gates.get("ungrounded_render_count")
    if type(renders) is not dict or type(renders.get("measured")) is not int or renders["measured"] != totals["ungrounded_renders"]:
        raise ValueError("Global render count disagrees with document coverage")
    return {"document_count": len(docs), "fixture_ids": sorted(d["fixture_id"] for d in docs),
            "corpus_hash": manifest["corpus_hash"], "answerable_fields": totals["answerable_fields"],
            "unanswerable_fields": totals["unanswerable_fields"]}


def _run_bench(fixtures_dir: str, output_path: str) -> dict:
    """Run both reviewed InvoicePack datasets; validate every indexed result."""
    manifest = _load_profile_manifest(fixtures_dir)
    output = pathlib.Path(output_path).resolve()
    code = """import json, sys
from bench.harness import run_benchmark
from packs.invoice.pack import InvoicePack
configs = [{**item, 'class': InvoicePack} for item in json.loads(sys.argv[1])]
report = run_benchmark(configs)
with open(sys.argv[2], 'w', encoding='utf-8') as stream:
    json.dump(report, stream, allow_nan=False)
"""
    with tempfile.TemporaryDirectory(prefix="kairo-regression-bench-") as directory:
        result = _run_isolated([sys.executable, "-c", code, json.dumps(manifest["packs"]), str(output)], directory)
        if result.returncode != 0:
            raise ValueError("Deterministic benchmark failed")
        with output.open(encoding="utf-8") as stream:
            report = json.load(stream)
    if _load_profile_manifest(fixtures_dir) != manifest:
        raise ValueError("Fixture profile changed during evaluation")
    coverage = _validate_report_coverage(report, manifest)
    report["profile_coverage"] = coverage
    return report


def _compute_gate_metrics(report: dict) -> dict:
    """Require measured values and consistent counts with positive rate coverage."""
    if not isinstance(report, dict) or not isinstance(report.get("gates"), dict):
        raise ValueError("Missing or malformed gates")
    metrics = {"rate_counts": {}}
    if "profile_coverage" in report:
        metrics["profile_coverage"] = report["profile_coverage"]
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
        "benchmark": "bench.harness.run_benchmark: InvoicePack / fixtures/held_out + fixtures/held_out_negative / indexed-document coverage",
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
Every indexed document and field must be accounted for; corpus bytes and counts
are checked against both reviewed fixture indexes. Every rate requires positive
coverage; numerator/denominator counts are retained. This is not attestation.
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
