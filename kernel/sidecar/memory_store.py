"""
Kairo Phantom — MemoryStore (SPEC §S2, §S4, §S6)

SQLite-backed persistent store for documents, extractions, corrections.
Supports the local flywheel: corrections surface via search_similar_corrections.

Local-first: zero external calls. Fully offline.

The kernel imports NOTHING from /domains or /legacy.
"""

from __future__ import annotations

import json
import logging
import pathlib
import sqlite3
import threading
import weakref
from datetime import datetime
from typing import Self

from kernel.core.data_model import (
    Action,
    ActionKind,
    ActionStatus,
    BBox,
    Chunk,
    Correction,
    Document,
    Entity,
    Extraction,
    ExtractionStatus,
    ModelVersion,
    Page,
    User,
)

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pages (
    doc_id TEXT NOT NULL,
    index_val INTEGER NOT NULL,
    width_px INTEGER NOT NULL,
    height_px INTEGER NOT NULL,
    image_sha256 TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (doc_id, index_val),
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    page INTEGER NOT NULL,
    bbox_x0 REAL NOT NULL,
    bbox_y0 REAL NOT NULL,
    bbox_x1 REAL NOT NULL,
    bbox_y1 REAL NOT NULL,
    text TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT '',
    embedding TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);

CREATE TABLE IF NOT EXISTS extractions (
    ext_id TEXT PRIMARY KEY,
    pack_id TEXT NOT NULL DEFAULT '',
    field_name TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.0,
    model_version TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'suggested',
    chunk_id TEXT NOT NULL,
    FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id)
);

CREATE TABLE IF NOT EXISTS corrections (
    corr_id TEXT PRIMARY KEY,
    ext_id TEXT NOT NULL,
    original TEXT NOT NULL,
    corrected TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    by_user TEXT NOT NULL DEFAULT '',
    at_time TEXT NOT NULL,
    FOREIGN KEY (ext_id) REFERENCES extractions(ext_id)
);

CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL DEFAULT '',
    value TEXT NOT NULL DEFAULT '',
    normalized TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS model_versions (
    model_id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    weights_hash TEXT NOT NULL DEFAULT '',
    tier INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS actions (
    action_id TEXT PRIMARY KEY,
    ext_id TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'suggest',
    target_app TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL DEFAULT '{}',
    confidence REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'pending',
    FOREIGN KEY (ext_id) REFERENCES extractions(ext_id)
);

CREATE INDEX IF NOT EXISTS idx_corrections_field ON corrections(ext_id);
CREATE INDEX IF NOT EXISTS idx_extractions_field ON extractions(field_name);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_actions_ext ON actions(ext_id);
"""


def _close_connection(conn: sqlite3.Connection) -> None:
    """Module-level closer so weakref.finalize never captures the store."""
    try:
        conn.close()
    except sqlite3.Error:  # pragma: no cover - already closed / interpreter teardown
        pass


class MemoryStoreImpl:
    """SQLite-backed MemoryStore implementing the MemoryStore Protocol.

    All data persists locally. Zero external calls.
    """

    def __init__(self, db_path: str | pathlib.Path = ":memory:") -> None:
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            pathlib.Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connect()

    def _connect(self) -> None:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(_SCHEMA)
        except sqlite3.Error:
            conn.close()
            raise
        self._conn = conn
        self._finalizer = weakref.finalize(self, _close_connection, conn)
        logger.info("MemoryStore initialized: %s", self._db_path)

    def reopen(self) -> None:
        """Reopen after an ASGI restart, preserving all service references."""
        with self._lock:
            if self.closed:
                self._connect()

    @property
    def closed(self) -> bool:
        """True once the underlying SQLite connection has been released."""
        return not self._finalizer.alive

    def close(self) -> None:
        """Close the database connection (idempotent, thread-safe)."""
        with self._lock:
            self._finalizer()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # ---- Document operations ----

    def upsert_document(self, doc: Document) -> None:
        """Insert or update a document record."""
        self._conn.execute(
            """INSERT OR REPLACE INTO documents
               (doc_id, source_path, sha256, page_count, ingested_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                doc.doc_id,
                doc.source_path,
                doc.sha256,
                doc.page_count,
                doc.ingested_at.isoformat(),
            ),
        )
        self._conn.commit()
        logger.debug("Upserted document: %s", doc.doc_id)

    def upsert_page(self, page: Page) -> None:
        """Insert or update a page record."""
        self._conn.execute(
            """INSERT OR REPLACE INTO pages
               (doc_id, index_val, width_px, height_px, image_sha256)
               VALUES (?, ?, ?, ?, ?)""",
            (
                page.doc_id,
                page.index,
                page.width_px,
                page.height_px,
                page.image_sha256,
            ),
        )
        self._conn.commit()

    def get_pages(self, doc_id: str) -> list[Page]:
        """Retrieve all pages for a document."""
        rows = self._conn.execute(
            "SELECT * FROM pages WHERE doc_id = ? ORDER BY index_val ASC",
            (doc_id,),
        ).fetchall()
        return [
            Page(
                doc_id=row["doc_id"],
                index=row["index_val"],
                width_px=row["width_px"],
                height_px=row["height_px"],
                image_sha256=row["image_sha256"],
            )
            for row in rows
        ]

    def upsert_chunk(self, chunk: Chunk) -> None:
        """Insert or update a chunk record."""
        if chunk.bbox is None:
            raise ValueError(f"Chunk {chunk.chunk_id} has no bbox")

        self._conn.execute(
            """INSERT OR REPLACE INTO chunks
               (chunk_id, doc_id, page, bbox_x0, bbox_y0, bbox_x1, bbox_y1,
                text, source_type, embedding)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                chunk.chunk_id,
                chunk.doc_id,
                chunk.page,
                chunk.bbox.x0,
                chunk.bbox.y0,
                chunk.bbox.x1,
                chunk.bbox.y1,
                chunk.text,
                chunk.source_type,
                json.dumps(chunk.embedding),
            ),
        )
        self._conn.commit()

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        """Retrieve a chunk by ID."""
        row = self._conn.execute(
            "SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_chunk(row)

    def get_document(self, doc_id: str) -> Document | None:
        """Retrieve a document by ID."""
        row = self._conn.execute(
            "SELECT * FROM documents WHERE doc_id = ?", (doc_id,)
        ).fetchone()
        if row is None:
            return None
        return Document(
            doc_id=row["doc_id"],
            source_path=row["source_path"],
            sha256=row["sha256"],
            page_count=row["page_count"],
            ingested_at=datetime.fromisoformat(row["ingested_at"]),
        )

    # ---- Extraction operations ----

    def record_extraction(self, extraction: Extraction) -> None:
        """Record a new extraction."""
        self._conn.execute(
            """INSERT OR REPLACE INTO extractions
               (ext_id, pack_id, field_name, value, confidence,
                model_version, status, chunk_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                extraction.ext_id,
                extraction.pack_id,
                extraction.field_name,
                extraction.value,
                extraction.confidence,
                extraction.model_version,
                extraction.status.value,
                extraction.chunk_id,
            ),
        )
        self._conn.commit()
        logger.debug("Recorded extraction: %s", extraction.ext_id)

    def get_extraction(self, ext_id: str) -> Extraction | None:
        """Retrieve an extraction by ID."""
        row = self._conn.execute(
            "SELECT * FROM extractions WHERE ext_id = ?", (ext_id,)
        ).fetchone()
        if row is None:
            return None
        return Extraction(
            ext_id=row["ext_id"],
            pack_id=row["pack_id"],
            field_name=row["field_name"],
            value=row["value"],
            confidence=row["confidence"],
            model_version=row["model_version"],
            status=ExtractionStatus(row["status"]),
            chunk_id=row["chunk_id"],
        )

    # ---- Correction operations (flywheel) ----

    def record_correction(self, correction: Correction) -> None:
        """Record a human correction to an extraction (flywheel input)."""
        self._conn.execute(
            """INSERT OR REPLACE INTO corrections
               (corr_id, ext_id, original, corrected, reason, by_user, at_time)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                correction.corr_id,
                correction.ext_id,
                correction.original,
                correction.corrected,
                correction.reason,
                correction.by,
                correction.at.isoformat(),
            ),
        )
        self._conn.commit()
        logger.debug("Recorded correction: %s", correction.corr_id)

    def search_similar_corrections(
        self, field_name: str, value: str, k: int = 5
    ) -> list[Correction]:
        """Search for corrections on similar extractions.

        Uses field_name matching + text similarity (simple substring match).
        In production, this would use embedding-based similarity search.
        Returns the k most relevant corrections.
        """
        # Find extractions for the same field
        rows = self._conn.execute(
            """SELECT c.corr_id, c.ext_id, c.original, c.corrected,
                      c.reason, c.by_user, c.at_time
               FROM corrections c
               JOIN extractions e ON c.ext_id = e.ext_id
               WHERE e.field_name = ?
               ORDER BY c.at_time DESC
               LIMIT ?""",
            (field_name, k),
        ).fetchall()

        corrections: list[Correction] = []
        for row in rows:
            corrections.append(
                Correction(
                    corr_id=row["corr_id"],
                    ext_id=row["ext_id"],
                    original=row["original"],
                    corrected=row["corrected"],
                    reason=row["reason"],
                    by=row["by_user"],
                    at=datetime.fromisoformat(row["at_time"]),
                )
            )

        # Score by text similarity (simple containment check)
        value_lower = value.lower()
        scored = []
        for corr in corrections:
            score = 0.0
            if value_lower in corr.original.lower():
                score = 0.8
            elif corr.original.lower() in value_lower:
                score = 0.6
            else:
                # Partial word overlap
                value_words = set(value_lower.split())
                orig_words = set(corr.original.lower().split())
                overlap = value_words & orig_words
                if overlap:
                    score = len(overlap) / max(len(value_words), 1) * 0.4
            scored.append((score, corr))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [corr for _, corr in scored[:k]]

    # ---- Entity operations ----

    def upsert_entity(self, entity: Entity) -> None:
        """Insert or update an entity record."""
        self._conn.execute(
            """INSERT OR REPLACE INTO entities
               (entity_id, kind, value, normalized)
               VALUES (?, ?, ?, ?)""",
            (
                entity.entity_id,
                entity.kind,
                entity.value,
                entity.normalized,
            ),
        )
        self._conn.commit()

    def get_entity(self, entity_id: str) -> Entity | None:
        """Retrieve an entity by ID."""
        row = self._conn.execute(
            "SELECT * FROM entities WHERE entity_id = ?", (entity_id,)
        ).fetchone()
        if row is None:
            return None
        return Entity(
            entity_id=row["entity_id"],
            kind=row["kind"],
            value=row["value"],
            normalized=row["normalized"],
        )

    # ---- ModelVersion operations ----

    def upsert_model_version(self, mv: ModelVersion) -> None:
        """Insert or update a model version record."""
        self._conn.execute(
            """INSERT OR REPLACE INTO model_versions
               (model_id, name, weights_hash, tier)
               VALUES (?, ?, ?, ?)""",
            (
                mv.model_id,
                mv.name,
                mv.weights_hash,
                mv.tier,
            ),
        )
        self._conn.commit()

    def get_model_version(self, model_id: str) -> ModelVersion | None:
        """Retrieve a model version by ID."""
        row = self._conn.execute(
            "SELECT * FROM model_versions WHERE model_id = ?", (model_id,)
        ).fetchone()
        if row is None:
            return None
        return ModelVersion(
            model_id=row["model_id"],
            name=row["name"],
            weights_hash=row["weights_hash"],
            tier=row["tier"],
        )

    # ---- User operations ----

    def upsert_user(self, user: User) -> None:
        """Insert or update a user record."""
        self._conn.execute(
            """INSERT OR REPLACE INTO users (user_id) VALUES (?)""",
            (user.user_id,),
        )
        self._conn.commit()

    def get_user(self, user_id: str) -> User | None:
        """Retrieve a user by ID."""
        row = self._conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return None
        return User(
            user_id=row["user_id"],
        )

    # ---- Action operations ----

    def upsert_action(self, action: Action) -> None:
        """Insert or update an action record."""
        self._conn.execute(
            """INSERT OR REPLACE INTO actions
               (action_id, ext_id, kind, target_app, payload, confidence, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                action.action_id,
                action.ext_id,
                action.kind.value,
                action.target_app,
                json.dumps(action.payload),
                action.confidence,
                action.status.value,
            ),
        )
        self._conn.commit()

    def get_action(self, action_id: str) -> Action | None:
        """Retrieve an action by ID."""
        row = self._conn.execute(
            "SELECT * FROM actions WHERE action_id = ?", (action_id,)
        ).fetchone()
        if row is None:
            return None
        return Action(
            action_id=row["action_id"],
            ext_id=row["ext_id"],
            kind=ActionKind(row["kind"]),
            target_app=row["target_app"],
            payload=json.loads(row["payload"]),
            confidence=row["confidence"],
            status=ActionStatus(row["status"]),
        )

    # ---- Helpers ----

    @staticmethod
    def _row_to_chunk(row: sqlite3.Row) -> Chunk:
        return Chunk(
            chunk_id=row["chunk_id"],
            doc_id=row["doc_id"],
            page=row["page"],
            bbox=BBox(
                x0=row["bbox_x0"],
                y0=row["bbox_y0"],
                x1=row["bbox_x1"],
                y1=row["bbox_y1"],
            ),
            text=row["text"],
            source_type=row["source_type"],
            embedding=json.loads(row["embedding"]),
        )

    @property
    def stats(self) -> dict[str, int]:
        """Return count of stored entities."""
        counts: dict[str, int] = {}
        for table in (
            "documents",
            "chunks",
            "extractions",
            "corrections",
            "entities",
            "model_versions",
            "users",
            "actions",
        ):
            row = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = row[0]
        return counts
