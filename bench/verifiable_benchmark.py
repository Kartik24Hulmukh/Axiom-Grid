"""Local ingestion/signing microbenchmark, format v2 (NOT agent-quality scoring).

BREAKING: v0.1 scorecards/adapter receipt chains are not accepted. v2 writes a
JSON report, detached <report>.sig (hex Ed25519 signature over EXACT report bytes),
and a JSON receipt-evidence file whose exact byte digest is in the signed report.
Each evidence record is also signed over canonical JSON (sorted keys, compact
separators, UTF-8, no NaN). No adapter is used. Semantic correctness and citation
quality are unmeasured; signatures authenticate assertions, not their truth.

Run with an EXISTING unencrypted Ed25519 private PEM (no key creation):
  python bench/verifiable_benchmark.py --tasks 3 --signing-key /path/private.pem
Verify with a trusted, independently supplied public PEM, plus original inputs:
  python bench/verifiable_benchmark.py --verify bench/verifiable_report.json --key /path/public.pem

Inputs are repeated local ingestions, not independent agent tasks. Latency is
monotonic complete ingestion + receipt-signing time. Complete ingestion includes
its internal file I/O, hashing, parsing and metadata work. Only benchmark-level
pre/post validation hashes, snapshot preparation, key loading, report signing and
disk export are excluded. Reported median/min/max describe only this sample;
no population tail, semantic, citation, model, network or deployment claims.

POSIX qualification only: requires O_NOFOLLOW and O_NONBLOCK; unsupported systems
(including Windows) fail closed, never silently weakening file-open flags. The
bounded captured input is parsed from a private TemporaryDirectory snapshot;
this is not parser sandboxing or protection against a compromised same-account
process. Original source bytes must still match after the run and at verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
import statistics
import sys
import tempfile
import time
from pathlib import Path

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

_REPO = Path(__file__).resolve().parents[1]
FORMAT = "axiom-ingestion-signing-v2"
MAX_TASKS = 1000
MAX_REPORT_BYTES = 2 * 1024 * 1024
MAX_EVIDENCE_BYTES = 2 * 1024 * 1024
MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_KEY_BYTES = 16 * 1024
SAMPLE_CAVEAT = "Descriptive median/range of repeated local ingestions only; no population tail estimate."


def _require_posix() -> None:
    """Do not degrade no-follow/nonblocking guarantees on unsupported platforms."""
    if os.name != "posix" or any(
            not isinstance(getattr(os, flag, None), int) or getattr(os, flag, 0) <= 0
            for flag in ("O_NOFOLLOW", "O_NONBLOCK")):
        raise ValueError(
            "Benchmark file access requires POSIX with O_NOFOLLOW and O_NONBLOCK; "
            "run on a supported POSIX host (Windows is unsupported). "
            "Required safety flags will not be disabled.")


def _read_bounded(path: str | Path, limit: int) -> bytes:
    """POSIX-only bounded read; reject symlinks, devices, directories and pipes."""
    _require_posix()
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError("Expected a bounded regular file")
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("File exceeds byte budget")
    return data


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _load_json(data: bytes):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("Non-finite JSON number")

    return json.loads(data, object_pairs_hook=unique, parse_constant=invalid)


def _count(tasks: int) -> None:
    if type(tasks) is not int or not 1 <= tasks <= MAX_TASKS:
        raise ValueError(f"tasks must be an integer from 1 to {MAX_TASKS}")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _metrics(results: list[dict]) -> dict:
    times = [row["latency_ms"] for row in results]
    return {
        "sample_count": len(times),
        "median_ms": statistics.median(times),
        "min_ms": min(times),
        "max_ms": max(times),
        "sample_caveat": SAMPLE_CAVEAT,
        "semantic_correctness": "unmeasured",
        "citation_quality": "unmeasured",
    }


def _write_new(path: Path, data: bytes) -> None:
    # Refuse overwrites (including symlinks), particularly accidental key/input
    # clobbering. A partial run can leave files; use a fresh output name to retry.
    with path.open("xb") as stream:
        stream.write(data)


def run_benchmark(tasks: int = 3, out: str = "bench/verifiable_report.json", *,
                  signing_key: str | Path | None = None,
                  document: str | Path | None = None) -> dict:
    """Measure local ingestion and Ed25519 receipt signing. Never create keys."""
    _require_posix()
    _count(tasks)
    if signing_key is None:
        raise ValueError("An existing Ed25519 signing_key is required")
    private = serialization.load_pem_private_key(_read_bounded(signing_key, MAX_KEY_BYTES), password=None)
    if not isinstance(private, Ed25519PrivateKey):
        raise ValueError("Expected an Ed25519 private key")
    source = Path(document) if document is not None else _REPO / "fixtures/demo/sample_nda.docx"
    # Use absolute original input paths; verification requires those exact bytes.
    source = source.absolute()
    source_bytes = _read_bounded(source, MAX_INPUT_BYTES)
    source_hash = _digest(source_bytes)
    out_path = Path(out)
    evidence_path = out_path.with_name(out_path.name + ".receipts.json")
    signature_path = out_path.with_name(out_path.name + ".sig")
    for path in (out_path, evidence_path, signature_path):
        if path.exists() or path.is_symlink():
            raise ValueError(f"Refusing to overwrite output: {path}")

    # The only Axiom runtime import, confined to benchmark execution. Verification
    # imports neither the ingestor nor any signing adapter/audit implementation.
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from kernel.sidecar.ingestor import IngestorImpl

    ingestor = IngestorImpl()
    results, receipts = [], []
    # Parse only bytes captured by our bounded read, never reopen the original
    # through the multi-read ingestion pipeline. TemporaryDirectory is private
    # (0700 on POSIX); it is not isolation from hostile same-account processes.
    with tempfile.TemporaryDirectory(prefix="axiom-bench-") as directory:
        snapshot = Path(directory) / ("input" + source.suffix)
        _write_new(snapshot, source_bytes)
        for index in range(1, tasks + 1):
            start = time.monotonic()
            chunks, doc, pages = ingestor.ingest(str(snapshot))
            extract_ms = (time.monotonic() - start) * 1000
            if doc.sha256 != source_hash:
                raise ValueError("Snapshot does not match captured input bytes")
            record = {"task": index, "operation": "ingest", "input_sha256": source_hash,
                      "chunks": len(chunks), "pages": len(pages)}
            signed = private.sign(_json_bytes(record)).hex()
            latency_ms = (time.monotonic() - start) * 1000
            receipts.append({"record": record, "signature": signed})
            results.append({**record, "extract_ms": extract_ms, "latency_ms": latency_ms})
    if _digest(_read_bounded(source, MAX_INPUT_BYTES)) != source_hash:
        raise ValueError("Input changed during benchmark")
    evidence_bytes = _json_bytes({"format": FORMAT, "receipts": receipts})
    report = {
        "format": FORMAT,
        "benchmark": "Local ingestion/signing microbenchmark",
        "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tasks_requested": tasks, "tasks_run": len(results),
        "input": {"path": str(source), "sha256": source_hash, "bytes": len(source_bytes)},
        "metrics": _metrics(results), "results": results,
        "evidence": {"file": evidence_path.name, "sha256": _digest(evidence_bytes),
                     "bytes": len(evidence_bytes)},
    }
    report_bytes = _json_bytes(report)
    if len(report_bytes) > MAX_REPORT_BYTES or len(evidence_bytes) > MAX_EVIDENCE_BYTES:
        raise ValueError("Output exceeds verification byte budget")
    signature = private.sign(report_bytes).hex().encode("ascii")
    _write_new(evidence_path, evidence_bytes)
    _write_new(out_path, report_bytes)
    _write_new(signature_path, signature)
    return report


def verify_report(report_path: str | Path, key: str | Path) -> bool:
    """Read-only verification with caller trust anchor; fail closed on bad input.

    Authentication precedes parsing referenced paths. Signature proves provenance
    of the exact report/evidence, NOT measurement accuracy or document quality.
    All inputs must still exist. Receipt paths must be sibling basenames. Nothing
    is fetched, keys are never generated, and no Axiom runtime is imported.
    Unsupported platforms raise actionable ValueError before any file is opened.
    """
    _require_posix()
    try:
        path = Path(report_path)
        public = serialization.load_pem_public_key(_read_bounded(key, MAX_KEY_BYTES))
        if not isinstance(public, Ed25519PublicKey):
            return False
        raw = _read_bounded(path, MAX_REPORT_BYTES)
        sig = _read_bounded(path.with_name(path.name + ".sig"), 128)
        if len(sig) != 128:
            return False
        public.verify(bytes.fromhex(sig.decode("ascii")), raw)
        report = _load_json(raw)
        if not isinstance(report, dict) or set(report) != {
                "format", "benchmark", "date", "tasks_requested", "tasks_run",
                "input", "metrics", "results", "evidence"}:
            return False
        if (report["format"] != FORMAT
                or report["benchmark"] != "Local ingestion/signing microbenchmark"
                or not isinstance(report["date"], str)):
            return False
        count = report["tasks_run"]
        _count(count)
        if type(report["tasks_requested"]) is not int or report["tasks_requested"] != count:
            return False
        results = report["results"]
        if not isinstance(results, list) or len(results) != count:
            return False
        evidence = report["evidence"]
        if not isinstance(evidence, dict) or set(evidence) != {"file", "sha256", "bytes"}:
            return False
        name = evidence["file"]
        if not isinstance(name, str) or name in ("", ".", "..") or "/" in name or "\\" in name:
            return False
        evidence_raw = _read_bounded(path.parent / name, MAX_EVIDENCE_BYTES)
        if (type(evidence["bytes"]) is not int or len(evidence_raw) != evidence["bytes"]
                or _digest(evidence_raw) != evidence["sha256"]):
            return False
        payload = _load_json(evidence_raw)
        if (not isinstance(payload, dict) or set(payload) != {"format", "receipts"}
                or payload["format"] != FORMAT or not isinstance(payload["receipts"], list)
                or len(payload["receipts"]) != count):
            return False
        source = report["input"]
        if not isinstance(source, dict) or set(source) != {"path", "sha256", "bytes"}:
            return False
        if not isinstance(source["path"], str) or not Path(source["path"]).is_absolute():
            return False
        input_bytes = _read_bounded(source["path"], MAX_INPUT_BYTES)
        if (type(source["bytes"]) is not int or len(input_bytes) != source["bytes"]
                or _digest(input_bytes) != source["sha256"]):
            return False
        for index, (row, receipt) in enumerate(zip(results, payload["receipts"]), 1):
            if (not isinstance(row, dict) or set(row) != {
                    "task", "operation", "input_sha256", "chunks", "pages", "extract_ms", "latency_ms"}
                    or not isinstance(receipt, dict) or set(receipt) != {"record", "signature"}):
                return False
            for field in ("extract_ms", "latency_ms"):
                value = row[field]
                if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                    return False
            if row["extract_ms"] > row["latency_ms"]:
                return False
            for field in ("task", "chunks", "pages"):
                if type(row[field]) is not int or row[field] < (0 if field == "chunks" else 1):
                    return False
            record = {field: row[field] for field in ("task", "operation", "input_sha256", "chunks", "pages")}
            if (record["task"] != index or record["operation"] != "ingest"
                    or record["input_sha256"] != source["sha256"]):
                return False
            supplied_record = receipt["record"]
            if not isinstance(supplied_record, dict) or set(supplied_record) != set(record):
                return False
            for field in ("task", "chunks", "pages"):
                if (type(supplied_record[field]) is not int
                        or supplied_record[field] < (0 if field == "chunks" else 1)):
                    return False
            if (type(supplied_record["operation"]) is not str
                    or type(supplied_record["input_sha256"]) is not str):
                return False
            # Python equality aliases true/1/1.0; only exact canonical signed
            # message bytes establish consistency between the supplied receipt
            # and the validated row. Authenticate the supplied record itself.
            supplied_bytes = _json_bytes(supplied_record)
            if supplied_bytes != _json_bytes(record):
                return False
            public.verify(bytes.fromhex(receipt["signature"]), supplied_bytes)
        return _json_bytes(report["metrics"]) == _json_bytes(_metrics(results))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, InvalidSignature, UnsupportedAlgorithm,
            RecursionError, OverflowError):
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tasks", type=int, default=3)
    ap.add_argument("--out", default="bench/verifiable_report.json")
    ap.add_argument("--document", help="local input (default: bundled NDA)")
    ap.add_argument("--signing-key", help="existing Ed25519 private PEM; no key creation")
    ap.add_argument("--verify", metavar="REPORT")
    ap.add_argument("--key", help="trusted public Ed25519 PEM, required for verification")
    args = ap.parse_args()
    if args.verify:
        if not args.key:
            ap.error("--verify requires --key (trusted public PEM)")
        try:
            ok = verify_report(args.verify, args.key)
        except ValueError as exc:
            print(f"VERIFY: FAILED: {exc}", file=sys.stderr)
            return 1
        print("VERIFY: OK (authenticity/integrity only)" if ok else "VERIFY: FAILED")
        return 0 if ok else 1
    if not args.signing_key:
        ap.error("benchmark execution requires --signing-key; v2 does not create keys")
    try:
        report = run_benchmark(args.tasks, args.out, signing_key=args.signing_key, document=args.document)
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        print(f"BENCHMARK: FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
