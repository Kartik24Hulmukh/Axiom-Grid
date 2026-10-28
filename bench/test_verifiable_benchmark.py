"""Offline v2 end-to-end benchmark tests (stdlib unittest; no pytest needed)."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from bench.verifiable_benchmark import FORMAT, run_benchmark, verify_report


class VerifiableBenchmarkTests(unittest.TestCase):
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
        self.source.write_text("Real ingestion fixture.\n\nSecond paragraph.", encoding="utf-8")
        self.out = self.root / "report.json"

    def test_benchmark_runs_and_signs(self):
        report = run_benchmark(tasks=3, out=str(self.out),
                               signing_key=self.private_path, document=self.source)
        self.assertEqual(report["tasks_requested"], 3)
        self.assertEqual(report["tasks_run"], 3)
        self.assertEqual(report["metrics"]["sample_count"], 3)
        self.assertEqual(report["metrics"]["semantic_correctness"], "unmeasured")
        self.assertEqual(report["metrics"]["citation_quality"], "unmeasured")
        for obsolete in ("all_actions_signed", "correctness", "citation_coverage", "p95_ms", "p99_ms"):
            self.assertNotIn(obsolete, report["metrics"])
        self.assertEqual(report["input"]["sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
        evidence_path = self.out.parent / report["evidence"]["file"]
        self.assertTrue(evidence_path.is_file())
        self.assertEqual(hashlib.sha256(evidence_path.read_bytes()).hexdigest(), report["evidence"]["sha256"])
        evidence = json.loads(evidence_path.read_bytes())
        self.assertEqual(len(evidence["receipts"]), 3)
        public = self.private.public_key()
        for index, (row, receipt) in enumerate(zip(report["results"], evidence["receipts"]), 1):
            self.assertEqual(row["task"], index)
            self.assertEqual(row["chunks"], 2)
            self.assertEqual(row["pages"], 1)
            self.assertGreaterEqual(row["extract_ms"], 0)
            self.assertGreaterEqual(row["latency_ms"], row["extract_ms"])
            self.assertEqual(receipt["record"]["input_sha256"], report["input"]["sha256"])
            # Check actual Ed25519 receipt signature, not merely its presence.
            canonical = json.dumps(receipt["record"], sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=False, allow_nan=False).encode("utf-8")
            public.verify(bytes.fromhex(receipt["signature"]), canonical)
        public.verify(bytes.fromhex((self.root / "report.json.sig").read_text()), self.out.read_bytes())
        self.assertTrue(verify_report(self.out, self.public_path))

    def test_benchmark_report_verifies(self):
        report = run_benchmark(tasks=2, out=str(self.out),
                               signing_key=self.private_path, document=self.source)
        # Verification needs only the independently supplied public key, not the signer.
        self.private_path.unlink()
        self.assertTrue(verify_report(self.out, self.public_path))
        data = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(data, report)
        self.assertEqual(data["format"], FORMAT)
        self.assertEqual(data["benchmark"], "Local ingestion/signing microbenchmark")
        self.assertEqual(data["tasks_run"], 2)
        wrong = self.root / "wrong-public.pem"
        wrong.write_bytes(Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        self.assertFalse(verify_report(self.out, wrong))
        data["metrics"]["median_ms"] += 1
        self.out.write_text(json.dumps(data), encoding="utf-8")
        self.assertFalse(verify_report(self.out, self.public_path))


if __name__ == "__main__":
    unittest.main()
