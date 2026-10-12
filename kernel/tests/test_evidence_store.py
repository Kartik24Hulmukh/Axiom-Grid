"""Atomic durable source chains, ownership, quotas and review conflict oracles."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import sqlite3
import pytest
from kernel.core.data_model import Document, Chunk, BBox, Extraction, Anchor, GroundingMethod, Action
from kernel.sidecar.evidence_store import EvidenceStore, ReviewConflict, EvidenceBudgetExceeded


def graph():
    doc = Document(source_path='fixture.txt', sha256='fixture-only')
    chunk = Chunk(doc_id=doc.doc_id, page=1, bbox=BBox(0,0,1,1), text='Alice')
    ext = Extraction(chunk_id=chunk.chunk_id, field_name='author', value='Alice', method=GroundingMethod.EXACT,
                     anchors=(Anchor(chunk_id=chunk.chunk_id, page=1, bbox=chunk.bbox, char_span=(0,5)),))
    return doc, chunk, ext


def test_roundtrip_reopen_other_connection_and_ownership(tmp_path):
    path=tmp_path/'evidence.db'; a=EvidenceStore(path); b=EvidenceStore(path)
    doc,c,e=graph(); action=Action(ext_id=e.ext_id)
    a.publish('a',doc,[c],[e],[action],{'scope':'fixture'})
    a.close(); a.reopen()
    for store in (a,b):
        chain=store.chain('a',e.ext_id)
        assert chain.is_complete and chain.extraction==e and chain.chunk==c and chain.document==doc
        assert store.chain('a',action.action_id).action==action
        assert not store.chain('b',e.ext_id).is_complete
        assert store.graph('b',doc.doc_id) is None
        assert store.traces('b')==[]
    a.close();b.close()


def test_unknown_mismatched_stale_and_concurrent_review(tmp_path):
    a=EvidenceStore(tmp_path/'e.db');b=EvidenceStore(tmp_path/'e.db');doc,c,e=graph()
    a.publish('a',doc,[c],[e])
    with pytest.raises(KeyError):a.review('b',e.ext_id,'author','Alice','Bob','fixture')
    with pytest.raises(KeyError):a.review('a','missing','author','Alice','Bob','fixture')
    with pytest.raises(ReviewConflict):a.review('a',e.ext_id,'wrong','Alice','Bob','fixture')
    def review(store):
        try:return store.review('a',e.ext_id,'author','Alice','Bob','fixture',0)['revision']
        except ReviewConflict:return 'conflict'
    with ThreadPoolExecutor(2) as pool:
        outcomes=list(pool.map(review,[a,b]))
    assert sorted(map(str,outcomes))==['1','conflict']
    with pytest.raises(ReviewConflict):a.review('a',e.ext_id,'author','Alice','Charlie','fixture',0)
    assert b.review('a',e.ext_id,'author','Bob','Charlie','fixture',1)['revision']==2
    assert a.chain('a',e.ext_id).extraction.value=='Alice'
    assert a.chunks_for_doc('a',doc.doc_id)[0].text=='Alice'
    a.close();b.close()


def test_retention_expiry_and_transaction_rollback(tmp_path):
    store=EvidenceStore(tmp_path/'e.db',retain=1);d,c,e=graph();store.publish('a',d,[c],[e])
    d2,c2,e2=graph();store.publish('a',d2,[c2],[e2]);assert store.graph('a',d.doc_id) is None
    assert not store.chain('a',e.ext_id).is_complete
    with pytest.raises(ValueError):store.publish('a',d,[c],[replace(e,chunk_id='wrong')])
    with pytest.raises(ValueError):store.publish('a',d,[c,c],[e])
    with pytest.raises(ValueError):store.publish('a',d,[c],[e],[Action(ext_id='wrong')])
    assert store.graph('a',d2.doc_id)
    with pytest.raises(sqlite3.IntegrityError):store.publish('a',d2,[c2],[e2])
    assert store.graph('a',d2.doc_id)
    with store._db:store._db.execute('UPDATE evidence_graphs SET completed=0')
    assert store.graph('a',d2.doc_id) is None
    with pytest.raises(KeyError):store.review('a',e2.ext_id,'author','Alice','Bob','fixture')
    store.close()


def test_byte_budget_fails_without_partial_publication(tmp_path):
    store=EvidenceStore(tmp_path/'e.db',max_graph_bytes=128,max_tenant_bytes=128)
    d,c,e=graph()
    with pytest.raises(EvidenceBudgetExceeded):store.publish('a',d,[c],[e])
    assert store.graph('a',d.doc_id) is None
    store.close()


def test_review_calibration_stays_in_credential_and_expiry_scope(tmp_path):
    from kernel.sidecar.evidence_store import ScopedReviewLookup
    from kernel.sidecar.quality_gate import LocalQualityGate
    store=EvidenceStore(tmp_path/'e.db');doc,c,e=graph();e=replace(e,confidence=.8)
    store.publish('a',doc,[c],[e]);gate=LocalQualityGate(ScopedReviewLookup(store,'a'))
    assert gate.check(e).calibrated_confidence==.8
    store.review('a',e.ext_id,'author','Alice','Bob','fixture',0)
    assert gate.check(e).calibrated_confidence==.65
    assert LocalQualityGate(ScopedReviewLookup(store,'b')).check(e).calibrated_confidence==.8
    assert store.chain('a',e.ext_id).extraction.value=='Alice'
    with store._db:store._db.execute('UPDATE evidence_graphs SET completed=0')
    assert gate.check(e).calibrated_confidence==.8
    store.close()


def test_review_byte_quota_is_atomic_including_utf8_and_source(tmp_path):
    store=EvidenceStore(tmp_path/'e.db',max_review_bytes=16);d,c,e=graph();store.publish('a',d,[c],[e])
    with pytest.raises(EvidenceBudgetExceeded):store.review('a',e.ext_id,'author','Alice','界'*4,'fixture',0)
    assert store.current_review('a',e.ext_id)['revision']==0
    assert store.review('a',e.ext_id,'author','Alice','Bob','ok',0)['revision']==1
    store.close()


def test_durable_health_and_private_database_mode(tmp_path):
    store=EvidenceStore(tmp_path/'e.db');store.healthcheck()
    assert store.path.stat().st_mode & 0o777==0o600
    store.close()
    with pytest.raises(RuntimeError):store.healthcheck()


def test_simultaneous_cold_connections_serialize_schema_migration(tmp_path):
    import threading
    path=tmp_path/'shared.db';barrier=threading.Barrier(8)
    def start(_):
        barrier.wait(timeout=5)
        store=EvidenceStore(path)
        try:store.healthcheck();return True
        finally:store.close()
    with ThreadPoolExecutor(8) as pool:assert all(pool.map(start,range(8)))


def test_unresolved_closed_refusal_does_not_poison_document_publication(tmp_path):
    from kernel.core.data_model import ExtractionStatus
    store=EvidenceStore(tmp_path/'e.db');d,c,e=graph()
    refused=replace(e,chunk_id='',anchors=(),method=GroundingMethod.BLOCK,status=ExtractionStatus.PENDING_REVIEW)
    store.publish('a',d,[c],[refused])
    assert store.chunks_for_doc('a',d.doc_id)==[c]
    assert not store.chain('a',refused.ext_id).is_complete
    with pytest.raises(KeyError):store.review('a',refused.ext_id,'author','Alice','Bob','fixture')
    store.close()
