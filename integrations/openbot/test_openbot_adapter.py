"""Integration test: OpenBot receipt adapter emits a verifiable signed chain.

Tests the Open Agent Receipt Specification v0.1 integration surface:
emit -> export JSONL -> re-load -> verify chain end-to-end with the real
Ed25519 audit-log primitives (no mocks).
"""
import json
from pathlib import Path

import pytest

from integrations.openbot.adapter import OpenBotReceiptAdapter


@pytest.fixture()
def adapter(tmp_path: Path) -> OpenBotReceiptAdapter:
    key_path = tmp_path / "bot_ed25519.pem"
    return OpenBotReceiptAdapter(agent_id="test-bot", key_path=key_path)


def test_emit_and_verify_chain(adapter: OpenBotReceiptAdapter, tmp_path: Path) -> None:
    adapter.log_run_started(doc_hash="deadbeef", playbook_id="openbot-test")
    adapter.log_action("read", doc_hash="deadbeef", summary={"url": "https://example.com", "citations": [{"page": 1, "line": 4}]})
    adapter.log_action("suggest", doc_hash="deadbeef", summary={"citations": [{"page": 2, "line": 10}]})

    assert len(adapter._entries) == 3
    # Every entry is signed and chain-linked
    for e in adapter._entries:
        assert e.signature
        assert e.entry_hash
    # Chain links: entry[1].prev_hash == entry[0].entry_hash
    assert adapter._entries[1].prev_hash == adapter._entries[0].entry_hash
    assert adapter._entries[2].prev_hash == adapter._entries[1].entry_hash
    # Native in-memory chain verification passes
    assert adapter.verify() is True


def test_export_reload_verify(adapter: OpenBotReceiptAdapter, tmp_path: Path) -> None:
    adapter.log_run_started(doc_hash="abcd", playbook_id="openbot-export")
    adapter.log_action("export", doc_hash="abcd", summary={"format": "pdf"})

    out = adapter.export(tmp_path / "receipts.jsonl")
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    entries = data["entries"]
    assert len(entries) == 2
    assert data["version"] == 1
    assert data["agent_id"] == "test-bot"
    obj = entries[0]
    assert obj["action"] == "run_started"
    assert obj.get("signature") or data.get("signatures")

    # Third-party-style verification from the exported JSONL
    assert adapter.verify(tmp_path / "receipts.jsonl") is True


def test_tamper_detected(adapter: OpenBotReceiptAdapter, tmp_path: Path) -> None:
    adapter.log_run_started(doc_hash="beef", playbook_id="openbot-tamper")
    out = adapter.export(tmp_path / "receipts.jsonl")

    # Tamper with a signed content field (edit_summary feeds content_bytes,
    # so the hash and the Ed25519 signature both stop matching).
    data = json.loads(out.read_text(encoding="utf-8"))
    data["entries"][0]["edit_summary"] = {"tampered": True}
    out.write_text(json.dumps(data), encoding="utf-8")

    fresh = OpenBotReceiptAdapter(agent_id="test-bot", key_path=adapter.key_path)
    assert fresh.verify(tmp_path / "receipts.jsonl") is False
