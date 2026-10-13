"""Release regressions for live-runner secrets and public signup claims."""

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "session21_melious_torture.py"
SITE = ROOT / "docs" / "index.html"


def test_live_runner_never_contains_embedded_credentials():
    source = RUNNER.read_text(encoding="utf-8")
    # Construct prefixes so this oracle itself cannot be mistaken for a token.
    assert "sk" + "-mel-" not in source
    assert "gh" + "p_" not in source
    assert 'os.environ["MELIOUS_API_KEY"] = KEY' not in source


def test_live_runner_fails_closed_without_environment_key():
    env = os.environ.copy()
    env.pop("MELIOUS_API_KEY", None)
    completed = subprocess.run(
        [sys.executable, str(RUNNER)], env=env, cwd=ROOT,
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert completed.returncode != 0
    assert "Set MELIOUS_API_KEY" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_public_site_does_not_claim_to_save_an_unwired_signup():
    html = SITE.read_text(encoding="utf-8")
    assert 'id="email-form"' not in html
    assert "https://github.com/Kartik24Hulmukh/Axiom-Grid" in html
    assert "https://github.com/Kartik24Hulmukh/Kairo-Phantom" not in html
    assert "LAUNCH-BLOCKERS.md" in html
