"""Offline stdlib unittest assurance for the v2 ingestion/signing benchmark."""
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SCRIPT = Path(__file__).resolve().parents[2] / "bench/verifiable_benchmark.py"
spec = importlib.util.spec_from_file_location("benchmark_assurance_subject", SCRIPT)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class BenchmarkAssuranceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.private = Ed25519PrivateKey.generate()
        self.private_path = self.root / "private.pem"
        self.private_path.write_bytes(self.private.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))
        self.public_path = self.root / "public.pem"
        self.public_path.write_bytes(self.private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        self.source = self.root / "source.txt"
        self.source.write_text("First paragraph.\n\nSecond paragraph.\n\nThird paragraph.\n\nFourth paragraph.", encoding="utf-8")
        self.report_path = self.root / "report.json"

    def run_bench(self, tasks=3):
        return bench.run_benchmark(tasks, str(self.report_path),
                                   signing_key=self.private_path, document=self.source)

    def verify(self):
        return bench.verify_report(self.report_path, self.public_path)

    def resign(self, report):
        raw = bench._json_bytes(report)
        self.report_path.write_bytes(raw)
        self.report_path.with_name("report.json.sig").write_text(self.private.sign(raw).hex())

    def test_positive_real_ingestion_hash_counts_and_honest_metrics(self):
        report = self.run_bench()
        self.assertTrue(self.verify())
        self.assertEqual(report["input"]["sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(report["tasks_run"], 3)
        self.assertTrue(all(row["chunks"] == 4 and row["pages"] == 1 for row in report["results"]))
        self.assertEqual(report["metrics"]["semantic_correctness"], "unmeasured")
        self.assertEqual(report["metrics"]["citation_quality"], "unmeasured")
        self.assertNotIn("p95_ms", report["metrics"])

    def test_unsupported_platform_fails_closed_with_actionable_error(self):
        # Simulates unsupported Windows; this is NOT a Windows qualification run.
        with patch.object(bench.os, "name", "nt"), patch.object(bench.os, "open") as opened:
            for call in (
                lambda: bench._read_bounded(self.source, 1024),
                lambda: self.run_bench(1),
                self.verify,
            ):
                with self.assertRaisesRegex(ValueError, "requires POSIX.*Windows is unsupported"):
                    call()
            opened.assert_not_called()

    def test_missing_required_posix_flags_fail_closed(self):
        for flag in ("O_NOFOLLOW", "O_NONBLOCK"):
            with self.subTest(flag=flag), patch.dict(bench.os.__dict__):
                delattr(bench.os, flag)
                with patch.object(bench.os, "open") as opened:
                    with self.assertRaisesRegex(ValueError, "Required safety flags will not be disabled"):
                        bench._read_bounded(self.source, 1024)
                    opened.assert_not_called()

    def test_snapshot_stays_stable_under_hostile_original_edits_after_capture(self):
        from kernel.sidecar.ingestor import IngestorImpl

        captured = self.source.read_bytes()
        poisoned = b"Hostile replacement: one paragraph, not four."
        read_bounded = bench._read_bounded
        real_ingest = IngestorImpl.ingest
        snapshots = []
        captured_once = False

        def capture_then_edit(path, limit):
            nonlocal captured_once
            data = read_bounded(path, limit)
            if Path(path) == self.source and not captured_once:
                captured_once = True
                self.source.write_bytes(poisoned)
            return data

        def inspect_snapshot(ingestor, path):
            snapshot = Path(path)
            self.assertNotEqual(snapshot, self.source)
            self.assertNotEqual(snapshot.parent, self.source.parent)
            self.assertEqual(snapshot.suffix, self.source.suffix)
            self.assertEqual(snapshot.parent.stat().st_mode & 0o077, 0)
            if not snapshots:
                self.assertEqual(self.source.read_bytes(), poisoned)
            self.source.write_bytes(poisoned)
            snapshots.append(snapshot)
            try:
                self.assertEqual(snapshot.read_bytes(), captured)
                chunks, document, pages = real_ingest(ingestor, path)
                self.assertEqual(len(chunks), 4)
                self.assertEqual(document.sha256, hashlib.sha256(captured).hexdigest())
                self.assertEqual(snapshot.read_bytes(), captured)
                self.assertEqual(self.source.read_bytes(), poisoned)
                return chunks, document, pages
            finally:
                # A transient attacker restores original before the final check.
                self.source.write_bytes(captured)

        with patch.object(bench, "_read_bounded", side_effect=capture_then_edit), patch.object(
                IngestorImpl, "ingest", autospec=True, side_effect=inspect_snapshot):
            report = self.run_bench(3)
        self.assertTrue(captured_once)
        self.assertEqual(len(snapshots), 3)
        self.assertTrue(all(not p.exists() for p in snapshots))
        self.assertEqual(report["input"]["path"], str(self.source))
        self.assertEqual(report["input"]["sha256"], hashlib.sha256(captured).hexdigest())
        self.assertTrue(self.verify())

    def test_persistent_original_edit_rejected_and_snapshot_cleaned(self):
        from kernel.sidecar.ingestor import IngestorImpl

        real_ingest = IngestorImpl.ingest
        snapshots = []

        def ingest_then_edit(ingestor, path):
            snapshots.append(Path(path))
            result = real_ingest(ingestor, path)
            self.source.write_text("Persistent change", encoding="utf-8")
            return result

        with patch.object(IngestorImpl, "ingest", autospec=True, side_effect=ingest_then_edit):
            with self.assertRaisesRegex(ValueError, "Input changed during benchmark"):
                self.run_bench(1)
        self.assertTrue(all(not p.exists() for p in snapshots))
        self.assertFalse(self.report_path.exists())

    def test_wrong_key(self):
        self.run_bench()
        self.public_path.write_bytes(Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        self.assertFalse(self.verify())

    def test_metric_edit_and_exact_byte_edit(self):
        report = self.run_bench()
        raw = self.report_path.read_bytes()
        report["metrics"]["median_ms"] += 1
        self.report_path.write_bytes(bench._json_bytes(report))
        self.assertFalse(self.verify())
        self.report_path.write_bytes(raw + b"\n")
        self.assertFalse(self.verify())

    def test_evidence_modification(self):
        report = self.run_bench()
        evidence = self.root / report["evidence"]["file"]
        evidence.write_bytes(evidence.read_bytes() + b"\n")
        self.assertFalse(self.verify())

    def test_receipt_signature_validated_even_with_resigned_digest(self):
        report = self.run_bench()
        evidence = self.root / report["evidence"]["file"]
        payload = json.loads(evidence.read_bytes())
        payload["receipts"][0]["signature"] = "00" * 64
        raw = bench._json_bytes(payload)
        evidence.write_bytes(raw)
        report["evidence"].update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
        self.resign(report)
        self.assertFalse(self.verify())

    def test_receipt_numeric_aliases_rejected_with_authenticated_outer_report(self):
        # All three integer fields are 1 so true and 1.0 compare equal in Python.
        self.source.write_text("One paragraph.", encoding="utf-8")
        original_report = self.run_bench(1)
        evidence_path = self.root / original_report["evidence"]["file"]
        original_payload = json.loads(evidence_path.read_bytes())
        original_receipt = original_payload["receipts"][0]
        original_signature = original_receipt["signature"]
        original_bytes = bench._json_bytes(original_receipt["record"])
        public = self.private.public_key()
        public.verify(bytes.fromhex(original_signature), original_bytes)
        for field in ("task", "chunks", "pages"):
            for alias in (True, 1.0):
                with self.subTest(field=field, alias=alias):
                    report = json.loads(json.dumps(original_report))
                    payload = json.loads(json.dumps(original_payload))
                    supplied = payload["receipts"][0]
                    self.assertIs(type(supplied["record"][field]), int)
                    self.assertEqual(supplied["record"][field], alias)
                    supplied["record"][field] = alias
                    self.assertEqual(supplied["signature"], original_signature)
                    changed_bytes = bench._json_bytes(supplied["record"])
                    self.assertNotEqual(changed_bytes, original_bytes)
                    with self.assertRaises(InvalidSignature):
                        public.verify(bytes.fromhex(original_signature), changed_bytes)
                    raw = bench._json_bytes(payload)
                    evidence_path.write_bytes(raw)
                    report["evidence"].update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
                    self.resign(report)
                    # This is authenticated malformed evidence, not outer tampering.
                    public.verify(bytes.fromhex((self.root / "report.json.sig").read_text()),
                                  self.report_path.read_bytes())
                    self.assertFalse(self.verify())

    def test_receipt_record_strict_schema_and_row_consistency(self):
        report = self.run_bench(1)
        evidence_path = self.root / report["evidence"]["file"]
        original_payload = json.loads(evidence_path.read_bytes())
        original_record = original_payload["receipts"][0]["record"]
        variants = [
            None,
            list(original_record),
            {k: v for k, v in original_record.items() if k != "pages"},
            {**original_record, "extra": 1},
            {**original_record, "operation": True},
            {**original_record, "input_sha256": 1},
            {**original_record, "task": "1"},
            {**original_record, "chunks": -1},
            {**original_record, "pages": 0},
            {**original_record, "chunks": original_record["chunks"] + 1},
        ]
        for record in variants:
            with self.subTest(record=record):
                payload = json.loads(json.dumps(original_payload))
                payload["receipts"][0]["record"] = record
                raw = bench._json_bytes(payload)
                evidence_path.write_bytes(raw)
                report["evidence"].update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
                self.resign(report)
                self.assertFalse(self.verify())

    def test_missing_files(self):
        report = self.run_bench()
        for path in (self.report_path, self.public_path, self.source,
                     self.root / report["evidence"]["file"], self.root / "report.json.sig"):
            with self.subTest(path=path.name):
                raw = path.read_bytes()
                path.unlink()
                self.assertFalse(self.verify())
                path.write_bytes(raw)

    def test_modified_source(self):
        self.run_bench()
        self.source.write_text("changed", encoding="utf-8")
        self.assertFalse(self.verify())

    def test_invalid_counts_before_key_or_ingestor_access(self):
        for tasks in (0, -1, 1001, True, 1.5, "3", None):
            with self.subTest(tasks=tasks), self.assertRaises(ValueError):
                bench.run_benchmark(tasks, str(self.report_path))
        self.assertFalse(self.report_path.exists())

    def test_signed_invalid_count_and_metrics(self):
        report = self.run_bench()
        for field, value in (("tasks_run", 0), ("tasks_requested", 2), ("tasks_requested", True)):
            changed = dict(report)
            changed[field] = value
            self.resign(changed)
            self.assertFalse(self.verify())
        report["metrics"]["median_ms"] = 999
        self.resign(report)
        self.assertFalse(self.verify())

    def test_verifier_is_read_only_without_private_key_or_runtime_imports(self):
        self.run_bench()
        self.private_path.unlink()
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        code = '''
import builtins, importlib.util, sys
original = builtins.__import__
def guarded(name, *a, **kw):
    if name.split('.')[0] in {'kernel', 'integrations', 'kairo'}:
        raise AssertionError('Axiom runtime import attempted: ' + name)
    return original(name, *a, **kw)
builtins.__import__ = guarded
spec = importlib.util.spec_from_file_location('subject', sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.verify_report(sys.argv[2], sys.argv[3])
'''
        result = subprocess.run([sys.executable, "-B", "-c", code, str(SCRIPT),
                                 str(self.report_path), str(self.public_path)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_malformed_and_bounded_inputs(self):
        self.run_bench()
        with patch.object(bench, "MAX_REPORT_BYTES", 8):
            self.assertFalse(self.verify())
        with patch.object(bench, "MAX_EVIDENCE_BYTES", 8):
            self.assertFalse(self.verify())
        with patch.object(bench, "MAX_INPUT_BYTES", 8):
            self.assertFalse(self.verify())
        self.public_path.write_bytes(b"not a key")
        self.assertFalse(self.verify())

    def test_authenticated_malformed_json(self):
        self.run_bench()
        for raw in (b"{", b'[]', b'{"format":1,"format":2}', b'{"x":NaN}'):
            self.report_path.write_bytes(raw)
            (self.root / "report.json.sig").write_text(self.private.sign(raw).hex())
            self.assertFalse(self.verify())

    def test_evidence_traversal_and_symlink_rejected(self):
        report = self.run_bench()
        original = report["evidence"]["file"]
        report["evidence"]["file"] = "../" + original
        self.resign(report)
        self.assertFalse(self.verify())
        report["evidence"]["file"] = original
        self.resign(report)
        evidence = self.root / original
        moved = self.root / "moved.json"
        evidence.rename(moved)
        evidence.symlink_to(moved)
        self.assertFalse(self.verify())

    def test_rejects_unknown_or_malformed_authenticated_shapes(self):
        original = self.run_bench()
        for mutate in (
            lambda r: r.update(correctness=1.0),
            lambda r: r["results"][0].update(chunks=True),
            lambda r: r["metrics"].update(sample_count=True),
            lambda r: r.update(results={"not": "a list"}),
            lambda r: r["evidence"].update(file="/absolute.json"),
        ):
            report = json.loads(json.dumps(original))
            mutate(report)
            self.resign(report)
            self.assertFalse(self.verify())

    def test_invalid_signature_and_key_byte_limits(self):
        self.run_bench()
        with patch.object(bench, "MAX_KEY_BYTES", 8):
            self.assertFalse(self.verify())
        signature = self.root / "report.json.sig"
        for data in (b"bad", b"z" * 128, b"0" * 129):
            signature.write_bytes(data)
            self.assertFalse(self.verify())

    def test_single_sample_and_no_overwrite(self):
        report = self.run_bench(1)
        metrics = report["metrics"]
        self.assertEqual(metrics["median_ms"], metrics["min_ms"])
        self.assertEqual(metrics["median_ms"], metrics["max_ms"])
        self.assertTrue(self.verify())
        with self.assertRaises(ValueError):
            self.run_bench(1)

    def test_cli_verify(self):
        self.run_bench(1)
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--verify",
                                 str(self.report_path), "--key", str(self.public_path)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("authenticity/integrity only", result.stdout)


if __name__ == "__main__":
    unittest.main()
