"""Bounded app-managed upload copies; no arbitrary authenticated filesystem reads.

Credential namespaces, not identity/account management. One protected local volume.
No at-rest encryption or forensic erasure. TTL denies reads immediately; physical
unlink requires purge activity (operator scheduling is mandatory on idle hosts).
"""
import math
import os
import re
import threading
import time
import uuid
from pathlib import Path

from kernel.sidecar.storage_security import (
    check_open_database_files,
    open_database,
    private_directory,
    private_file,
    validate_schema,
)


class UploadConflict(ValueError):
    pass


class UploadBudgetExceeded(ValueError):
    pass


_UPLOAD_SCHEMA = {"uploads": {"tenant": ("TEXT", 1, 1), "id": ("TEXT", 1, 2),
                             "suffix": ("TEXT", 1, 0), "bytes": ("INTEGER", 1, 0), "created": ("REAL", 1, 0)}}
_SUFFIXES = {'.txt', '.md', '.pdf', '.docx', '.pptx'}


def _identity(value):
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value
    except ValueError:
        return False


class DocumentStore:
    def __init__(self, root, *, max_files=128, max_bytes=64*1024*1024, ttl=3600):
        if max_files < 1 or max_bytes < 1 or ttl <= 0:
            raise ValueError('Invalid upload budget')
        self.root = private_directory(root)
        self.max_files, self.max_bytes, self.ttl = max_files, max_bytes, ttl
        self._lock = threading.RLock()
        self._db = None
        self.reopen()

    def reopen(self):
        with self._lock:
            if self._db is not None:
                return
            with open_database(self.root/'uploads.db') as db:
                db.execute('BEGIN IMMEDIATE')
                validate_schema(db, _UPLOAD_SCHEMA, initializing=True)
                db.execute('''CREATE TABLE IF NOT EXISTS uploads (
                    tenant TEXT NOT NULL, id TEXT NOT NULL, suffix TEXT NOT NULL,
                    bytes INTEGER NOT NULL, created REAL NOT NULL,
                    PRIMARY KEY(tenant,id))''')
                validate_schema(db, _UPLOAD_SCHEMA)
                db.commit()
                check_open_database_files(self.root/'uploads.db')
                # Recovery shares the publisher's cross-process SQLite lock.
                with db:
                    db.execute('BEGIN IMMEDIATE')
                    for row in db.execute('SELECT tenant,id,suffix,bytes,created FROM uploads'):
                        self._target(*row)
                    for namespace in self.root.iterdir():
                        if namespace.name != 'local' and not re.fullmatch('[0-9a-f]{64}', namespace.name):
                            continue
                        namespace = self._namespace(namespace.name)
                        known = {ident+suffix for ident, suffix in db.execute(
                            'SELECT id,suffix FROM uploads WHERE tenant=?', (namespace.name,))}
                        for candidate in namespace.iterdir():
                            if candidate.suffix in _SUFFIXES and _identity(candidate.stem):
                                private_file(candidate)
                                if candidate.name not in known:
                                    candidate.unlink(missing_ok=True)
                    self._purge(db)
            self._db = db

    def healthcheck(self):
        with self._lock:
            if self._db is None:
                raise RuntimeError('Durable state unavailable')
            check_open_database_files(self.root/'uploads.db')
            validate_schema(self._db, _UPLOAD_SCHEMA)
            for row in self._db.execute('SELECT tenant,id,suffix,bytes,created FROM uploads'):
                self._target(*row)
            self.purge_expired()

    def close(self):
        with self._lock:
            if self._db is not None:
                self._db.close()
                self._db = None

    def _namespace(self, tenant):
        # Only internally-derived full SHA256 digests or trusted local mode.
        if tenant != 'local' and not re.fullmatch('[0-9a-f]{64}', tenant):
            raise ValueError('Invalid credential namespace')
        private_directory(self.root)
        path = self.root/tenant
        if path.exists() or path.is_symlink():
            private_directory(path)
        return path

    def _target(self, tenant, ident, suffix, size=None, created=None):
        if (not _identity(ident) or suffix not in _SUFFIXES
                or size is not None and (type(size) is not int or not 0 < size <= self.max_bytes)
                or created is not None and (not isinstance(created, (int, float)) or not math.isfinite(created))):
            raise ValueError('Corrupt upload metadata')
        target = self._namespace(tenant)/(ident+suffix)
        present = private_file(target)
        if size is not None and present and target.stat().st_size != size:
            raise ValueError('Upload copy size does not match metadata')
        if created is not None and created >= time.time()-self.ttl and not present:
            raise ValueError('Retained upload copy missing')
        return target

    def _purge(self, db):
        expired = db.execute('SELECT tenant,id,suffix,bytes,created FROM uploads WHERE created<?', (time.time()-self.ttl,)).fetchall()
        # Validate all deletion targets before unlinking any. Unlinks are not a
        # SQLite transaction; crash can leave stale metadata, recovered next time.
        targets = [self._target(*row) for row in expired]
        for target in targets:
            target.unlink(missing_ok=True)
        for tenant, ident, *_ in expired:
            db.execute('DELETE FROM uploads WHERE tenant=? AND id=?', (tenant, ident))
        return len(expired)

    def purge_expired(self):
        """All-tenant logical deletion/unlink; no WAL/backup erasure guarantee."""
        with self._lock, self._db as db:
            db.execute('BEGIN IMMEDIATE')
            return self._purge(db)

    def save(self, tenant, filename, content):
        suffix = Path(filename).suffix.lower()
        if suffix not in _SUFFIXES:
            raise ValueError('Unsupported document extension')
        if not content or len(content) > self.max_bytes:
            raise UploadBudgetExceeded('Upload byte budget exceeded')
        namespace = self._namespace(tenant)
        namespace = private_directory(namespace)
        identity = str(uuid.uuid4())
        target = namespace/(identity+suffix)
        with self._lock, self._db as db:
            db.execute('BEGIN IMMEDIATE')
            self._purge(db)
            retained = db.execute('SELECT tenant,id,suffix,bytes,created FROM uploads WHERE tenant=?', (tenant,)).fetchall()
            for row in retained:
                self._target(*row)
            total, size = len(retained), sum(row[3] for row in retained)
            if total >= self.max_files or size+len(content) > self.max_bytes:
                raise UploadBudgetExceeded('Credential upload quota exceeded')
            created = False
            try:
                # Mode is private at creation, not chmod after a disclosure window.
                fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                created = True
                with os.fdopen(fd, 'wb') as file:
                    file.write(content)
                db.execute('INSERT INTO uploads VALUES(?,?,?,?,?)', (tenant, identity, suffix, len(content), time.time()))
            except FileExistsError as exc:
                raise UploadConflict('Generated upload reference conflict; retry') from exc
            except BaseException:
                if created:
                    target.unlink(missing_ok=True)
                raise
        return 'uploaded:'+identity

    def resolve(self, tenant, reference):
        identity = reference.removeprefix('uploaded:')
        if not reference.startswith('uploaded:') or not _identity(identity):
            return None
        self._namespace(tenant)
        with self._lock:
            row = self._db.execute('SELECT suffix,bytes,created FROM uploads WHERE tenant=? AND id=? AND created>=?',
                                   (tenant, identity, time.time()-self.ttl)).fetchone()
            if not row:
                return None
            target = self._target(tenant, identity, *row)
            return target if target.is_file() else None
