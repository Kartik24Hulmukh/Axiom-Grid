"""
Kairo Phantom — P0.1 Runnable Artifact Test

Tests that `make run` (via scripts/qa_pipeline.py) produces:
  1. A grounded answer with source region for an answerable question
  2. A refusal for an unanswerable question

This test is FAILING-CAPABLE: if the pipeline breaks (grounding verifier
returns BLOCK for a grounded question, or returns a grounded answer for an
unanswerable question), this test will fail.

No mocks, no stubs. Uses the real ingestor + real grounding verifier.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from scripts.qa_pipeline import answer_question


# ---------------------------------------------------------------------------
# Helper: run the Q&A pipeline as a subprocess (simulates `make run`)
# ---------------------------------------------------------------------------

def _run_qa(doc: str, question: str) -> dict:
    """Run qa_pipeline.py as a subprocess and return parsed JSON output."""
    result = subprocess.run(
        [sys.executable, "scripts/qa_pipeline.py",
         "--doc", doc, "--question", question, "--json"],
        capture_output=True, text=True, timeout=30,
        cwd=str(_REPO_ROOT),
    )
    if result.returncode not in (0, 1):
        # exit 0 = grounded, exit 1 = refusal, both valid
        # exit 2+ = error
        raise RuntimeError(
            f"qa_pipeline.py exited with code {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Tests: Grounded answers (one per Pack)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("doc,question,expected_contains", [
    ("samples/invoice/sample_invoice_01.txt",
     "What is the invoice number?", "INV-2026-001"),
    ("samples/contract/sample_contract_01.txt",
     "What is the termination date?", "June 1, 2029"),
    ("samples/paper/sample_paper_01.txt",
     "What architecture does the paper propose?", "Transformer"),
])
def test_grounded_answer_produced(doc, question, expected_contains):
    """A grounded answer is produced with source region for answerable questions."""
    output = _run_qa(doc, question)

    assert output["grounded"] is True, (
        f"Expected grounded=True for '{question}' on {doc}, "
        f"but got grounded={output['grounded']}, text={output['text']!r}"
    )
    assert output["refused"] is False, (
        f"Expected refused=False for '{question}', but got refused=True"
    )
    assert expected_contains.lower() in output["text"].lower(), (
        f"Expected answer to contain '{expected_contains}', "
        f"but got: {output['text']!r}"
    )
    assert len(output["citations"]) > 0, (
        "Expected at least one citation for a grounded answer, got none"
    )
    # Every citation must have a page and bbox
    for cite in output["citations"]:
        assert cite["page"] is not None and cite["page"] > 0, (
            f"Citation missing valid page: {cite}"
        )
        assert cite["bbox"] is not None, (
            f"Citation missing bbox (no source region): {cite}"
        )
        assert len(cite["bbox"]) == 4, (
            f"Citation bbox must have 4 coordinates, got: {cite['bbox']}"
        )


# ---------------------------------------------------------------------------
# Tests: Refusals (one per Pack)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("doc,question", [
    ("samples/invoice/sample_invoice_01.txt",
     "What is the CEO's salary?"),
    ("samples/contract/sample_contract_01.txt",
     "What is the annual revenue of the Licensor?"),
    ("samples/paper/sample_paper_01.txt",
     "What is the author's home address?"),
])
def test_refusal_produced_for_unanswerable(doc, question):
    """A refusal is produced for unanswerable questions (no source → no answer)."""
    output = _run_qa(doc, question)

    assert output["refused"] is True, (
        f"Expected refused=True for unanswerable question '{question}' on {doc}, "
        f"but got refused={output['refused']}, grounded={output['grounded']}, "
        f"text={output['text']!r}"
    )
    assert output["grounded"] is False, (
        f"Expected grounded=False for unanswerable question, "
        f"but got grounded=True (ungrounded answer leaked!)"
    )
    assert len(output["citations"]) == 0, (
        f"Expected no citations for a refusal, but got {len(output['citations'])}"
    )


# ---------------------------------------------------------------------------
# Test: make run command works (integration with Makefile)
# ---------------------------------------------------------------------------

def test_make_run_works():
    """The `make run` command works on the bundled samples (skips when make is unavailable)."""
    import shutil
    if shutil.which("make") is None:
        import pytest
        pytest.skip("make not installed on this platform")
    result = subprocess.run(
        ["make", "run",
         f"DOC=samples/invoice/sample_invoice_01.txt",
         'Q=What is the invoice number?'],
        capture_output=True, text=True, timeout=30,
        cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"make run failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "INV-2026-001" in result.stdout, (
        f"Expected 'INV-2026-001' in make run output, got: {result.stdout}"
    )
    assert "page 1" in result.stdout, (
        f"Expected 'page 1' (source region) in make run output, got: {result.stdout}"
    )


# ---------------------------------------------------------------------------
# Test: Direct API call (no subprocess) for unit-level verification
# ---------------------------------------------------------------------------

def test_answer_question_grounded_direct():
    """Direct call to answer_question() produces a grounded answer."""
    answer = answer_question(
        "samples/invoice/sample_invoice_01.txt",
        "What is the total amount due?",
    )
    assert answer.grounded is True
    assert answer.refused is False
    assert "1250" in answer.text
    assert len(answer.citations) > 0
    cite = answer.citations[0]
    assert cite.page == 1
    assert cite.bbox is not None


def test_answer_question_refusal_direct():
    """Direct call to answer_question() produces a refusal for unanswerable."""
    answer = answer_question(
        "samples/invoice/sample_invoice_01.txt",
        "What is the CEO's salary?",
    )
    assert answer.refused is True
    assert answer.grounded is False
    assert len(answer.citations) == 0


# ---------------------------------------------------------------------------
# Test: Failing-capable — if grounding is broken, this test catches it
# ---------------------------------------------------------------------------

def test_grounding_break_detection():
    """If the grounding verifier is broken (always returns BLOCK),
    no grounded answers are produced. This test verifies the pipeline
    actually depends on the grounding verifier working.

    We verify by checking that a known-answerable question produces
    a grounded answer — if the cascade were broken, this would fail.
    """
    answer = answer_question(
        "samples/contract/sample_contract_01.txt",
        "Which state's laws govern this agreement?",
    )
    assert answer.grounded is True, (
        "Grounding cascade appears broken: a known-answerable question "
        "did not produce a grounded answer. The verifier may be returning "
        "BLOCK for everything."
    )
    assert "delaware" in answer.text.lower(), (
        f"Expected 'Delaware' in answer, got: {answer.text!r}"
    )
