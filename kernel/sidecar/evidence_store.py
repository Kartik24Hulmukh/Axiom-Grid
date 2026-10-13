"""Bounded, credential-scoped complete evidence snapshots and review CAS.

SQLite WAL shares state across processes on one local filesystem. It is NOT
a distributed database, execution witness, encrypted vault or audit journal.
Legacy unscoped state is never assigned to authenticated credentials.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from pathlib import Path

from kernel.core.data_model import (
    Action,
    ActionKind,
    ActionStatus,
    Anchor,
    BBox,
    Chain,
    Chunk,
    Correction,
    Document,
    Extraction,
    ExtractionStatus,
    GroundingMethod,
)
from kernel.sidecar.storage_security import (
    check_open_database_files,
    open_database,
    private_directory,
    validate_schema,
)

_EVIDENCE_SCHEMA = {
    "evidence_graphs": {"tenant": ("TEXT", 1, 1), "doc_id": ("TEXT", 1, 2),
                        "payload": ("TEXT", 1, 0), "bytes": ("INTEGER", 1, 0), "completed": ("REAL", 1, 0)},
    "evidence_entities": {"tenant": ("TEXT", 1, 1), "entity_id": ("TEXT", 1, 2), "doc_id": ("TEXT", 1, 0)},
    "evidence_reviews": {"tenant": ("TEXT", 1, 1), "ext_id": ("TEXT", 1, 2), "doc_id": ("TEXT", 1, 0),
                         "revision": ("INTEGER", 1, 0), "corrected": ("TEXT", 1, 0), "reason": ("TEXT", 1, 0),
                         "updated": ("REAL", 1, 0), "field_name": ("TEXT", 0, 0), "source_value": ("TEXT", 0, 0)},
}
_EVIDENCE_FKS = {table: {("evidence_graphs", "tenant", "tenant", "CASCADE"),
                          ("evidence_graphs", "doc_id", "doc_id", "CASCADE")}
                 for table in ("evidence_entities", "evidence_reviews")}


def _schema(db, initializing=False):
    validate_schema(db, _EVIDENCE_SCHEMA, initializing=initializing,
                    optional=(("evidence_reviews", "field_name"), ("evidence_reviews", "source_value")),
                    foreign_keys=_EVIDENCE_FKS)


class EvidenceBudgetExceeded(ValueError):
    pass


class ReviewConflict(ValueError):
    pass


def _json(value):
    def scalar(item):
        if isinstance(item, Enum):
            return item.value
        if isinstance(item, datetime):
            return item.isoformat()
        raise TypeError("Unsupported evidence scalar")
    return json.dumps(value, default=scalar, ensure_ascii=True, allow_nan=False,
                      separators=(",", ":"))


def _document(value):
    return Document(**{**value, "ingested_at": datetime.fromisoformat(value["ingested_at"])})


def _chunk(value):
    return Chunk(**{**value, "bbox": BBox(**value["bbox"]) if value["bbox"] else None})


def _extraction(value):
    anchors = tuple(Anchor(**{**a, "char_span": tuple(a["char_span"]),
                              "bbox": BBox(**a["bbox"]) if a["bbox"] else None})
                    for a in value["anchors"])
    return Extraction(**{**value, "status": ExtractionStatus(value["status"]),
                         "method": GroundingMethod(value["method"]), "anchors": anchors})


def _action(value):
    return Action(**{**value, "kind": ActionKind(value["kind"]),
                     "status": ActionStatus(value["status"])})


class EvidenceStore:
    def __init__(self, path, *, retain=128, ttl=3600, max_graph_bytes=16*1024*1024,
                 max_tenant_bytes=64*1024*1024, max_review_bytes=8*1024*1024):
        if retain < 1 or ttl <= 0 or max_graph_bytes < 1 or max_tenant_bytes < max_graph_bytes:
            raise ValueError("Invalid evidence budget")
        self.path = private_directory(Path(path).absolute().parent) / Path(path).name
        self.retain, self.ttl = retain, ttl
        if max_review_bytes < 1:
            raise ValueError("Invalid review budget")
        self.max_review_bytes = max_review_bytes
        self.max_graph_bytes, self.max_tenant_bytes = max_graph_bytes, max_tenant_bytes
        self._lock = threading.RLock()
        self._db = None
        self.reopen()

    def reopen(self):
        with self._lock:
            if self._db is not None:
                return
            with open_database(self.path) as db:
                db.execute("PRAGMA synchronous=NORMAL")
                db.execute("PRAGMA foreign_keys=ON")
                # Schema inspection, creation and migration share ONE writer
                # transaction; executescript would implicitly commit it.
                db.execute("BEGIN IMMEDIATE")
                _schema(db, initializing=True)
                statements = """
                CREATE TABLE IF NOT EXISTS evidence_graphs (
                  tenant TEXT NOT NULL, doc_id TEXT NOT NULL, payload TEXT NOT NULL,
                  bytes INTEGER NOT NULL, completed REAL NOT NULL,
                  PRIMARY KEY(tenant, doc_id));
                CREATE INDEX IF NOT EXISTS evidence_time ON evidence_graphs(tenant, completed);
                CREATE TABLE IF NOT EXISTS evidence_entities (
                  tenant TEXT NOT NULL, entity_id TEXT NOT NULL, doc_id TEXT NOT NULL,
                  PRIMARY KEY(tenant, entity_id),
                  FOREIGN KEY(tenant, doc_id) REFERENCES evidence_graphs(tenant, doc_id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS evidence_reviews (
                  tenant TEXT NOT NULL, ext_id TEXT NOT NULL, doc_id TEXT NOT NULL,
                  revision INTEGER NOT NULL, corrected TEXT NOT NULL, reason TEXT NOT NULL,
                  updated REAL NOT NULL, PRIMARY KEY(tenant, ext_id),
                  FOREIGN KEY(tenant, doc_id) REFERENCES evidence_graphs(tenant, doc_id) ON DELETE CASCADE);
                """
                for statement in statements.split(";"):
                    if statement.strip():
                        db.execute(statement)
                columns = {row[1] for row in db.execute("PRAGMA table_info(evidence_reviews)")}
                # Additive migration; legacy unscoped memory is NEVER imported.
                for column in ("field_name", "source_value"):
                    if column not in columns:
                        db.execute(f"ALTER TABLE evidence_reviews ADD COLUMN {column} TEXT")
                _schema(db)
                db.commit()
                check_open_database_files(self.path)
            self._db = db
            self.purge_expired()

    def healthcheck(self):
        with self._lock:
            if self._db is None or self._db.execute("SELECT 1").fetchone() != (1,):
                raise RuntimeError("Durable state unavailable")
            check_open_database_files(self.path)
            _schema(self._db)
            self.purge_expired()

    def purge_expired(self):
        """Logical all-tenant expiry; operator must schedule for idle deployments.

        Not forensic erasure: WAL, backups and filesystem copies remain separate.
        """
        with self._lock, self._db as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute("DELETE FROM evidence_graphs WHERE completed<?", (time.time()-self.ttl,))
            return cursor.rowcount

    def close(self):
        with self._lock:
            if self._db is not None:
                self._db.close()
                self._db = None

    def _prune(self, db, tenant):
        db.execute("DELETE FROM evidence_graphs WHERE completed<?", (time.time()-self.ttl,))
        # Evict completed snapshots only; publication happens after execution.
        rows = db.execute("SELECT doc_id, bytes FROM evidence_graphs WHERE tenant=? ORDER BY completed DESC, doc_id",
                          (tenant,)).fetchall()
        total = 0
        for kept, (doc_id, size) in enumerate(rows, 1):
            total += size
            if kept > self.retain or total > self.max_tenant_bytes:
                db.execute("DELETE FROM evidence_graphs WHERE tenant=? AND doc_id=?", (tenant, doc_id))

    def publish(self, tenant, document, chunks, extractions, actions=(), trace=None):
        """One transaction publishes a complete immutable observation graph."""
        chunks, extractions, actions = list(chunks), list(extractions), list(actions)
        chunk_ids = {c.chunk_id for c in chunks}
        ext_ids = {e.ext_id for e in extractions}
        if len(chunk_ids) != len(chunks) or len(ext_ids) != len(extractions):
            raise ValueError("Duplicate evidence identifier")
        if any(a.ext_id not in ext_ids for a in actions):
            raise ValueError("Invalid action evidence edge")
        if any(c.doc_id != document.doc_id or c.bbox is None for c in chunks):
            raise ValueError("Invalid document evidence edge")
        if any(e.chunk_id not in chunk_ids and e.status != ExtractionStatus.BLOCKED
               and e.method != GroundingMethod.BLOCK for e in extractions):
            raise ValueError("Invalid extraction evidence edge")
        payload = _json({"document": asdict(document), "chunks": [asdict(c) for c in chunks],
                         "extractions": [asdict(e) for e in extractions],
                         "actions": [asdict(a) for a in actions], "trace": trace})
        size = len(payload.encode())
        if size > self.max_graph_bytes:
            raise EvidenceBudgetExceeded("Evidence exceeds snapshot byte budget")
        with self._lock, self._db as db:
            db.execute("BEGIN IMMEDIATE")
            # UUID collision/republication is a defect, not an overwrite.
            db.execute("INSERT INTO evidence_graphs VALUES(?,?,?,?,?)",
                       (tenant, document.doc_id, payload, size, time.time()))
            for entity in [*extractions, *actions]:
                entity_id = entity.ext_id if isinstance(entity, Extraction) else entity.action_id
                db.execute("INSERT INTO evidence_entities VALUES(?,?,?)",
                           (tenant, entity_id, document.doc_id))
            self._prune(db, tenant)

    def graph(self, tenant, doc_id):
        with self._lock:
            row = self._db.execute(
                "SELECT payload,bytes FROM evidence_graphs WHERE tenant=? AND doc_id=? AND completed>=?",
                (tenant, doc_id, time.time()-self.ttl)).fetchone()
        return self._decode_graph(row[0], row[1], doc_id) if row else None

    def _decode_graph(self, payload, size, doc_id):
        """Refuse malformed rows rather than return partial source observations."""
        try:
            if len(payload.encode("utf-8")) != size or size > self.max_graph_bytes:
                raise ValueError("Invalid evidence payload size")
            graph = json.loads(payload, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite evidence")))
            if set(graph) != {"document", "chunks", "extractions", "actions", "trace"}:
                raise ValueError("Invalid evidence payload shape")
            doc = _document(graph["document"])
            chunks = [_chunk(c) for c in graph["chunks"]]
            exts = [_extraction(e) for e in graph["extractions"]]
            actions = [_action(a) for a in graph["actions"]]
            chunk_ids = {c.chunk_id for c in chunks}
            ext_ids = {e.ext_id for e in exts}
            entity_ids = [e.ext_id for e in exts]+[a.action_id for a in actions]
            if (doc.doc_id != doc_id or len(chunk_ids) != len(chunks)
                    or len(set(entity_ids)) != len(entity_ids)
                    or any(c.doc_id != doc_id or c.bbox is None for c in chunks)
                    or any(e.chunk_id not in chunk_ids and e.status != ExtractionStatus.BLOCKED
                           and e.method != GroundingMethod.BLOCK for e in exts)
                    or any(a.ext_id not in ext_ids for a in actions)):
                raise ValueError("Invalid persisted evidence edges")
            return graph
        except (KeyError, TypeError, AttributeError, OverflowError) as exc:
            raise ValueError("Corrupt evidence payload") from exc

    def chunks_for_doc(self, tenant, doc_id):
        graph = self.graph(tenant, doc_id)
        return [_chunk(c) for c in graph["chunks"]] if graph else []

    def chain(self, tenant, entity_id):
        with self._lock:
            row = self._db.execute("SELECT doc_id FROM evidence_entities WHERE tenant=? AND entity_id=?",
                                   (tenant, entity_id)).fetchone()
        graph = self.graph(tenant, row[0]) if row else None
        if not graph:
            return Chain()
        action_data = next((a for a in graph["actions"] if a["action_id"] == entity_id), None)
        ext_id = action_data["ext_id"] if action_data else entity_id
        ext_data = next((e for e in graph["extractions"] if e["ext_id"] == ext_id), None)
        chunk_data = next((c for c in graph["chunks"] if ext_data and c["chunk_id"] == ext_data["chunk_id"]), None)
        return Chain(action=_action(action_data) if action_data else None,
                     extraction=_extraction(ext_data) if ext_data else None,
                     chunk=_chunk(chunk_data) if chunk_data else None,
                     document=_document(graph["document"]))

    def action_for_extraction(self, tenant, ext_id):
        chain = self.chain(tenant, ext_id)
        graph = self.graph(tenant, chain.document.doc_id) if chain.is_complete else None
        value = next((a for a in graph["actions"] if a["ext_id"] == ext_id), None) if graph else None
        return _action(value) if value else None

    def review(self, tenant, ext_id, field_name, original, corrected, reason, expected_revision=None):
        """CAS review state; immutable extraction/source observations never change."""
        with self._lock, self._db as db:
            db.execute("BEGIN IMMEDIATE")
            chain = self.chain(tenant, ext_id)
            if not chain.is_complete:
                raise KeyError("Extraction unavailable")
            ext = chain.extraction
            if ext.status == ExtractionStatus.BLOCKED or ext.method == GroundingMethod.BLOCK:
                raise ReviewConflict("Blocked observation cannot be reviewed as grounded")
            if ext.field_name != field_name:
                raise ReviewConflict("Field does not match extraction")
            row = db.execute("SELECT revision, corrected FROM evidence_reviews WHERE tenant=? AND ext_id=?",
                             (tenant, ext_id)).fetchone()
            revision, current = row if row else (0, ext.value)
            if original != current or (expected_revision is not None and expected_revision != revision):
                raise ReviewConflict("Stale correction; reload current review")
            used = db.execute("""SELECT COALESCE(SUM(
                length(CAST(corrected AS BLOB))+length(CAST(reason AS BLOB))+
                COALESCE(length(CAST(source_value AS BLOB)),0)),0)
                FROM evidence_reviews WHERE tenant=? AND ext_id<>?""", (tenant,ext_id)).fetchone()[0]
            size = sum(len(v.encode("utf-8")) for v in (corrected,reason,ext.value))
            if used+size > self.max_review_bytes:
                raise EvidenceBudgetExceeded("Credential review byte quota exceeded")
            revision += 1
            db.execute("""INSERT INTO evidence_reviews(tenant,ext_id,doc_id,revision,corrected,reason,updated,field_name,source_value) VALUES(?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(tenant, ext_id) DO UPDATE SET
                        revision=excluded.revision, corrected=excluded.corrected,
                        reason=excluded.reason, updated=excluded.updated,
                        field_name=excluded.field_name, source_value=excluded.source_value""",
                       (tenant, ext_id, chain.document.doc_id, revision, corrected, reason, time.time(), ext.field_name, ext.value))
            return {"success": True, "revision": revision,
                    "review_scope": "human correction; not automatically re-grounded"}

    def similar_reviews(self, tenant, field_name, value, k=5):
        """Bounded exact-original-value lookup; human review only calibrates confidence."""
        with self._lock:
            rows = self._db.execute("""SELECT r.ext_id,r.corrected,r.reason
                FROM evidence_reviews r JOIN evidence_graphs g
                ON r.tenant=g.tenant AND r.doc_id=g.doc_id
                WHERE r.tenant=? AND r.field_name=? AND r.source_value=? AND g.completed>=?
                ORDER BY r.updated DESC LIMIT ?""",
                (tenant, field_name, value, time.time()-self.ttl, max(1,min(5,k)))).fetchall()
        return [Correction(ext_id=ext_id, original=value, corrected=corrected, reason=reason,
                           by="credential-scoped-review") for ext_id,corrected,reason in rows]

    def current_review(self, tenant, ext_id):
        with self._lock:
            chain = self.chain(tenant, ext_id)
            if not chain.is_complete:
                raise KeyError("Extraction unavailable")
            row = self._db.execute("SELECT revision,corrected,reason FROM evidence_reviews WHERE tenant=? AND ext_id=?",
                                   (tenant, ext_id)).fetchone()
        return {"ext_id": ext_id, "field_name": chain.extraction.field_name,
                "revision": row[0] if row else 0,
                "value": row[1] if row else chain.extraction.value,
                "reason": row[2] if row else "",
                "source_value": chain.extraction.value,
                "review_scope": "human correction; not automatically re-grounded" if row else "original observation"}

    def traces(self, tenant, limit=50):
        limit = max(1, min(128, limit))
        with self._lock:
            rows = self._db.execute(
                "SELECT payload,bytes,doc_id FROM evidence_graphs WHERE tenant=? AND completed>=? ORDER BY completed DESC LIMIT ?",
                (tenant, time.time()-self.ttl, limit)).fetchall()
        return [{"doc_id": g["document"]["doc_id"], "trace": g["trace"]}
                for g in (self._decode_graph(r[0], r[1], r[2]) for r in rows)]

class ScopedReviewLookup:
    """QualityGate protocol without leaking one credential's corrections to another."""
    def __init__(self, store, tenant):
        self.store, self.tenant = store, tenant

    def search_similar_corrections(self, field_name, value, k=5):
        return self.store.similar_reviews(self.tenant, field_name, value, k)
