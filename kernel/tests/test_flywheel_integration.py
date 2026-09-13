"""
Kairo Phantom — Flywheel Integration Test (SPEC §S6, §S8)

Proves: a human correction demonstrably changes the quality gate's
handling of the next similar extraction.

This test is not a mock — it exercises the real MemoryStore, QualityGate,
and search_similar_corrections path end-to-end.
"""

from __future__ import annotations

from kernel.core.contracts import GateVerdict
from kernel.core.data_model import Anchor, Correction, Extraction, GroundingMethod
from kernel.sidecar.memory_store import MemoryStoreImpl
from kernel.sidecar.quality_gate import LocalQualityGate


def test_flywheel_correction_lowers_next_extraction_confidence():
    """
    Flywheel contract: after recording a correction for field X,
    a subsequent extraction for the same field with a similar value
    should have its confidence lowered by the quality gate.
    """
    # 1. Fresh in-memory store — no history
    store = MemoryStoreImpl(":memory:")
    gate = LocalQualityGate(store)

    # 2. First extraction (no corrections exist) — should PASS at 0.85
    ext_before = Extraction(
        field_name="author",
        value="Dr. Margaret Chen",
        confidence=0.85,
        chunk_id="chunk-abc",
        method=GroundingMethod.EXACT,
        anchors=(Anchor(chunk_id="chunk-abc"),),
    )
    result_before = gate.check(ext_before)
    assert result_before.verdict == GateVerdict.PASS, (
        f"Expected PASS for uncorrected extraction, got {result_before.verdict}"
    )
    conf_before = result_before.calibrated_confidence

    # 3. Record the extraction in the store (needed for JOIN in search_similar_corrections)
    store.record_extraction(ext_before)

    # 4. Record a correction — the human says the author was wrong
    correction = Correction(
        ext_id=ext_before.ext_id,
        original="Dr. Margaret Chen",
        corrected="Dr. M. A. Chen",
        reason="Name was partially extracted",
        by="test-user",
    )
    store.record_correction(correction)

    # 5. Second extraction (same field, similar value) — flywheel should lower confidence
    ext_after = Extraction(
        field_name="author",
        value="Dr. Margaret Chen",
        confidence=0.85,
        chunk_id="chunk-def",
        method=GroundingMethod.EXACT,
        anchors=(Anchor(chunk_id="chunk-def"),),
    )
    result_after = gate.check(ext_after)
    conf_after = result_after.calibrated_confidence

    # 6. Assert: confidence was lowered due to the stored correction
    assert conf_after < conf_before, (
        f"Flywheel FAILED: confidence was NOT lowered after correction. "
        f"Before={conf_before}, After={conf_after}"
    )


def test_flywheel_correction_can_trigger_flag_on_repeat():
    """
    A correction on a field with borderline confidence should push
    the next similar extraction into FLAG territory when the corrected
    value differs from the extraction value.
    """
    store = MemoryStoreImpl(":memory:")
    gate = LocalQualityGate(store)

    # First, store an extraction so the correction can be found via JOIN
    ext_original = Extraction(
        field_name="classification_marking",
        value="SECRET//NOFORN",
        confidence=0.90,
        chunk_id="chunk-orig",
        method=GroundingMethod.EXACT,
        anchors=(Anchor(chunk_id="chunk-orig"),),
    )
    store.record_extraction(ext_original)

    # Record a correction — the original value was wrong
    correction = Correction(
        ext_id=ext_original.ext_id,
        original="SECRET//NOFORN",
        corrected="SECRET",
        reason="NOFORN control was misidentified",
        by="test-user",
    )
    store.record_correction(correction)

    # Now a borderline extraction for the same field with the OLD (wrong) value
    # Correction penalty is 0.15 per contradiction, so 0.55 - 0.15 = 0.40
    # which is below the FLAG threshold (0.5)
    ext = Extraction(
        field_name="classification_marking",
        value="SECRET//NOFORN",
        confidence=0.55,  # borderline
        chunk_id="chunk-xyz",
        method=GroundingMethod.EXACT,
        anchors=(Anchor(chunk_id="chunk-xyz"),),
    )
    result = gate.check(ext)

    # With correction history + borderline confidence, the penalty should push
    # confidence below 0.5 into FLAG territory
    assert result.verdict == GateVerdict.FLAG, (
        f"Expected FLAG for corrected borderline extraction, "
        f"got {result.verdict} (confidence={result.calibrated_confidence})"
    )
