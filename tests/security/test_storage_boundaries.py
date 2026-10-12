"""Local synthetic storage attacks; no provider, keys, or load tests."""
import multiprocessing
import os
import sqlite3
import stat
from pathlib import Path

import pytest

from kernel.core.data_model import (
    Anchor,
    BBox,
    Chunk,
    Document,
    Extraction,
    GroundingMethod,
)
from kernel.sidecar.evidence_store import EvidenceStore, ReviewConflict
from overlay.document_store import DocumentStore


def publish(store):
    doc = Document(source_path='synthetic.txt')
    chunk = Chunk(doc_id=doc.doc_id, bbox=BBox(0, 0, 1, 1), text='Alice')
    ext = Extraction(chunk_id=chunk.chunk_id, field_name='author', value='Alice',
                     method=GroundingMethod.EXACT,
                     anchors=(Anchor(chunk_id=chunk.chunk_id, bbox=chunk.bbox, char_span=(0, 5)),))
    store.publish('local', doc, [chunk], [ext])
    return doc, ext


@pytest.mark.parametrize('kind', ['evidence', 'upload'])
@pytest.mark.parametrize('leaf', ['database', 'wal', 'shm'])
def test_reject_database_sidecar_symlinks_without_touching_victim(tmp_path, kind, leaf):
    root = tmp_path/'state'; root.mkdir(mode=0o700)
    victim = tmp_path/'victim'; victim.write_bytes(b'not a sqlite database'); victim.chmod(0o644)
    name = 'e.db' if kind == 'evidence' else 'uploads.db'
    suffix = {'database': '', 'wal': '-wal', 'shm': '-shm'}[leaf]
    (root/(name+suffix)).symlink_to(victim)
    with pytest.raises((ValueError, OSError)):
        if kind == 'evidence': EvidenceStore(root/name)
        else: DocumentStore(root)
    assert victim.read_bytes() == b'not a sqlite database'
    assert stat.S_IMODE(victim.stat().st_mode) == 0o644


