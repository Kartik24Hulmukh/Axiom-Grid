"""Production credentials come from a bounded read-only secret file."""
import hashlib

import pytest

from overlay import server


def test_loads_read_only_key_file(monkeypatch, tmp_path):
    key = "secret-file-key-0123456789abcdef"
    path = tmp_path / "api.keys"
    path.write_text(f"{key}\nshort\n")
    path.chmod(0o400)
    monkeypatch.setenv("AXIOM_API_KEYS_FILE", str(path))
    monkeypatch.delenv("AXIOM_API_KEYS", raising=False)

    digest = hashlib.sha256(key.encode()).hexdigest()
    assert server._load_api_key_digests() == {digest: digest}


def test_inline_compatibility_value_is_removed_from_environment(monkeypatch):
    key = "local-ci-only-key-0123456789"
    monkeypatch.delenv("AXIOM_API_KEYS_FILE", raising=False)
    monkeypatch.setenv("AXIOM_API_KEYS", key)

    assert server._load_api_key_digests()
    assert "AXIOM_API_KEYS" not in server.os.environ


def test_rejects_ambiguous_or_writable_secret_sources(monkeypatch, tmp_path):
    path = tmp_path / "api.keys"
    path.write_text("secret-file-key-0123456789abcdef\n")
    path.chmod(0o600)
    monkeypatch.setenv("AXIOM_API_KEYS_FILE", str(path))
    monkeypatch.delenv("AXIOM_API_KEYS", raising=False)
    with pytest.raises(RuntimeError, match="read-only"):
        server._load_api_key_digests()

    path.chmod(0o400)
    monkeypatch.setenv("AXIOM_API_KEYS", "inline-key-0123456789abcdef")
    with pytest.raises(RuntimeError, match="not both"):
        server._load_api_key_digests()