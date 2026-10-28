"""Credential-safe local probe evidence tests; no network or model is contacted."""
import importlib.util
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("live_probe", ROOT / "scripts/axiom-live-e2e.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)
TOKEN = "ab" * 32  # Public synthetic fixture; not a deployment credential.


class ProbeEvidenceTests(unittest.TestCase):
    def test_env_token_validation(self):
        for token in ["", "bad", "a" * 63, "g" * 64, "a" * 63 + "\n"]:
            with self.subTest(token_length=len(token)), patch.dict(os.environ, {"AXIOM_API_TOKEN": token}, clear=True):
                with self.assertRaises(ValueError):
                    probe.paired_token()
        with patch.dict(os.environ, {"AXIOM_API_TOKEN": TOKEN}, clear=True):
            self.assertEqual(probe.paired_token(), TOKEN)

    def test_pairing_file_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "token"
            with patch.dict(os.environ, {"AXIOM_PAIRING_FILE": str(p)}, clear=True):
                p.write_text(TOKEN + "\n")
                p.chmod(0o600)
                self.assertEqual(probe.paired_token(), TOKEN)
                p.write_text(TOKEN * 10)
                with self.assertRaises(ValueError):
                    probe.paired_token()

    def test_recursive_token_redaction_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "report.json"
            probe.write_evidence(p, {TOKEN: ["echo:" + TOKEN, {"x": TOKEN}], "passed": False}, TOKEN)
            data = p.read_text()
            self.assertNotIn(TOKEN, data)
            self.assertIn("[REDACTED_PAIRING_TOKEN]", data)
            self.assertFalse(json.loads(data)["passed"])
            with self.assertRaises(FileExistsError):
                probe.write_evidence(p, {"changed": True}, TOKEN)
            self.assertEqual(p.read_text(), data)

    def test_numeric_token_echo_is_redacted(self):
        token = "1" * 64
        probe._validated_token(token)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "report.json"
            probe.write_evidence(p, {"metadata": {"echo": int(token), int(token): "key"}}, token)
            self.assertNotIn(token, p.read_text())
            self.assertIn("[REDACTED_PAIRING_TOKEN]", p.read_text())
            json.loads(p.read_text())

    def test_response_byte_budget_fails_closed(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, budget):
                self.budget = budget
                return b"x" * budget
        class Opener:
            def open(self, *args, **kwargs): return Response()
        with patch.object(probe.urllib.request, "build_opener", return_value=Opener()):
            with self.assertRaisesRegex(ValueError, "byte budget"):
                probe.request(7437, "/health")

    def test_reported_inventory_identity_is_strict(self):
        identity = {"name": "fixture:latest", "digest": "a" * 64, "size": 1024}
        ready = {"ready": True, "configured_model": identity["name"], "installed_models": [identity],
                 "expected_digest": "a" * 64, "identity_check_scope": "reported-only"}
        self.assertEqual(probe.reported_model_identity(ready), identity)
        for bad in [{**ready, "expected_digest": None},
                    {**ready, "expected_digest": "A" * 64},
                    {**ready, "expected_digest": "b" * 64},
                    {**ready, "identity_check_scope": None},
                    {**ready, "identity_check_scope": "attested"},
                    {**ready, "configured_model": "bad name"},
                    {**ready, "ready": 1}, {**ready, "installed_models": []},
                    {**ready, "installed_models": [identity, identity]},
                    {**ready, "installed_models": [{**identity, "size": True}]},
                    {**ready, "installed_models": [{**identity, "digest": ""}]}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                probe.reported_model_identity(bad)

    def test_loaded_report_requires_matching_digest(self):
        identity = {"name": "fixture:latest", "digest": "a" * 64, "size": 1024}
        probe.check_reported_loaded_model({"models": [identity]}, identity)
        for bad in [{}, {"models": []}, {"models": [{**identity, "digest": "b" * 64}]},
                    {"models": [identity, identity]},
                    {"models": [identity, {**identity, "digest": "b" * 64}]},
                    {"models": [{**identity, "model": "conflicting-model"}]}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                probe.check_reported_loaded_model(bad, identity)

    @unittest.skipUnless(os.name == "posix", "POSIX pairing-file contract")
    def test_insecure_or_special_pairing_files_fail(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "token"
            p.write_text(TOKEN)
            p.chmod(0o644)
            with patch.dict(os.environ, {"AXIOM_PAIRING_FILE": str(p)}, clear=True):
                with self.assertRaises(ValueError): probe.paired_token()
                p.unlink()
                os.mkfifo(p)
                with self.assertRaises(ValueError): probe.paired_token()
                p.unlink()
                actual = Path(d) / "actual"
                actual.write_text(TOKEN)
                actual.chmod(0o600)
                p.symlink_to(actual)
                with self.assertRaises(OSError): probe.paired_token()

    def test_preview_and_cancel_types_are_strict(self):
        good = {"suggestion": "x", "char_count": 1, "word_count": 1}
        probe.validate_preview_response(good)
        for bad in [{**good, "char_count": True}, {**good, "char_count": 1.0},
                    {**good, "suggestion": 7}, {**good, "suggestion": " "},
                    {**good, "word_count": False}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                probe.validate_preview_response(bad)
        for expected in (True, False):
            probe.validate_cancellation({"cancelled": expected}, expected)
            for bad in [{"cancelled": "false"}, {"cancelled": 0}, {"cancelled": 1}, {}, []]:
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    probe.validate_cancellation(bad, expected)

    def test_complete_probe_with_synthetic_http_contract(self):
        # Tests the probe, NOT a real runtime/model. No socket is opened.
        identity = {"name": "fixture:latest", "digest": "a" * 64, "size": 1024}
        ready = {"ready": True, "configured_model": identity["name"], "installed_models": [identity],
                 "expected_digest": "a" * 64, "identity_check_scope": "reported-only"}
        for invalid in (None, "count", "active_cancel", "idle_cancel"):
            release = threading.Event()
            active = threading.Event()
            def request(port, path, token=None, payload=None, headers=None):
                if path == "/health": return 200, {}
                if path == "/readiness": return (200, ready) if token == TOKEN else (401, {})
                if path == "/api/version": return 200, {"version": "fixture"}
                if path == "/api/show": return 200, {"details": {"x": 1}, "model_info": {"x": 1}}
                if path == "/api/ps": return 200, {"models": [identity]}
                if token != TOKEN: return 401, {}
                if headers: return 403, {}
                if path == "/cancel":
                    if active.is_set():
                        active.clear(); release.set()
                        return 200, {"cancelled": "false" if invalid == "active_cancel" else True}
                    return 200, {"cancelled": 0 if invalid == "idle_cancel" else False}
                context = payload["context"]
                if "extra" in payload: return 422, {}
                if not context.strip() or len(context) > 16000: return 400, {}
                if context.startswith("Write a detailed"):
                    active.set()
                    if not release.wait(2): raise RuntimeError("fixture cancellation timeout")
                    return 499, {}
                return 200, {"suggestion": "x", "char_count": True if invalid == "count" else 1, "word_count": 1}
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as d:
                path = Path(d) / "report.json"
                with patch.dict(os.environ, {"AXIOM_API_TOKEN": TOKEN}, clear=True), \
                     patch.object(probe, "request", side_effect=request), \
                     patch.object(probe, "PROMPTS", ["first fixture", "second fixture"]), \
                     patch("sys.argv", ["probe", "--output", str(path)]):
                    if invalid is None:
                        probe.main()
                    else:
                        with self.assertRaises(RuntimeError): probe.main()
                evidence = json.loads(path.read_text())
                self.assertIs(evidence["passed"], invalid is None)
                self.assertIs(evidence["backend_locality_verified"], False)
                self.assertNotIn(TOKEN, path.read_text())

    def test_failed_probe_saves_limits_without_exception_secret(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "report.json"
            with patch.dict(os.environ, {"AXIOM_API_TOKEN": TOKEN}, clear=True), \
                 patch.object(probe, "request", side_effect=RuntimeError(TOKEN)), \
                 patch("sys.argv", ["probe", "--output", str(p)]):
                with self.assertRaises(RuntimeError) as failure:
                    probe.main()
                self.assertNotIn(TOKEN, str(failure.exception))
            data = p.read_text()
            self.assertNotIn(TOKEN, data)
            result = json.loads(data)
            for flag in ["passed", "backend_locality_verified", "offline_operation_verified", "native_ui_tested", "production_qualified"]:
                self.assertIs(result[flag], False)
            self.assertEqual(result["error_type"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()
