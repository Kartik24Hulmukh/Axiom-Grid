"""Isolated real-profile harness; not part of default test collection.

Run: /data/axiom-minvenv/bin/python -I tests/profile/pdf_absent_engine_guard.py
Requires actually absent fitz/opendataloader/olmocr/surya and real pdfplumber.
Wrong profile is a hard error, never a skip. No imports are intercepted and no
engine availability flags, parser methods, or output values are substituted.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
ENGINES = ("fitz", "opendataloader", "olmocr", "surya")
DISTRIBUTIONS = ("PyMuPDF", "PyMuPDFb", "opendataloader", "opendataloader-pdf", "olmocr", "surya-ocr")


def check_profile() -> None:
    for name in ENGINES:
        if name in sys.modules or importlib.util.find_spec(name) is not None:
            raise RuntimeError(f"Blocked: optional engine discoverable/imported: {name}")
    for name in DISTRIBUTIONS:
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        raise RuntimeError(f"Blocked: optional engine distribution present: {name} {version}")
    if importlib.util.find_spec("pdfplumber") is None:
        raise RuntimeError("Blocked: real pdfplumber is required")
    print(f"PROFILE {sys.executable}; optional engines absent; "
          f"pdfplumber={importlib.metadata.version('pdfplumber')}", flush=True)


# Check the real interpreter before making the repository importable.
check_profile()
sys.path.insert(0, str(ROOT / "kairo-sidecar"))
sys.path.insert(0, str(ROOT))
# Check again against the final import path, without importing optional engines.
check_profile()
from sidecar.parsers.pdf_extraction_engine import PdfExtractionEngine
from kairo.pdf.engine import extract_text_with_coords


class AbsentEngineGuard(unittest.TestCase):
    def assert_extraction_fails_closed(self, filename: str) -> None:
        source = ROOT / "fixtures" / "pdf" / filename
        self.assertTrue(source.is_file())
        engine = PdfExtractionEngine(offline_mode=True)
        # An uncaught import/model error is a test failure, not an accepted denial.
        with self.assertRaisesRegex(RuntimeError, "no extraction tier produced text"):
            result = engine.extract(str(source))
            print(f"BASELINE {filename}: text={result.text!r}, "
                  f"tier={result.tier_used}, confidence={result.confidence}, "
                  f"metadata={result.metadata}", flush=True)
        self.assertFalse(any(name in sys.modules for name in ENGINES))

    def test_born_digital_exhaustion_is_not_success(self) -> None:
        self.assert_extraction_fails_closed("s01_born_digital_report.pdf")

    def test_scanned_exhaustion_is_not_success(self) -> None:
        self.assert_extraction_fails_closed("s03_scanned_contract.pdf")

    def test_supported_real_pdfplumber_positive(self) -> None:
        text, boxes = extract_text_with_coords(
            str(ROOT / "fixtures/pdf/s01_born_digital_report.pdf"))
        self.assertTrue(text.strip())
        self.assertGreater(len(boxes), 0)
        self.assertTrue(all(box.text.strip() and box.x1 >= box.x0 and
                            box.y1 >= box.y0 and box.page >= 0 for box in boxes))
        self.assertFalse(any(name in sys.modules for name in ENGINES))
        print(f"SUPPORTED pdfplumber: chars={len(text)}, measured_boxes={len(boxes)}", flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
