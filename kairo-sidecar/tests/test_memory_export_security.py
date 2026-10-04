"""Memory exports require authenticated encryption and safe file custody."""
from __future__ import annotations

import os
import stat

import pytest

from sidecar.memory.memory_export_import import MAGIC, MemoryExportImport

PASSPHRASE = "correct horse battery staple for tests"
MEMORIES = [{"id": 1, "text": "private preference", "user_id": "local"}]


def test_export_requires_explicit_nonempty_passphrase(monkeypatch):
    monkeypatch.delenv("KAIRO_MEMORY_PASSPHRASE", raising=False)
    with pytest.raises(ValueError, match="passphrase"):
        MemoryExportImport()


def test_authenticated_roundtrip_is_randomized_and_private(tmp_path):
    exporter = MemoryExportImport(PASSPHRASE)
    first, second = tmp_path / "first.kairo-memory", tmp_path / "second.kairo-memory"
    exporter.export_to_file(MEMORIES, str(first), include_pii=True)
    exporter.export_to_file(MEMORIES, str(second), include_pii=True)

    assert first.read_bytes().startswith(MAGIC)
    assert first.read_bytes() != second.read_bytes()
    assert stat.S_IMODE(first.stat().st_mode) == 0o600
    assert exporter.import_from_file(str(first)) == MEMORIES


def test_wrong_key_tamper_plaintext_and_legacy_fail_closed(tmp_path):
    path = tmp_path / "memory.kairo-memory"
    MemoryExportImport(PASSPHRASE).export_to_file(MEMORIES, str(path), include_pii=True)

    with pytest.raises(ValueError, match="authentication"):
        MemoryExportImport("wrong passphrase").import_from_file(str(path))

    payload = bytearray(path.read_bytes())
    payload[-8] ^= 1
    path.write_bytes(payload)
    with pytest.raises(ValueError):
        MemoryExportImport(PASSPHRASE).import_from_file(str(path))

    path.write_text('{"memories": [{"text": "plaintext"}]}')
    with pytest.raises(ValueError, match="Legacy or plaintext"):
        MemoryExportImport(PASSPHRASE).import_from_file(str(path))

    path.write_bytes(b"KAIRO_MEM\x00legacy-xor")
    with pytest.raises(ValueError, match="Legacy or plaintext"):
        MemoryExportImport(PASSPHRASE).import_from_file(str(path))


def test_symlink_and_hardlink_destinations_are_rejected(tmp_path):
    exporter = MemoryExportImport(PASSPHRASE)
    victim = tmp_path / "victim"
    victim.write_text("unchanged")
    symlink = tmp_path / "symlink.kairo-memory"
    symlink.symlink_to(victim)
    with pytest.raises(ValueError, match="unsafe"):
        exporter.export_to_file(MEMORIES, str(symlink))
    assert victim.read_text() == "unchanged"

    hardlink = tmp_path / "hardlink.kairo-memory"
    os.link(victim, hardlink)
    with pytest.raises(ValueError, match="unsafe"):
        exporter.export_to_file(MEMORIES, str(hardlink))
    assert victim.read_text() == "unchanged"


def test_hardlinked_import_is_rejected(tmp_path):
    exporter = MemoryExportImport(PASSPHRASE)
    original = tmp_path / "original.kairo-memory"
    linked = tmp_path / "linked.kairo-memory"
    exporter.export_to_file(MEMORIES, str(original), include_pii=True)
    os.link(original, linked)
    with pytest.raises(ValueError, match="single-link"):
        exporter.import_from_file(str(linked))
