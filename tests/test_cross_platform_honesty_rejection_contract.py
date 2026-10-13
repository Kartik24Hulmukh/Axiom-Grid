"""Actual README-claim rejection contracts, NOT native-platform verification.

Execute identical guard bytes with deliberately authored temporary README text.
No OS behavior, platform reports, successful workflow or CI proof is synthesized.
"""
from pathlib import Path
import runpy
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _actual_linux_guard(tmp_path, claim):
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    original = ROOT / "tests" / "test_cross_platform_honesty.py"
    copied = test_dir / original.name
    copied.write_bytes(original.read_bytes())
    (tmp_path / "README.md").write_text(claim + "\n", encoding="utf-8")
    prior_path = sys.path[:]
    try:
        actual = runpy.run_path(str(copied))
        assert copied.read_bytes() == original.read_bytes()
        actual["TestREADMEPlatformHonesty"]().test_linux_claim_honest()
    finally:
        # The original module prepends its temporary root at import time.
        sys.path[:] = prior_path


@pytest.mark.parametrize("claim", [
    "Linux | live ghost-typing | verified",
    "Linux | ghost-typing | VERIFIED",
    "Linux ghost-typing is verified",
    "Linux live ghost-typing is CI-verified",
])
def test_actual_linux_guard_rejects_unqualified_verified_claim(tmp_path, claim):
    with pytest.raises(pytest.fail.Exception, match="Linux ghost-typing"):
        _actual_linux_guard(tmp_path, claim)


@pytest.mark.parametrize("claim", [
    "Linux | ghost-typing | unverified",
    "Linux | ghost-typing | not verified",
    "Linux | ghost-typing | never verified",
    "Linux | ghost-typing | not CI-verified",
    "Linux | ghost-typing | scaffold; verified code only",
    "Linux | ghost-typing | pending; verified code only",
    "Linux | ghost-typing | compile-only verified code",
])
def test_actual_linux_guard_retains_explicit_non_native_qualifications(tmp_path, claim):
    _actual_linux_guard(tmp_path, claim)
