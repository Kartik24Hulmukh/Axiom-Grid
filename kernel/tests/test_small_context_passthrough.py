"""Small offline extraction contexts preserve bytes and skip optional engines."""
import sys

from kernel.core.data_model import BBox, Chunk
from kairo.context.compressor import compress_document_chunks


def test_small_context_never_imports_optional_engine(monkeypatch):
    monkeypatch.setitem(sys.modules, "headroom", None)
    chunks = [Chunk(chunk_id="small", text="Invoice number: AX-42", page=1,
                    bbox=BBox(0, 0, 10, 10))]
    output, stats = compress_document_chunks(chunks, passthrough_below_bytes=4096)
    assert output == chunks
    assert output[0] is chunks[0]
    assert stats.tokens_saved == 0 and stats.tokens_before == stats.tokens_after
    assert stats.transforms_applied == ["small_document_passthrough_estimated_tokens"]


def test_byte_budget_counts_unicode_bytes_not_characters(monkeypatch):
    monkeypatch.setitem(sys.modules, "headroom", None)
    chunks = [Chunk(chunk_id="large", text="界" * 10, page=1, bbox=BBox(0, 0, 10, 10))]
    _, stats = compress_document_chunks(chunks, passthrough_below_bytes=10)
    assert "small_document_passthrough_estimated_tokens" not in stats.transforms_applied