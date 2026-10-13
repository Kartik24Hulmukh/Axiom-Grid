"""POSIX local-store custody checks, not encryption or hostile-host isolation.

SQLite opens paths internally: all containing directories must be protected from
other users. A same-UID process, privileged host or malicious filesystem remains
outside this boundary. Never alter the process-wide umask in a threaded server.
"""
import fcntl
import os
import sqlite3
import stat
from contextlib import contextmanager
from pathlib import Path


def private_directory(path):
    path = Path(os.path.abspath(path))  # Do not resolve away evidence of symlinks.
    for component in reversed((path, *path.parents)):
        try:
            info = component.lstat()
        except FileNotFoundError:
            try: component.mkdir(mode=0o700)
            except FileExistsError: pass  # Concurrent cold worker; inspect below.
            info = component.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid not in (0, os.getuid()):
            raise ValueError('Untrusted storage directory')
        if info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX:
            raise ValueError('Storage ancestor is writable by other users')
        if component == path:
            if info.st_uid != os.getuid() or info.st_mode & 0o022:
                raise ValueError('Storage directory is not privately owned')
            component.chmod(0o700)
    return path


def private_file(path, *, create=False):
    path = Path(path)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    if create: flags |= os.O_CREAT
    try:
        fd = os.open(path, flags, 0o600)
    except FileNotFoundError:
        if create: raise
        return False
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or info.st_mode & 0o022:
            raise ValueError('Untrusted storage file')
        os.fchmod(fd, 0o600)
    finally: os.close(fd)
    return True


def check_database_files(path):
    private_directory(Path(path).parent)
    for suffix in ('', '-wal', '-shm', '-journal'):
        private_file(str(path)+suffix)


def check_open_database_files(path):
    """Validate live SQLite files without closing duplicate descriptors."""
    private_directory(Path(path).parent)
    for suffix in ('', '-wal', '-shm', '-journal', '.init.lock'):
        try:
            info = Path(str(path)+suffix).lstat()
        except FileNotFoundError:
            continue
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_nlink != 1 or info.st_mode & 0o022):
            raise ValueError('Untrusted storage file')


@contextmanager
def open_database(path):
    path = Path(path)
    private_directory(path.parent)
    lock_path = str(path) + ".init.lock"
    private_file(lock_path, create=True)
    lock = os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    db = None
    try:
        # Cold journal-mode transition and schema setup must be one
        # cross-process critical section.
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not path.exists():
            # No SQLite connection exists yet, so creating and closing this
            # custody descriptor cannot release SQLite's process-wide locks.
            private_file(path, create=True)
        # Once any connection may be live, inspect with lstat only. Opening and
        # closing duplicate descriptors can release POSIX locks for the whole
        # process and invalidate another connection's mapped WAL/SHM state.
        check_open_database_files(path)
        db = sqlite3.connect(Path(path).as_uri()+'?mode=rw', uri=True,
                             check_same_thread=False, timeout=5)
        mode = db.execute("PRAGMA journal_mode").fetchone()
        if mode != ("wal",):
            mode = db.execute("PRAGMA journal_mode=WAL").fetchone()
        if mode != ("wal",):
            raise sqlite3.DatabaseError("Could not enable WAL journal mode")
        yield db
    except BaseException:
        if db is not None:
            db.close()
        raise
    finally:
        os.close(lock)


def validate_schema(db, schema, *, initializing=False, optional=(), foreign_keys=None):
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    if initializing and not tables:
        return
    if not set(schema).issubset(tables):
        raise ValueError('Storage schema missing required tables')
    for table, expected in schema.items():
        rows = {r[1]: (r[2].upper(), r[3], r[5]) for r in db.execute(f'PRAGMA table_info({table})')}
        for name, shape in expected.items():
            if initializing and (table, name) in optional and name not in rows:
                continue
            if rows.get(name) != shape:
                raise ValueError('Incompatible storage schema')
        if set(rows)-set(expected):
            raise ValueError('Unexpected storage schema columns')
        actual = {(r[2], r[3], r[4], r[6]) for r in db.execute(f'PRAGMA foreign_key_list({table})')}
        if actual != (foreign_keys or {}).get(table, set()):
            raise ValueError('Storage foreign-key schema mismatch')
    if db.execute('PRAGMA quick_check').fetchall() != [('ok',)] or db.execute('PRAGMA foreign_key_check').fetchone():
        raise sqlite3.DatabaseError('Storage integrity check failed')
