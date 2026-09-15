"""Real SQLite handles must close even when setup or recall SQL fails."""
import gc
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sidecar.mem_machine import MemMachineClient


def test_connect_closes_on_pragma_failure(tmp_path, monkeypatch):
    client = MemMachineClient(str(tmp_path / "memory.db"))
    opened = []
    original = sqlite3.connect

    class FailingConnection(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql == "PRAGMA journal_mode=WAL":
                raise sqlite3.OperationalError("injected setup failure")
            return super().execute(sql, *args, **kwargs)

    def connect(*args, **kwargs):
        conn = original(*args, factory=FailingConnection, **kwargs)
        opened.append(conn)
        return conn

    monkeypatch.setattr(sqlite3, "connect", connect)
    try:
        with pytest.raises(sqlite3.OperationalError, match="setup failure"):
            client._connect()
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            opened[0].execute("SELECT 1")
    finally:
        for conn in opened:
            conn.close()


def test_recall_closes_on_sql_failure(tmp_path, monkeypatch):
    import sidecar.embeddings as embeddings
    client = MemMachineClient(str(tmp_path / "memory.db"))
    conn = client._connect()
    conn.execute("DROP TABLE interactions")
    conn.commit()
    # Embedding is irrelevant to the SQL lifecycle fault under test.
    monkeypatch.setattr(embeddings, "embed_text", lambda text: [1.0, 0.0])
    monkeypatch.setattr(client, "_connect", lambda: conn)
    try:
        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            client.recall_contextualized("hello")
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            conn.execute("SELECT 1")
    finally:
        conn.close()
    gc.collect()


def test_pdf_ingest_closes_on_schema_error(tmp_path, monkeypatch):
    from sidecar.masters.other_masters import WeKnoraPipeline
    pipeline = WeKnoraPipeline.__new__(WeKnoraPipeline)
    pipeline.db_path = str(tmp_path / "broken.db")
    pdf = tmp_path / "present.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    opened = []
    original = sqlite3.connect
    def connect(*args, **kwargs):
        conn = original(*args, **kwargs)
        opened.append(conn)
        return conn
    monkeypatch.setattr(sqlite3, "connect", connect)
    try:
        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            pipeline.ingest(str(pdf))
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            opened[0].execute("SELECT 1")
    finally:
        for conn in opened:
            conn.close()
