"""AG-07 / AG-08 / AG-09 launch-hardening regressions.

Resource containment on *expanded* parser work, bounded readiness
revalidation (no permanent success cache), and a durable shared spend ledger.
Deterministic: no network, no sleeps beyond a 0.05s TTL window.
"""
from __future__ import annotations

import io
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest

from kernel.sidecar import ingestor as ingestor_mod
from kernel.sidecar.ingestor import IngestorImpl, ResourceBudgetExceeded, inspect_zip_container
from kernel.sidecar.melious_router import DurableSpendLedger, MeliousModelRouter, SpendCeilingError


# ---------------------------------------------------------------- AG-07

def _docx_bomb(path, declared_bytes: int, entries: int = 1) -> None:
    """Write a tiny zip whose central directory *declares* a huge payload."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        for i in range(entries):
            z.writestr(f"word/part{i}.xml", "<w/>")
    # Rewrite the first entry's declared uncompressed size in the central
    # directory so the bomb is detectable without inflating anything.
    data = bytearray(path.read_bytes())
    marker = data.rfind(b"PK\x01\x02")
    data[marker + 24:marker + 28] = declared_bytes.to_bytes(4, "little")
    path.write_bytes(bytes(data))


def test_docx_declared_decompression_bomb_rejected_before_parse(tmp_path):
    bomb = tmp_path / "bomb.docx"
    _docx_bomb(bomb, declared_bytes=ingestor_mod.MAX_DOCX_EXPANDED_BYTES + 1)
    assert bomb.stat().st_size < 4096  # tiny on the wire, huge when expanded
    with pytest.raises(ResourceBudgetExceeded):
        inspect_zip_container(bomb)
    with pytest.raises(ValueError):  # ResourceBudgetExceeded is a ValueError -> HTTP 422
        IngestorImpl().ingest(str(bomb))


def test_docx_entry_flood_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(ingestor_mod, "MAX_DOCX_ENTRIES", 4)
    flood = tmp_path / "flood.docx"
    _docx_bomb(flood, declared_bytes=10, entries=8)
    with pytest.raises(ResourceBudgetExceeded):
        inspect_zip_container(flood)


def test_real_docx_fixture_still_within_budget():
    entries, expanded = inspect_zip_container(
        ingestor_mod.pathlib.Path("fixtures/demo/sample_nda.docx"))
    assert entries <= ingestor_mod.MAX_DOCX_ENTRIES
    assert expanded <= ingestor_mod.MAX_DOCX_EXPANDED_BYTES


def test_pdf_page_flood_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(ingestor_mod, "MAX_PDF_PAGES", 2)
    pdf = tmp_path / "pages.pdf"
    pages = 5
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Kids [" + " ".join(f"{3+i} 0 R" for i in range(pages)) + f"] /Count {pages} >>"]
    objs += ["<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>" for _ in range(pages)]
    out = io.BytesIO(); out.write(b"%PDF-1.4\n"); offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(out.tell()); out.write(f"{i} 0 obj\n{o}\nendobj\n".encode())
    xref = out.tell()
    out.write(f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    pdf.write_bytes(out.getvalue())
    with pytest.raises(ResourceBudgetExceeded):
        IngestorImpl().ingest(str(pdf))


def test_extraction_deadline_returns_504_and_releases_slot(monkeypatch):
    from fastapi.testclient import TestClient

    from overlay import server

    release = threading.Event()

    class HangingIngestor:
        def ingest(self, path):
            release.wait(5)
            raise ValueError("aborted")

    monkeypatch.setattr(server, "EXTRACTION_DEADLINE_SECONDS", 0.2)
    monkeypatch.setattr(server, "IngestorImpl", HangingIngestor)
    before = server._extraction_slots._value
    with TestClient(server.app) as client:
        r = client.post("/api/extract-document", json={"file": "fixtures/demo/sample_nda.docx"})
    assert r.status_code == 504
    assert r.headers.get("retry-after") == "5"
    release.set()
    deadline = threading.Event()
    for _ in range(100):  # the worker's done-callback returns the slot exactly once
        if server._extraction_slots._value == before:
            break
        deadline.wait(0.05)
    assert server._extraction_slots._value == before
    assert server.OPS_METRICS["extraction_deadline_total"] >= 1


# ---------------------------------------------------------------- AG-09

def test_readyz_revalidates_after_ttl_and_recovers(monkeypatch):
    from fastapi.testclient import TestClient

    from overlay import server

    server._readyz_state.update(verdict=None, checked_at=0.0)
    monkeypatch.setattr(server, "READYZ_TTL_SECONDS", 0.05)
    monkeypatch.setattr(server, "READYZ_NEGATIVE_TTL_SECONDS", 0.05)
    client = TestClient(server.app)
    first = client.get("/readyz")
    assert first.status_code == 200 and first.json()["checks"]["pdf_parser"] == "ok"
    assert client.get("/readyz").json().get("cached") is True

    # Dependency breaks: after the TTL the pod must leave rotation (503) ...
    real_checks = server._readyz_dependency_checks
    monkeypatch.setattr(server, "_readyz_dependency_checks",
                        lambda: {**real_checks(), "pdf_parser": "missing:ImportError"})
    threading.Event().wait(0.06)
    broken = client.get("/readyz")
    assert broken.status_code == 503
    assert broken.json()["status"] == "not_ready"
    assert not server._readyz_probe_ok.is_set()

    # ... and recover automatically once the dependency is back.
    monkeypatch.setattr(server, "_readyz_dependency_checks", real_checks)
    threading.Event().wait(0.06)
    assert client.get("/readyz").status_code == 200


def test_readyz_single_flight_under_probe_stampede(monkeypatch):
    from fastapi.testclient import TestClient

    from overlay import server

    server._readyz_state.update(verdict=None, checked_at=0.0)
    monkeypatch.setattr(server, "READYZ_TTL_SECONDS", 30.0)
    calls = []
    real = server._readyz_dependency_checks

    def counting():
        calls.append(1)
        return real()

    monkeypatch.setattr(server, "_readyz_dependency_checks", counting)
    client = TestClient(server.app)
    with ThreadPoolExecutor(max_workers=32) as pool:
        codes = list(pool.map(lambda _: client.get("/readyz").status_code, range(64)))
    assert codes == [200] * 64
    assert len(calls) == 1, f"probe stampede: pipeline ran {len(calls)} times for 64 probes"


# ---------------------------------------------------------------- AG-08

def test_durable_ledger_shared_across_replicas_and_idempotent(tmp_path):
    path = tmp_path / "spend.sqlite"
    replica_a = DurableSpendLedger(str(path), ceiling=100)
    replica_b = DurableSpendLedger(str(path), ceiling=100)  # "another process"

    a1 = replica_a.reserve(60)
    with pytest.raises(SpendCeilingError):  # B sees A's reservation
        replica_b.reserve(50)
    b1 = replica_b.reserve(40)
    replica_a.settle(a1, 70)  # overshoot is real money and is never clamped
    replica_a.settle(a1, 70)  # idempotent replay: no double count
    replica_b.settle(b1, 10)
    snap = replica_b.snapshot()
    assert snap["spend_committed"] == 80 and snap["spend_reserved"] == 0
    assert replica_a.reserve(20, attempt_id="retry-1") == "retry-1"
    assert replica_a.reserve(20, attempt_id="retry-1") == "retry-1"  # replayed retry reserves once
    assert replica_a.snapshot()["spend_reserved"] == 20


def test_durable_ledger_concurrent_admission_never_exceeds_ceiling(tmp_path):
    path = tmp_path / "spend.sqlite"
    ledgers = [DurableSpendLedger(str(path), ceiling=1000) for _ in range(4)]
    admitted = []

    def worker(i):
        try:
            ledgers[i % 4].reserve(90)
            admitted.append(90)
        except SpendCeilingError:
            pass

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(worker, range(64)))
    assert sum(admitted) <= 1000 and sum(admitted) >= 900
    assert ledgers[0].snapshot()["spend_reserved"] == sum(admitted)


def test_durable_ledger_reconcile_charges_stale_reservations(tmp_path):
    ledger = DurableSpendLedger(str(tmp_path / "s.sqlite"), ceiling=None, stale_after_seconds=1.0)
    ledger.reserve(30)
    import time
    assert ledger.reconcile(now=time.time() + 5) == 1
    snap = ledger.snapshot()
    assert snap["spend_reserved"] == 0 and snap["spend_committed"] == 30  # charged, not forgiven


def test_router_uses_durable_ledger_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MELIOUS_SPEND_LEDGER", str(tmp_path / "router.sqlite"))
    monkeypatch.setenv("MELIOUS_TOKEN_CEILING", "50")
    usage = {"usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
             "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}
    router = MeliousModelRouter(transport=lambda model, payload, timeout: dict(usage), sleep=lambda s: None)
    assert isinstance(router.spend, DurableSpendLedger)
    router.complete([{"role": "user", "content": "hi"}], max_tokens=8)
    snap = router.spend.snapshot()
    assert snap["spend_committed"] == 10 and snap["spend_reserved"] == 0
    with pytest.raises(SpendCeilingError):
        router.complete([{"role": "user", "content": "x" * 300}], max_tokens=64)
