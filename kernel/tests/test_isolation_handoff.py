"""Real spawned parsing and explicitly isolated parent-handoff contract checks."""
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from kernel.sidecar.ingestor import IngestorImpl
from kernel.sidecar.isolated_ingest import (
    ParsedDocumentIngestor,
    ingest_isolated_document,
)


def test_large_result_is_drained_before_child_join(tmp_path):
    path = tmp_path / "large.txt"
    text = ("A real local parsing payload beyond the OS pipe buffer. " * 20 + "\n") * 180
    path.write_text(text)
    chunks, doc, pages = ingest_isolated_document(str(path), timeout=10)
    assert sum(len(chunk.text) for chunk in chunks) > 65536
    assert all(chunk.bbox is not None for chunk in chunks)
    assert doc.sha256
    assert pages


def test_preparsed_source_rejects_another_document():
    ingestor = ParsedDocumentIngestor("a.pdf", ([], None, []))
    assert ingestor.ingest("a.pdf") == ([], None, [])
    with pytest.raises(ValueError, match="different source"):
        ingestor.ingest("b.pdf")


def test_http_pipeline_never_reparses_isolated_result_in_parent(tmp_path, monkeypatch):
    # Deliberate boundary oracle: actual spawned parsing is tested above.
    from kernel.sidecar import isolated_ingest
    from overlay import server

    parsed = IngestorImpl().ingest(str(server.FIXTURES_DIR / "sample_memo_01.txt"))
    path = tmp_path / "handoff.pdf"
    path.write_bytes(b"%PDF-1.4 handoff-contract-only")
    parsed = (parsed[0], replace(parsed[1], source_path=str(path)), parsed[2])
    called = []

    def isolated(filepath, timeout):
        called.append(filepath)
        return parsed

    def forbidden(*args, **kwargs):
        raise AssertionError("The isolated input was reparsed in the parent")

    monkeypatch.setenv("AXIOM_EXTRACTION_ISOLATION", "process")
    monkeypatch.setattr(isolated_ingest, "ingest_isolated_document", isolated)
    monkeypatch.setattr(IngestorImpl, "ingest", forbidden)
    with TestClient(server.app) as client:
        response = client.post("/api/extract-document", json={"file": str(path)})
    assert response.status_code == 200, response.text
    assert called == [str(path)]
    assert response.json()["fields"]