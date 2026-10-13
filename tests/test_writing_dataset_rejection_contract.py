"""Malformed-file oracle for actual validator; NOT a training-asset substitute.

Copies exact validator bytes into an isolated temporary layout. Only an
intentionally malformed outer JSON line is exercised; no successful training
examples, production asset, parser/Path/pytest substitution or skip changes.
"""
from pathlib import Path
import runpy

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_actual_validator_reports_malformed_outer_json(tmp_path):
    tests_dir = tmp_path / "tests"
    training_dir = tmp_path / "training_data"
    tests_dir.mkdir()
    training_dir.mkdir()
    original = ROOT / "tests" / "test_writing_dataset.py"
    copied = tests_dir / original.name
    copied.write_bytes(original.read_bytes())
    # Satisfy ONLY the existing line-count admission so the real negative
    # outer-JSON branch is reached. Every line is invalid training data;
    # this file is temporary, never the repository's release asset.
    corrupt = training_dir / "kairo_writing_dataset_5k.jsonl"
    corrupt.write_text("{invalid-json\n" + "not-training-data\n" * 4999, encoding="utf-8")
    actual = runpy.run_path(str(copied))
    with pytest.raises(pytest.fail.Exception, match="Invalid JSON at line 1:"):
        actual["test_writing_dataset_validation"]()
    assert copied.read_bytes() == original.read_bytes()
