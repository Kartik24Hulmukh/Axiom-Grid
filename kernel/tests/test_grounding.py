"""
Tests for GroundingVerifierImpl.
"""

from kernel.core.data_model import BBox, Chunk, GroundingMethod
from kernel.core.grounding import (
    GroundingVerifierImpl,
    levenshtein_ratio,
    normalize_text,
)


def test_normalize_text():
    assert normalize_text("  Dr. Margaret Chen! $100 ") == "dr. margaret chen 100"


def test_levenshtein_ratio():
    assert levenshtein_ratio("test", "test") == 1.0
    assert levenshtein_ratio("test", "text") == 0.75
    assert levenshtein_ratio("", "abc") == 0.0


def test_exact_grounding():
    verifier = GroundingVerifierImpl()
    chunks = [
        Chunk(chunk_id="c1", text="The total amount payable is USD 250.00 immediately.", page=1, bbox=BBox(0, 0, 1, 1)),
        Chunk(chunk_id="c2", text="Please pay by credit card.", page=1, bbox=BBox(0, 0, 1, 1)),
    ]
    method, anchors = verifier.verify("USD 250.00", "", chunks)
    assert method == GroundingMethod.EXACT
    assert len(anchors) == 1
    assert anchors[0].chunk_id == "c1"
    assert anchors[0].char_span == (28, 38)


def test_fuzzy_grounding():
    verifier = GroundingVerifierImpl(fuzzy_threshold=0.9)
    chunks = [
        Chunk(chunk_id="c1", text="The vendor is Acme Corporation Inc.", page=1, bbox=BBox(0, 0, 1, 1)),
    ]
    # "Acme Corporatin" (typo) vs "Acme Corporation" in text
    method, anchors = verifier.verify("Acme Corporatin", "", chunks)
    assert method == GroundingMethod.FUZZY
    assert len(anchors) == 1
    assert anchors[0].chunk_id == "c1"


def test_semantic_grounding():
    # Set threshold lower to match the offline bag-of-words hash embedding similarity
    verifier = GroundingVerifierImpl(semantic_threshold=0.4)
    chunks = [
        Chunk(chunk_id="c1", text="The project schedule is delayed by six weeks.", page=1, bbox=BBox(0, 0, 1, 1)),
    ]
    # "delayed schedule" vs "project schedule is delayed by six weeks"
    method, anchors = verifier.verify("delayed schedule", "", chunks)
    assert method == GroundingMethod.SEMANTIC
    assert len(anchors) == 1
    assert anchors[0].chunk_id == "c1"


def test_block_grounding():
    verifier = GroundingVerifierImpl()
    chunks = [
        Chunk(chunk_id="c1", text="The project schedule is delayed by six weeks.", page=1, bbox=BBox(0, 0, 1, 1)),
    ]
    # Totally unrelated
    method, anchors = verifier.verify("banana shake", "", chunks)
    assert method == GroundingMethod.BLOCK
    assert len(anchors) == 0
