"""Concurrency & thread-safety regression gauntlet (launch-blocker #1).

Before the September 2026 launch hardening, every overlay request serialized on
a single global mutex and the shared services mutated unguarded dicts/SQLite
handles. Under 100 concurrent clients that shed 80-91% of requests. These tests
lock in the fix:

1. ProvenanceLogImpl is safe under concurrent register/read and exposes
   snapshot accessors (no dict-changed-size-during-iteration).
2. MemoryStoreImpl serializes its SQLite access internally.
3. The overlay pipeline gate allows bounded PARALLELISM, not mutual exclusion.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from kernel.core.data_model import BBox, Chunk, Document, Extraction
from kernel.core.provenance import ProvenanceLogImpl
from kernel.sidecar.memory_store import MemoryStoreImpl

THREADS = 16
OPS = 60


class TestProvenanceThreadSafety:
    def test_class_is_marked_thread_safe(self):
        assert getattr(ProvenanceLogImpl, "__axiom_thread_safe__", False)

    def test_concurrent_register_and_snapshot_reads(self):
        log = ProvenanceLogImpl()
        doc = Document(source_path="/tmp/a.txt", sha256="0" * 64)
        log.register_document(doc)
        errors: list[BaseException] = []

        def writer(worker: int) -> None:
            try:
                for i in range(OPS):
                    chunk = Chunk(
                        doc_id=doc.doc_id,
                        page=1,
                        bbox=BBox(0, 0, 1, 1),
                        text=f"w{worker}-{i}",
                        source_type="text",
                    )
                    log.register_chunk(chunk)
                    log.register_extraction(
                        Extraction(field_name="f", value="v", chunk_id=chunk.chunk_id)
                    )
            except BaseException as exc:  # pragma: no cover - failure path
                errors.append(exc)

        def reader() -> None:
            try:
                for _ in range(OPS):
                    log.chunks_for_doc(doc.doc_id)
                    log.all_chunks()
                    log.stats
            except BaseException as exc:  # pragma: no cover - failure path
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=THREADS * 2) as pool:
            futures = [pool.submit(writer, w) for w in range(THREADS)]
            futures += [pool.submit(reader) for _ in range(THREADS)]
            for f in futures:
                f.result()

        assert not errors, f"concurrent provenance access raised: {errors[:3]}"
        assert len(log.chunks_for_doc(doc.doc_id)) == THREADS * OPS
        assert log.stats["extractions"] == THREADS * OPS

    def test_snapshot_accessor_is_a_copy(self):
        log = ProvenanceLogImpl()
        doc = Document(source_path="/tmp/b.txt", sha256="1" * 64)
        log.register_document(doc)
        chunk = Chunk(doc_id=doc.doc_id, page=1, bbox=BBox(0, 0, 1, 1), text="x")
        log.register_chunk(chunk)
        snap = log.chunks_for_doc(doc.doc_id)
        snap.clear()
        assert len(log.chunks_for_doc(doc.doc_id)) == 1


class TestMemoryStoreThreadSafety:
    def test_class_is_marked_thread_safe(self):
        assert getattr(MemoryStoreImpl, "__axiom_thread_safe__", False)

    def test_concurrent_writes_and_reads(self, tmp_path):
        store = MemoryStoreImpl(tmp_path / "concurrency.db")
        errors: list[BaseException] = []
        docs = [
            Document(source_path=f"/tmp/{i}.txt", sha256=f"{i:064d}")
            for i in range(THREADS * 4)
        ]

        def work(doc: Document) -> None:
            try:
                store.upsert_document(doc)
                for _ in range(10):
                    assert store.get_document(doc.doc_id) is not None
            except BaseException as exc:  # pragma: no cover - failure path
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            for f in [pool.submit(work, d) for d in docs]:
                f.result()

        assert not errors, f"concurrent store access raised: {errors[:3]}"
        assert store.stats["documents"] == len(docs)
        store.close()


class TestOverlayPipelineGate:
    """The gate must allow parallelism -- a single mutex is a launch blocker."""

    def test_gate_is_bounded_but_parallel(self):
        server = pytest.importorskip("overlay.server")
        gate = server.orchestrator_gate
        assert gate.limit > 1, "pipeline gate must not serialize requests"
        assert gate.limit == server.PIPELINE_CONCURRENCY

        entered = threading.Semaphore(0)
        release = threading.Event()
        holders = 2

        def hold() -> None:
            with gate:
                entered.release()
                release.wait(5)

        threads = [threading.Thread(target=hold) for _ in range(holders)]
        for t in threads:
            t.start()
        try:
            for _ in range(holders):
                assert entered.acquire(timeout=5), "gate serialized concurrent holders"
        finally:
            release.set()
            for t in threads:
                t.join(5)
