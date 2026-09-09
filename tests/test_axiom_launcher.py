"""Stdlib-only launcher regression tests; no inherited pytest dependencies."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("launcher", Path(__file__).resolve().parents[1] / "scripts/axiom-launch.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)

class LauncherTests(unittest.TestCase):
    def test_ephemeral_token_overrides_inherited_secret(self):
        with patch.dict(os.environ, {"AXIOM_API_TOKEN": "never-reuse"}):
            first = launcher.credential_env("test:latest")
            second = launcher.credential_env("test:latest")
        self.assertNotEqual(first["AXIOM_API_TOKEN"], second["AXIOM_API_TOKEN"])
        self.assertEqual(len(bytes.fromhex(first["AXIOM_API_TOKEN"])), 32)
        self.assertEqual(first["AXIOM_MODEL"], "test:latest")
        self.assertEqual(first["KAIRO_OFFLINE"], "1")

    def test_invalid_model_is_rejected(self):
        for model in ["", " ", "x" * 257, "bad\nmodel"]:
            with self.assertRaises(ValueError): launcher.credential_env(model)

    def test_stop_only_owned_process(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        launcher.stop(child)
        self.assertIsNotNone(child.poll())
        launcher.stop(child)
        launcher.stop(None)

    def test_redirect_is_refused(self):
        import urllib.request, urllib.error
        with self.assertRaises(urllib.error.HTTPError) as caught:
            launcher.NoRedirect().redirect_request(urllib.request.Request(launcher.BASE), None, 302, "", {}, "https://example.com")
        caught.exception.close()

if __name__ == "__main__": unittest.main()
