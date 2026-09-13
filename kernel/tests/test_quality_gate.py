"""
Tests for LocalQualityGate.
"""

import pytest

from kernel.core.contracts import GateVerdict
from kernel.core.data_model import Anchor, Correction, Extraction, GroundingMethod
from kernel.sidecar.quality_gate import LocalQualityGate


class MockCorrectionStore:
    """Mock correction store for testing LocalQualityGate."""

    def __init__(self):
        self.corrections_by_field: dict[str, list[Correction]] = {}

    def search_similar_corrections(
        self, field_name: str, value: str, k: int = 5
    ) -> list[Correction]:
        return self.corrections_by_field.get(field_name, [])[:k]


def test_grounded_extraction_passes():
    """Test that a well-grounded extraction with high confidence passes."""
    store = MockCorrectionStore()
    gate = LocalQualityGate(store)
    
    ext = Extraction(
        field_name="author",
        value="Dr. Margaret Chen",
        confidence=0.9,
        chunk_id="chunk-123",
        method=GroundingMethod.EXACT,
        anchors=(Anchor(chunk_id="chunk-123"),),
    )
    result = gate.check(ext)
    assert result.verdict == GateVerdict.PASS
    assert result.calibrated_confidence == 0.9
    assert len(result.reasons) == 0


def test_ungrounded_extraction_blocked():
    """Test that an extraction without a chunk_id gets blocked."""
    store = MockCorrectionStore()
    gate = LocalQualityGate(store)
    
    ext = Extraction(
        field_name="author",
        value="Dr. Margaret Chen",
        confidence=0.9,
        chunk_id="",  # Ungrounded
    )
    result = gate.check(ext)
    assert result.verdict == GateVerdict.BLOCK
    assert result.calibrated_confidence < 0.2
    assert any("UNGROUNDED" in reason for reason in result.reasons)


def test_correction_lowers_confidence():
    """Test that matching corrections with different corrected values lower confidence."""
    store = MockCorrectionStore()
    gate = LocalQualityGate(store)
    
    # Register a correction where the value was edited from "Margaret Chen" to "Dr. Margaret Chen"
    # So if the extractor tries to output "Margaret Chen", there is a contradicting correction.
    corr = Correction(
        corr_id="corr-1",
        ext_id="ext-orig",
        original="Margaret Chen",
        corrected="Dr. Margaret Chen",
    )
    store.corrections_by_field["author"] = [corr]

    # Now check an extraction proposing "Margaret Chen" (conflicting correction exists)
    ext = Extraction(
        field_name="author",
        value="Margaret Chen",
        confidence=0.8,
        chunk_id="chunk-123",
        method=GroundingMethod.EXACT,
        anchors=(Anchor(chunk_id="chunk-123"),),
    )
    result = gate.check(ext)
    # 0.8 - 0.15 = 0.65. Still above 0.5 (PASS)
    assert result.verdict == GateVerdict.PASS
    assert result.calibrated_confidence == 0.65
    assert any("CORRECTION_CONFLICT" in reason for reason in result.reasons)
    assert any("CONFIDENCE_LOWERED" in reason for reason in result.reasons)


def test_low_confidence_routes_to_flag():
    """Test that confidence < 0.5 but >= 0.2 routes to FLAG."""
    store = MockCorrectionStore()
    gate = LocalQualityGate(store)
    
    ext = Extraction(
        field_name="author",
        value="Jane Doe",
        confidence=0.4,  # Under 0.5 flag threshold
        chunk_id="chunk-123",
        method=GroundingMethod.EXACT,
        anchors=(Anchor(chunk_id="chunk-123"),),
    )
    result = gate.check(ext)
    assert result.verdict == GateVerdict.FLAG
    assert result.calibrated_confidence == 0.4
    assert any("VERDICT_FLAG" in reason for reason in result.reasons)


def test_very_low_confidence_routes_to_block():
    """Test that confidence < 0.2 routes to BLOCK."""
    store = MockCorrectionStore()
    gate = LocalQualityGate(store)
    
    ext = Extraction(
        field_name="author",
        value="Jane Doe",
        confidence=0.15,  # Under 0.2 block threshold
        chunk_id="chunk-123",
        method=GroundingMethod.EXACT,
        anchors=(Anchor(chunk_id="chunk-123"),),
    )
    result = gate.check(ext)
    assert result.verdict == GateVerdict.BLOCK
    assert result.calibrated_confidence == 0.15
    assert any("VERDICT_BLOCK" in reason for reason in result.reasons)


def test_invalid_gate_thresholds():
    """Test that LocalQualityGate raises ValueError if block_threshold >= flag_threshold."""
    store = MockCorrectionStore()
    with pytest.raises(ValueError) as exc_info:
        LocalQualityGate(store, flag_threshold=0.3, block_threshold=0.4)
    assert "block_threshold" in str(exc_info.value)
