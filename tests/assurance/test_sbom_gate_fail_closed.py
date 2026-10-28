"""Legacy supply-chain tools must not fabricate signing or scan success."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / 'scripts/ci/sbom_gate.py'
spec = importlib.util.spec_from_file_location('legacy_sbom_gate', PATH)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class SbomFailClosedTests(unittest.TestCase):
    def test_signing_refuses_without_writes_even_with_stale_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, signature = Path(tmp) / 'sbom.json', Path(tmp) / 'sig'
            source.write_text('{}')
            signature.write_text('stale-not-approved')
            self.assertIs(gate.sign_sbom(str(source), str(signature)), False)
            self.assertEqual(signature.read_text(), 'stale-not-approved')
            self.assertIs(gate.sign_sbom(str(source), str(Path(tmp) / 'new')), False)
            self.assertFalse((Path(tmp) / 'new').exists())

    def test_missing_input_cannot_sign(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIs(gate.sign_sbom(str(Path(tmp) / 'absent'), str(Path(tmp) / 'sig')), False)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_cli_refuses_without_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, '-B', str(PATH)], cwd=tmp,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertIn('production_qualified=false', result.stderr)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_import_does_not_configure_root_logging(self):
        code = ('import logging,runpy; root=logging.getLogger(); before=list(root.handlers); '
                f'runpy.run_path({str(PATH)!r}); assert root.handlers == before')
        result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_main_refuses_before_helpers_files_or_subprocesses(self):
        with patch.object(gate, 'scan_for_secrets', side_effect=AssertionError('scan')), \
             patch.object(gate, 'run_cargo_audit', side_effect=AssertionError('audit')), \
             patch.object(gate, 'generate_sbom', side_effect=AssertionError('inventory')), \
             patch.object(gate, 'sign_sbom', side_effect=AssertionError('sign')), \
             patch('builtins.open', side_effect=AssertionError('open')), \
             patch('os.open', side_effect=AssertionError('os.open')), \
             patch('os.makedirs', side_effect=AssertionError('mkdir')), \
             patch('subprocess.run', side_effect=AssertionError('subprocess')):
            self.assertEqual(gate.main(), 2)

    def test_module_initialization_has_no_scan_write_or_process_side_effects(self):
        # Compile before installing traps: source loading itself is legitimate.
        code = compile(PATH.read_bytes(), str(PATH), 'exec')
        namespace = {'__name__': 'sbom_import_probe', '__file__': str(PATH)}
        with patch('builtins.open', side_effect=AssertionError('open')), \
             patch('os.open', side_effect=AssertionError('os.open')), \
             patch('os.walk', side_effect=AssertionError('walk')), \
             patch('os.makedirs', side_effect=AssertionError('mkdir')), \
             patch('subprocess.run', side_effect=AssertionError('subprocess')), \
             patch('logging.basicConfig', side_effect=AssertionError('logging')):
            exec(code, namespace)
        self.assertIn('main', namespace)

    def test_cargo_audit_missing_manifest_tooling_and_errors_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIs(gate.run_cargo_audit(tmp), False)
            (Path(tmp) / 'Cargo.toml').write_text('[package]')
            for exc in (FileNotFoundError(), RuntimeError('synthetic'),
                        subprocess.TimeoutExpired('cargo', 120)):
                with self.subTest(error=type(exc).__name__), patch('subprocess.run', side_effect=exc):
                    self.assertIs(gate.run_cargo_audit(tmp), False)

    def test_cargo_audit_requires_successful_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'Cargo.toml').write_text('[package]')
            for code in (0, 1):
                with self.subTest(code=code), patch('subprocess.run', return_value=
                        subprocess.CompletedProcess(['cargo'], code, stdout='{}')):
                    self.assertIs(gate.run_cargo_audit(tmp), code == 0)


if __name__ == '__main__':
    unittest.main()
