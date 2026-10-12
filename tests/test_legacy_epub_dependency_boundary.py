"""Focused missing-EbookLib behavior checks against the real legacy exporter.

Only the dependency import is blocked. No exporter/engine substitutes, skips,
package installation, model/provider calls or servers are used.
"""
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
_PROBE = r'''
import builtins
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, sys.argv[1])
from sidecar.exporters.kami_kpx import KPXExporter

original_import = builtins.__import__
def without_ebooklib(name, *args, **kwargs):
    if name.split(".", 1)[0] == "ebooklib":
        raise ModuleNotFoundError("No module named 'ebooklib'", name="ebooklib")
    return original_import(name, *args, **kwargs)

# Simulates a clean missing-dependency environment even if host has EbookLib.
builtins.__import__ = without_ebooklib
with tempfile.TemporaryDirectory() as directory:
    exporter = KPXExporter(output_dir=Path(directory))
    try:
        exporter.export_epub("# Review\nPlain content.", {"title": "Review"})
    except ModuleNotFoundError as exc:
        direct = {"exception": type(exc).__name__, "name": exc.name}
    else:
        raise AssertionError("Direct EPUB export did not fail without EbookLib")
    assert not list(Path(directory).iterdir()), "Direct export wrote an artifact"
    aggregate = exporter.export_all("# Review\nPlain content.", {"title": "Review"})
    results = aggregate["results"]
    output = {
        "direct": direct,
        "aggregate_ok": aggregate["ok"],
        "notification": aggregate["notification"],
        "epub_result": results["epub"],
        "remaining_artifacts_exist": {
            name: Path(results[name]).is_file()
            for name in ("html", "markdown", "latex", "json")
        },
        "epub_artifacts": len(list(Path(directory).glob("*.epub"))),
    }
    print(json.dumps(output))
'''


class TestLegacyEpubDependencyBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(
            [sys.executable, "-I", "-c", _PROBE, str(ROOT / "kairo-sidecar")],
            capture_output=True, text=True, check=True, timeout=20,
        )
        cls.observed = json.loads(result.stdout)

    def test_direct_real_epub_export_raises_missing_dependency(self):
        self.assertEqual(self.observed["direct"],
                         {"exception": "ModuleNotFoundError", "name": "ebooklib"})

    def test_aggregate_reports_requested_epub_failure(self):
        self.assertIs(self.observed["aggregate_ok"], False)
        self.assertEqual(self.observed["epub_result"], "FAILED: No module named 'ebooklib'")
        self.assertIn("4/5 formats exported", self.observed["notification"])
        self.assertIn("failed: epub", self.observed["notification"])
        self.assertNotIn("All formats exported", self.observed["notification"])

    def test_no_fake_epub_is_written_and_other_real_exports_remain(self):
        self.assertEqual(self.observed["epub_artifacts"], 0)
        self.assertEqual(self.observed["remaining_artifacts_exist"],
                         {name: True for name in ("html", "markdown", "latex", "json")})


if __name__ == "__main__":
    unittest.main()
