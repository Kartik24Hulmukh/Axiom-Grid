"""Bound completed preview state without deleting in-flight provenance."""
from concurrent.futures import ThreadPoolExecutor

from kernel.core.data_model import Action, ActionKind, BBox, Chunk, Document, Extraction
from kernel.core.provenance import ProvenanceLogImpl


def register(log, identity):
    doc = Document(doc_id=f"doc-{identity}", source_path="local.txt")
    chunk = Chunk(chunk_id=f"chunk-{identity}", doc_id=doc.doc_id, page=1,
                  bbox=BBox(0, 0, 1, 1), text="evidence")
    ext = Extraction(ext_id=f"ext-{identity}", pack_id="test", field_name="test",
                     value="evidence", chunk_id=chunk.chunk_id)
    action = Action(action_id=f"action-{identity}", ext_id=ext.ext_id,
                    kind=ActionKind.SUGGEST, target_app="notepad", payload={"value": "evidence"})
    log.register_document(doc)
    log.register_chunk(chunk)
    log.register_extraction(ext)
    log.register_action(action)
    return doc, ext


def test_retention_preserves_active_and_retires_whole_graph():
    log = ProvenanceLogImpl()
    active, active_ext = register(log, "active")
    for i in range(100):
        doc, _ = register(log, i)
        log.complete_document(doc.doc_id, retain=4)
    assert log.stats == {"documents": 5, "chunks": 5, "extractions": 5, "actions": 5}
    assert log.get_provenance(active_ext.ext_id).is_complete
    assert not log.get_provenance("ext-0").is_complete
    assert log.action_for_extraction("ext-0") is None
    assert log.action_for_extraction("ext-99") is not None
    log.complete_document(active.doc_id, retain=4)
    assert log.stats["documents"] == 4


def test_concurrent_registration_and_lookup_are_consistent():
    log = ProvenanceLogImpl()
    def work(i):
        doc, ext = register(log, i)
        assert log.action_for_extraction(ext.ext_id).ext_id == ext.ext_id
        assert log.get_provenance(ext.ext_id).is_complete
        log.complete_document(doc.doc_id, retain=100)
    with ThreadPoolExecutor(max_workers=100) as pool:
        list(pool.map(work, range(1000)))
    assert log.stats == {"documents": 100, "chunks": 100, "extractions": 100, "actions": 100}