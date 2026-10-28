"""Isolated stdlib tests: reported evidence is never production certification."""
from __future__ import annotations

import builtins
import contextlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
SPEC = importlib.util.spec_from_file_location("owned_release_evidence", SCRIPTS / "release_evidence.py")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)
REV = "a" * 40
NOW = datetime(2026, 10, 28, 19, 0, tzinfo=timezone.utc)


def document(now=NOW):
    return {"schema_version": 1, "revision": REV, "profile": "authorized-preview",
            "run_id": "isolated-test-run", "generated_at": now.isoformat(),
            "synthetic": False,
            "metrics": {"passed": 90, "total": 100, "bmc": 0.074,
                        "vlm_calls": 4, "total_calls": 100}}


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="release-evidence-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "input.json"

    def validate(self, data, **kwargs):
        return evidence.validate_evidence(data, expected_revision=kwargs.get("revision", REV),
                                         expected_profile=kwargs.get("profile", "authorized-preview"),
                                         now=kwargs.get("now", NOW))

    def read(self, raw):
        self.path.write_bytes(raw if isinstance(raw, bytes) else raw.encode())
        return evidence.load_evidence(self.path)

    def test_acceptance_is_scoped_not_qualification(self):
        result = self.validate(document())
        self.assertEqual(result["status"], "accepted")
        self.assertIs(result["production_qualified"], False)
        for word in ("authenticity", "attestation", "native", "offline", "production"):
            self.assertIn(word, result["limitations"])
        self.assertNotIn("run_id", result)

    def test_valid_roundtrip_and_revision_case(self):
        expected = document(); expected["metrics"]["bmc"] = Decimal("0.074")
        self.assertEqual(self.read(json.dumps(document())), expected)
        self.validate(document(), revision=REV.upper())
        data = document(); data["revision"] = REV.upper(); self.validate(data)

    def test_all_required_fields_and_unknown_keys(self):
        for key in document():
            with self.subTest(missing=key):
                data = document(); del data[key]
                with self.assertRaises(evidence.EvidenceError): self.validate(data)
        data = document(); data["production_qualified"] = True
        with self.assertRaises(evidence.EvidenceError): self.validate(data)
        for key in document()["metrics"]:
            with self.subTest(metric=key):
                data = document(); del data["metrics"][key]
                with self.assertRaises(evidence.EvidenceError): self.validate(data)
        data = document(); data["metrics"]["bmc_typo"] = 0
        with self.assertRaises(evidence.EvidenceError): self.validate(data)

    def test_invalid_metadata(self):
        cases = {"schema_version": [True, False, "1", 1.0, 0, 2, None],
                 "revision": [None, 123, "a"*39, "g"*40, REV+"\n", "b"*40],
                 "profile": [None, 1, "", " \n", "different", "authorized-preview "],
                 "run_id": [None, 1, "", " \n"],
                 "synthetic": [True, 0, 1, None, "false", [], {}],
                 "metrics": [None, [], "", 0]}
        for key, values in cases.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    data = document(); data[key] = value
                    with self.assertRaises(evidence.EvidenceError): self.validate(data)
        for value in (None, True, 40, "", "z"*40):
            with self.assertRaises(evidence.EvidenceError): self.validate(document(), revision=value)
        for value in (None, 1, "", " \n"):
            with self.assertRaises(evidence.EvidenceError): self.validate(document(), profile=value)

    def test_timestamp_format_and_invalid_calendar(self):
        for value in (None, 1, "2026-10-28", "2026-10-28T19:00:00",
                      "2026-10-28T19:00:00+01:00", "2026-10-28T19:00:00-00:00",
                      "2026-10-28t19:00:00z", "2026-02-30T19:00:00Z",
                      "2026-10-28T19:00:60Z", "2026-10-28T19:00:00Z\n"):
            with self.subTest(value=value):
                data = document(); data["generated_at"] = value
                with self.assertRaises(evidence.EvidenceError): self.validate(data)
        for value in ("2026-10-28T19:00:00Z", "2026-10-28T19:00:00.000000+00:00"):
            data = document(); data["generated_at"] = value; self.validate(data)
        with self.assertRaises(evidence.EvidenceError): self.validate(document(), now=NOW.replace(tzinfo=None))

    def test_fixed_freshness_boundaries(self):
        self.validate(document(NOW-timedelta(hours=24)))
        self.validate(document(NOW+timedelta(minutes=5)))
        for delta in (-timedelta(hours=24, microseconds=1), timedelta(minutes=5, microseconds=1)):
            with self.assertRaises(evidence.EvidenceError): self.validate(document(NOW+delta))

    def test_counts_strict_and_nonzero(self):
        for key in ("passed", "total", "vlm_calls", "total_calls"):
            for value in (True, False, "100", 90.0, None, -1, float("nan"), float("inf")):
                with self.subTest(key=key, value=value):
                    data = document(); data["metrics"][key] = value
                    with self.assertRaises(evidence.EvidenceError): self.validate(data)
        for updates in ({"passed":101}, {"total":0}, {"passed":0,"total":0},
                        {"total_calls":0}, {"vlm_calls":101}, {"passed":89}, {"vlm_calls":5}):
            data = document(); data["metrics"].update(updates)
            with self.assertRaises(evidence.EvidenceError): self.validate(data)
        data = document(); data["metrics"].update(passed=1,total=1,vlm_calls=0,total_calls=1)
        self.validate(data)

    def test_exact_integer_rate_thresholds(self):
        # The latter ratio rounds to .05 as float but is actually below it.
        n = 10**100
        data = document(); data["metrics"].update(vlm_calls=n-1,total_calls=20*n)
        self.validate(data)
        data["metrics"].update(passed=9*n-1,total=10*n)
        with self.assertRaises(evidence.EvidenceError): self.validate(data)

    def test_bmc_range_type_and_threshold(self):
        for value in (True, False, None, "0.01", -0.01, 1.01, 0.0740001,
                      float("nan"), float("inf"), -float("inf"), 10**1000):
            with self.subTest(value=str(value)[:30]):
                data = document(); data["metrics"]["bmc"] = value
                with self.assertRaises(evidence.EvidenceError): self.validate(data)
        for value in (0, 0.0, 0.074):
            data = document(); data["metrics"]["bmc"] = value; self.validate(data)

    def json_with_bmc(self, literal, now=NOW):
        return json.dumps(document(now)).replace('"bmc": 0.074', '"bmc": '+literal)

    def test_actual_json_decimal_precision_and_underflow(self):
        for literal in ("0.074000000000000001", "7.4000000000000001e-2", "-1e-9999"):
            with self.subTest(literal=literal):
                data = self.read(self.json_with_bmc(literal))
                self.assertIs(type(data["metrics"]["bmc"]), Decimal)
                self.assertEqual(data["metrics"]["bmc"], Decimal(literal))
                with self.assertRaises(evidence.EvidenceError): self.validate(data)
        for literal in ("0", "0.074", "7.4e-2", "74e-3", "1e-9999"):
            with self.subTest(literal=literal):
                data = self.read(self.json_with_bmc(literal))
                self.validate(data)
                self.assertEqual(data["metrics"]["bmc"], Decimal(literal))
        self.assertNotEqual(self.read(self.json_with_bmc("1e-9999"))["metrics"]["bmc"], 0)
        # Parsing/comparisons must not round to the ambient decimal precision.
        with localcontext() as ctx:
            ctx.prec = 2
            with self.assertRaises(evidence.EvidenceError):
                self.validate(self.read(self.json_with_bmc("0.074000000000000001")))

    def test_decimal_parser_overflow_policy(self):
        for literal in ("1e9999", "-1e9999", "1e999999999999", "1e999999999999999999999999999999"):
            with self.subTest(literal=literal):
                with self.assertRaises(evidence.EvidenceError): self.read(self.json_with_bmc(literal))
        # Large finite values may parse, but cannot pass BMC range validation.
        with self.assertRaises(evidence.EvidenceError):
            self.validate(self.read(self.json_with_bmc("1e308")))

    def test_direct_api_decimal_and_float_semantics(self):
        for value in (Decimal("0.074000000000000001"), Decimal("-1e-9999"),
                      Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity")):
            data = document(); data["metrics"]["bmc"] = value
            with self.assertRaises(evidence.EvidenceError): self.validate(data)
        # Floats supplied by callers have already lost their literal precision.
        data = document(); data["metrics"]["bmc"] = float("0.074000000000000001")
        self.validate(data)  # Defined as Decimal(str(0.074)), not original-literal proof.
        for key in ("passed", "total", "vlm_calls", "total_calls"):
            data = document(); data["metrics"][key] = Decimal(str(data["metrics"][key]))
            with self.assertRaises(evidence.EvidenceError): self.validate(data)

    def test_actual_json_decimal_cases_through_both_clis(self):
        args = ["--evidence",str(self.path),"--expected-revision",REV,
                "--expected-profile","authorized-preview"]
        for literal, exit_code in (("0.074000000000000001",1), ("-1e-9999",1),
                                   ("1e999999999999",1), ("0",0), ("0.074",0),
                                   ("7.4e-2",0), ("1e-9999",0)):
            self.path.write_text(self.json_with_bmc(literal, datetime.now(timezone.utc)))
            for script in ("release_evidence.py", "verify_production_gate.py"):
                with self.subTest(literal=literal,script=script):
                    result = self.cli(script,args)
                    self.assertEqual(result.returncode,exit_code,result.stderr)
                    data = json.loads(result.stdout)
                    self.assertEqual(data["status"], "accepted" if exit_code == 0 else "rejected")
                    self.assertIs(data["production_qualified"],False)

    def test_strict_json_rejections(self):
        for raw in ('', '{', 'null', '[]', '1', 'true', '"text"', '{} {}',
                    '{"x":1,"x":2}', '{"x":1,"\\u0078":2}',
                    '{"nested":{"x":1,"x":2}}',
                    '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}',
                    '{"x":1e9999}', '{"x":-1e9999}', '['*2000+']'*2000,
                    b'\xff', b'\xef\xbb\xbf{}'):
            with self.subTest(raw=repr(raw[:60])):
                with self.assertRaises(evidence.EvidenceError): self.read(raw)

    def test_bounded_read_and_file_errors(self):
        raw = json.dumps(document()).encode()
        data = self.read(raw+b' '*(evidence.MAX_BYTES-len(raw)))
        self.validate(data)
        with self.assertRaises(evidence.EvidenceError): self.read(b' '*(evidence.MAX_BYTES+1))
        with self.assertRaises(evidence.EvidenceError): evidence.load_evidence(self.root/'missing-SENSITIVE')
        with self.assertRaises(evidence.EvidenceError): evidence.load_evidence(self.root)
        if hasattr(os, "mkfifo"):
            fifo = self.root/'fifo'; os.mkfifo(fifo)
            with self.assertRaises(evidence.EvidenceError): evidence.load_evidence(fifo)

    def test_reader_closes_descriptors_on_success_and_rejection(self):
        real_open, real_close = os.open, os.close
        opened, closed = [], []
        def track_open(*args, **kwargs):
            fd = real_open(*args, **kwargs); opened.append(fd); return fd
        def track_close(fd):
            closed.append(fd); return real_close(fd)
        self.path.write_text('{}')
        with mock.patch.object(evidence.os, 'open', side_effect=track_open), \
             mock.patch.object(evidence.os, 'close', side_effect=track_close):
            with self.assertRaises(evidence.EvidenceError): evidence.load_evidence(self.root)
        self.assertEqual(opened, closed)
        # Stream ownership uses the C-level close; verify the captured fd is gone.
        opened.clear()
        with mock.patch.object(evidence.os, 'open', side_effect=track_open):
            self.assertEqual(evidence.load_evidence(self.path), {})
        with self.assertRaises(OSError): os.fstat(opened[0])

    def cli(self, script, args=()):
        env = dict(os.environ, HOME=str(self.root), PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, "-B", str(SCRIPTS/script), *args],
                              cwd=self.root, env=env, capture_output=True, text=True, timeout=10)

    def test_explicit_cli_both_entrypoints(self):
        self.path.write_text(json.dumps(document(datetime.now(timezone.utc))))
        args = ["--evidence",str(self.path),"--expected-revision",REV,
                "--expected-profile","authorized-preview"]
        for script in ("release_evidence.py", "verify_production_gate.py"):
            with self.subTest(script=script):
                result = self.cli(script,args)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIs(json.loads(result.stdout)["production_qualified"],False)
                for missing in ([],args[:2],args[2:]):
                    result = self.cli(script,missing)
                    self.assertEqual(result.returncode,2)
                result = self.cli(script,[*args,"--unknown-SENSITIVE"])
                self.assertEqual(result.returncode,2)
                self.assertNotIn("SENSITIVE",result.stdout+result.stderr)
        self.assertEqual({p.name for p in self.root.iterdir()}, {"input.json"})

    def test_cli_sanitized_rejection_and_no_discovery(self):
        self.path.write_text('{"SENSITIVE":1,"SENSITIVE":2}')
        args = ["--evidence",str(self.path),"--expected-revision",REV,
                "--expected-profile","authorized-preview"]
        result = self.cli("verify_production_gate.py", args)
        self.assertEqual(result.returncode,1)
        self.assertNotIn("SENSITIVE",result.stdout+result.stderr)
        self.assertNotIn(str(self.root),result.stdout+result.stderr)
        self.assertIs(json.loads(result.stdout)["production_qualified"],False)
        self.assertEqual(self.cli("verify_production_gate.py").returncode,2)
        self.assertEqual({p.name for p in self.root.iterdir()}, {"input.json"})

    def test_legacy_entrypoints_always_block_without_writes(self):
        for script in ("generate_certification.py", "verify_launch_checklist.py"):
            for args in ([], ["--anything"]):
                result = self.cli(script,args)
                self.assertEqual(result.returncode,1)
                self.assertIn("BLOCKED",result.stderr)
                self.assertEqual(result.stdout,"")
        self.assertEqual(list(self.root.iterdir()),[])

    def test_all_owned_imports_have_no_writes_or_runtime_imports(self):
        # Compile before blocking filesystem access; exec models module import.
        names = ("release_evidence.py", "verify_production_gate.py",
                 "generate_certification.py", "verify_launch_checklist.py")
        compiled = [(name,compile((SCRIPTS/name).read_text(),str(SCRIPTS/name),'exec')) for name in names]
        original_import = builtins.__import__
        def guarded_import(name,*args,**kwargs):
            if name.split('.')[0] in {"kernel","sidecar","httpx","requests","torch","ollama"}:
                raise AssertionError("Project runtime import during module import")
            return original_import(name,*args,**kwargs)
        output = io.StringIO()
        with mock.patch('builtins.open',side_effect=AssertionError('file access during import')), \
             mock.patch('os.open',side_effect=AssertionError('file access during import')), \
             mock.patch.object(Path,'write_text',side_effect=AssertionError('write during import')), \
             mock.patch.object(Path,'write_bytes',side_effect=AssertionError('write during import')), \
             mock.patch('builtins.__import__',side_effect=guarded_import), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            for name,code in compiled:
                exec(code,{'__name__':'import_audit_'+name[:-3], '__file__':str(SCRIPTS/name)})
        self.assertEqual(output.getvalue(),"")
        self.assertEqual(list(self.root.iterdir()),[])


if __name__ == "__main__":
    unittest.main()