@pytest.mark.parametrize('kind', ['evidence', 'upload'])
def test_reject_symlinked_state_root(tmp_path, kind):
    real = tmp_path/'real'; real.mkdir(mode=0o700)
    link = tmp_path/'link'; link.symlink_to(real, target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        if kind == 'evidence': EvidenceStore(link/'e.db')
        else: DocumentStore(link)
    assert list(real.iterdir()) == []


def test_namespace_symlink_cannot_write_or_recovery_delete_outside(tmp_path):
    root = tmp_path/'owned'; store = DocumentStore(root)
    outside = tmp_path/'outside'; outside.mkdir(mode=0o700)
    orphan = outside/'11111111-1111-1111-1111-111111111111.txt'; orphan.write_bytes(b'keep')
    (root/'local').symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises((ValueError, OSError)):
            store.save('local', 'safe.txt', b'owned')
        store.close()
        with pytest.raises((ValueError, OSError)):
            store.reopen()
        assert orphan.read_bytes() == b'keep'
        assert list(outside.iterdir()) == [orphan]
    finally: store.close()


def test_corrupt_upload_suffix_cannot_resolve_or_delete_outside(tmp_path):
    store = DocumentStore(tmp_path/'owned')
    ref = store.save('local', 'safe.txt', b'owned')
    with store._db:
        store._db.execute('UPDATE uploads SET suffix=?', ('/../../outside.txt',))
    try:
        with pytest.raises((ValueError, sqlite3.DatabaseError)):
            store.resolve('local', ref)
    finally: store.close()


@pytest.mark.parametrize('kind', ['evidence', 'upload'])
def test_health_fails_closed_on_missing_storage_schema(tmp_path, kind):
    store = EvidenceStore(tmp_path/'e.db') if kind == 'evidence' else DocumentStore(tmp_path/'owned')
    table = 'evidence_reviews' if kind == 'evidence' else 'uploads'
    with store._db: store._db.execute('DROP TABLE '+table)
    try:
        with pytest.raises((RuntimeError, ValueError, sqlite3.DatabaseError)):
            store.healthcheck()
    finally: store.close()


def test_reopen_refuses_wrong_primary_key_schema(tmp_path):
    path = tmp_path/'e.db'
    db = sqlite3.connect(path)
    try:
        with db:
            db.execute('CREATE TABLE evidence_graphs (tenant TEXT NOT NULL, doc_id TEXT PRIMARY KEY, payload TEXT NOT NULL, bytes INTEGER NOT NULL, completed REAL NOT NULL)')
    finally:
        db.close()
    with pytest.raises((ValueError, sqlite3.DatabaseError)):
        EvidenceStore(path)


def test_corrupt_graph_fails_before_exposing_payload(tmp_path):
    store = EvidenceStore(tmp_path/'e.db'); doc, _ = publish(store)
    with store._db: store._db.execute("UPDATE evidence_graphs SET payload='{}'")
    try:
        with pytest.raises((ValueError, sqlite3.DatabaseError)):
            store.graph('local', doc.doc_id)
    finally: store.close()


def test_purge_removes_inactive_tenants_and_review_entities(tmp_path):
    store = EvidenceStore(tmp_path/'e.db'); doc, ext = publish(store)
    store.review('local', ext.ext_id, 'author', 'Alice', 'Bob', 'fixture', 0)
    with store._db: store._db.execute('UPDATE evidence_graphs SET completed=0')
    try:
        assert store.purge_expired() == 1
        assert [store._db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in
                ('evidence_graphs', 'evidence_entities', 'evidence_reviews')] == [0, 0, 0]
        assert store.graph('local', doc.doc_id) is None
    finally: store.close()


def test_upload_purge_removes_inactive_tenant_copy(tmp_path):
    store = DocumentStore(tmp_path/'owned'); ref = store.save('a'*64, 'safe.txt', b'owned')
    target = store.resolve('a'*64, ref)
    with store._db: store._db.execute('UPDATE uploads SET created=0')
    try:
        assert store.purge_expired() == 1
        assert not target.exists()
        assert store._db.execute('SELECT COUNT(*) FROM uploads').fetchone()[0] == 0
    finally: store.close()


@pytest.mark.parametrize('kind', ['evidence', 'upload'])
def test_private_database_and_wal_without_process_umask_change(tmp_path, kind):
    before = os.umask(0o022); os.umask(before)
    store = EvidenceStore(tmp_path/'state'/'e.db') if kind == 'evidence' else DocumentStore(tmp_path/'state')
    try:
        if kind == 'evidence': publish(store)
        else: store.save('local', 'safe.txt', b'owned')
        root = tmp_path/'state'
        assert stat.S_IMODE(root.stat().st_mode) == 0o700
        for path in root.glob('*.db*'):
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
        after = os.umask(before); os.umask(after)
        assert after == before
    finally: store.close()


def _cas_worker(path, ext_id, barrier, result):
    store = EvidenceStore(Path(path))
    try:
        barrier.wait(timeout=10)
        try: result.put(store.review('local', ext_id, 'author', 'Alice', 'Bob', 'fixture', 0)['revision'])
        except ReviewConflict: result.put('conflict')
    finally: store.close()


def test_independent_process_review_cas(tmp_path):
    path = tmp_path/'e.db'; store = EvidenceStore(path); _, ext = publish(store); store.close()
    context = multiprocessing.get_context('spawn')
    barrier, result = context.Barrier(2), context.Queue()
    workers = [context.Process(target=_cas_worker, args=(str(path), ext.ext_id, barrier, result)) for _ in range(2)]
    try:
        for worker in workers: worker.start()
        outcomes = [result.get(timeout=20) for _ in workers]
        for worker in workers:
            worker.join(timeout=10); assert worker.exitcode == 0
        assert sorted(map(str, outcomes)) == ['1', 'conflict']
        with_store = EvidenceStore(path)
        try:
            assert with_store.current_review('local', ext.ext_id)['revision'] == 1
            assert with_store.chain('local', ext.ext_id).extraction.value == 'Alice'
        finally: with_store.close()
    finally:
        for worker in workers:
            if worker.is_alive(): worker.terminate(); worker.join()
        result.close(); result.join_thread()


@pytest.mark.parametrize('bad_bytes', [-100, 1, 'wrong'])
def test_corrupt_upload_size_refused_for_read_and_quota(tmp_path, bad_bytes):
    store = DocumentStore(tmp_path/'owned', max_bytes=16)
    ref = store.save('local', 'safe.txt', b'owned')
    with store._db: store._db.execute('UPDATE uploads SET bytes=?', (bad_bytes,))
    try:
        with pytest.raises((ValueError, sqlite3.DatabaseError)):
            store.resolve('local', ref)
        with pytest.raises((ValueError, sqlite3.DatabaseError)):
            store.save('local', 'second.txt', b'next')
    finally: store.close()


@pytest.mark.parametrize('kind', ['evidence', 'upload'])
def test_hardlinked_database_is_not_adopted_or_chmodded(tmp_path, kind):
    root = tmp_path/'state'; root.mkdir(mode=0o700)
    victim = tmp_path/'victim'; victim.write_bytes(b'keep'); victim.chmod(0o644)
    name = 'e.db' if kind == 'evidence' else 'uploads.db'
    os.link(victim, root/name)
    with pytest.raises((ValueError, OSError)):
        if kind == 'evidence': EvidenceStore(root/name)
        else: DocumentStore(root)
    assert victim.read_bytes() == b'keep' and stat.S_IMODE(victim.stat().st_mode) == 0o644


@pytest.mark.parametrize('kind', ['evidence', 'upload'])
def test_other_user_writable_root_is_refused(tmp_path, kind):
    root = tmp_path/'state'; root.mkdir(mode=0o777); root.chmod(0o777)
    with pytest.raises((ValueError, OSError)):
        if kind == 'evidence': EvidenceStore(root/'e.db')
        else: DocumentStore(root)
    assert list(root.iterdir()) == []


def test_reject_same_namespace_symlink_on_resolve(tmp_path):
    store = DocumentStore(tmp_path/'owned')
    ref = store.save('local', 'safe.txt', b'owned'); target = store.resolve('local', ref)
    other = target.parent/'other.txt'; other.write_bytes(b'not source')
    target.unlink(); target.symlink_to(other)
    try:
        with pytest.raises((ValueError, OSError)):
            store.resolve('local', ref)
        assert other.read_bytes() == b'not source'
    finally: store.close()


def _cold_worker(path, barrier, result):
    barrier.wait(timeout=10)
    evidence = EvidenceStore(Path(path)/'e.db')
    upload = None
    try:
        upload = DocumentStore(Path(path)/'owned')
        evidence.healthcheck(); upload.healthcheck()
        result.put('ok')
    finally:
        evidence.close()
        if upload is not None: upload.close()


def test_independent_process_cold_initialization(tmp_path):
    context = multiprocessing.get_context('spawn')
    barrier, result = context.Barrier(4), context.Queue()
    workers = [context.Process(target=_cold_worker, args=(str(tmp_path/'state'), barrier, result)) for _ in range(4)]
    try:
        for worker in workers: worker.start()
        assert [result.get(timeout=20) for _ in workers] == ['ok']*4
        for worker in workers:
            worker.join(timeout=10); assert worker.exitcode == 0
    finally:
        for worker in workers:
            if worker.is_alive(): worker.terminate(); worker.join()
        result.close(); result.join_thread()


def test_reopen_and_health_purge_all_tenants(tmp_path):
    evidence = EvidenceStore(tmp_path/'state'/'e.db')
    upload = DocumentStore(tmp_path/'state'/'owned')
    _, ext = publish(evidence)
    evidence.review('local', ext.ext_id, 'author', 'Alice', 'Bob', 'fixture', 0)
    ref = upload.save('a'*64, 'safe.txt', b'owned'); target = upload.resolve('a'*64, ref)
    with evidence._db: evidence._db.execute('UPDATE evidence_graphs SET completed=0')
    with upload._db: upload._db.execute('UPDATE uploads SET created=0')
    evidence.close(); upload.close()
    try:
        evidence.reopen(); upload.reopen()
        assert evidence._db.execute('SELECT COUNT(*) FROM evidence_reviews').fetchone()[0] == 0
        assert upload._db.execute('SELECT COUNT(*) FROM uploads').fetchone()[0] == 0
        assert not target.exists()
        publish(evidence)
        ref = upload.save('b'*64, 'safe.txt', b'owned'); target = upload.resolve('b'*64, ref)
        with evidence._db: evidence._db.execute('UPDATE evidence_graphs SET completed=0')
        with upload._db: upload._db.execute('UPDATE uploads SET created=0')
        evidence.healthcheck(); upload.healthcheck()
        assert evidence._db.execute('SELECT COUNT(*) FROM evidence_graphs').fetchone()[0] == 0
        assert not target.exists()
    finally: evidence.close(); upload.close()
