import pytest
from overlay.document_store import DocumentStore, UploadBudgetExceeded


def test_opaque_owned_copy_cross_worker_expiry_and_permissions(tmp_path):
    a=DocumentStore(tmp_path);b=DocumentStore(tmp_path);tenant='a'*64
    ref=a.save(tenant,'../../outside.txt',b'owned fixture')
    target=a.resolve(tenant,ref)
    assert target.read_bytes()==b'owned fixture' and target.stat().st_mode & 0o777==0o600
    assert b.resolve(tenant,ref)==target
    assert a.resolve('b'*64,ref) is None
    assert a.resolve(tenant,'uploaded:../../outside') is None
    assert not (tmp_path.parent/'outside.txt').exists()
    with a._db:a._db.execute('UPDATE uploads SET created=0')
    assert b.resolve(tenant,ref) is None
    a.save(tenant,'valid.txt',b'next');assert not target.exists()
    a.close();b.close()


def test_quotas_do_not_destroy_valid_copies(tmp_path):
    s=DocumentStore(tmp_path,max_files=1,max_bytes=8)
    ref=s.save('local','fixture.txt',b'1234')
    with pytest.raises(UploadBudgetExceeded):s.save('local','fixture.txt',b'1234')
    with pytest.raises(ValueError):s.save('local','fixture.exe',b'12')
    assert s.resolve('local',ref).read_bytes()==b'1234';s.close()


def test_reopen_recovers_orphan_copy_without_deleting_committed_upload(tmp_path):
    store=DocumentStore(tmp_path);ref=store.save('local','file.txt',b'committed')
    committed=store.resolve('local',ref);namespace=committed.parent
    orphan=namespace/'11111111-1111-1111-1111-111111111111.txt';orphan.write_bytes(b'orphan')
    store.close();store.reopen()
    assert not orphan.exists() and committed.read_bytes()==b'committed';store.close()


def test_generated_uuid_collision_never_deletes_existing_owned_copy(tmp_path,monkeypatch):
    import uuid
    from overlay import document_store
    from overlay.document_store import UploadConflict
    monkeypatch.setattr(document_store.uuid,'uuid4',lambda:uuid.UUID('11111111-1111-1111-1111-111111111111'))
    store=DocumentStore(tmp_path);ref=store.save('local','file.txt',b'immutable owned copy')
    with pytest.raises(UploadConflict):store.save('local','file.txt',b'not a replacement')
    assert store.resolve('local',ref).read_bytes()==b'immutable owned copy';store.close()
