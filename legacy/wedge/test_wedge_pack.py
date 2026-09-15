"""
Tests for WedgePack extraction and oracle scoring.
"""

import os
import json
import pytest
from pathlib import Path

from kernel.core.data_model import Chunk, BBox
from legacy.wedge.pack import WedgePack  # wedge pack relocated to legacy/ (obsolete packs.wedge path)


def test_wedge_pack_fields():
    """Test that WedgePack exposes the correct 12 fields."""
    pack = WedgePack()
    assert len(pack.fields) == 12
    assert "classification_marking" in pack.fields
    assert "pii_spans" in pack.fields


def test_wedge_pack_extract_basic():
    """Test that WedgePack extracts fields from basic chunks."""
    pack = WedgePack()
    chunks = [
        Chunk(
            chunk_id="c1",
            doc_id="d1",
            page=1,
            bbox=BBox(0,0,1,1),
            text="CLASSIFICATION: SECRET//NOFORN\nFROM: Office of the Director, Central Analysis Group (CAG)\nAUTHOR: Dr. Margaret Chen\nDATE OF INFORMATION: 15 March 2003\nSUBJECT: Assessment of Weapons Procurement Networks"
        )
    ]
    extractions = pack.extract(chunks)
    assert len(extractions) > 0

    field_map = {e.field_name: e.value for e in extractions}
    assert field_map.get("classification_marking") == "SECRET"
    assert field_map.get("author") == "Dr. Margaret Chen"
    assert field_map.get("date_of_information") == "2003-03-15"
    assert "Central Analysis Group" in field_map.get("originating_org", "")


def test_wedge_pack_oracle():
    """Test that the oracle runs on fixtures and scores accuracy correctly."""
    pack = WedgePack()
    fixtures_dir = str(Path(__file__).parents[2] / "fixtures" / "wedge")
    
    scores = pack.oracle(fixtures_dir)
    assert isinstance(scores, dict)
    assert len(scores) == 12
    for field_name in pack.fields:
        assert field_name in scores
        # Accuracy should be a float between 0.0 and 1.0
        assert 0.0 <= scores[field_name] <= 1.0
