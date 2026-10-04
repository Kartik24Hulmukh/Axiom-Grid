"""Authenticated, custody-safe cross-machine memory migration."""
from __future__ import annotations

import base64
import json
import logging
import os
import stat
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from sidecar.safety.pii_guard import PiiGuard
from sidecar.safety.prompt_shield import PromptShield

log = logging.getLogger("kairo-sidecar.memory_export_import")
MAGIC = b"KAIRO_MEM\x02"
FORMAT_VERSION = 2
SALT_BYTES = 16
NONCE_BYTES = 12
MAX_EXPORT_BYTES = 64 * 1024 * 1024
MAX_MEMORIES = 100_000
AAD = b"kairo-memory-export:v2"


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    if not passphrase:
        raise ValueError("A non-empty memory export passphrase is required")
    return Scrypt(salt=salt, length=32, n=2**14, r=8, p=1).derive(passphrase.encode("utf-8"))


def _read_private_regular_file(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Memory export must be a regular file")
        # st_nlink is reliable on both POSIX and Windows: a single-link file
        # reports 1, a hardlinked file reports 2 (link count is maintained by
        # NTFS and POSIX alike). Reject anything that is not single-link.
        if info.st_nlink != 1:
            raise ValueError("Memory export must be a single-link regular file")
        if info.st_size > MAX_EXPORT_BYTES:
            raise ValueError("Memory export exceeds the byte limit")
        with os.fdopen(descriptor, "rb", closefd=True) as source:
            return source.read(MAX_EXPORT_BYTES + 1)
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass


def _atomic_private_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        existing = path.lstat()
    except FileNotFoundError:
        existing = None
    if existing is not None and (not stat.S_ISREG(existing.st_mode) or existing.st_nlink != 1):
        raise ValueError("Refusing unsafe memory export destination")

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as target:
                target.write(payload)
                target.flush()
                os.fsync(target.fileno())
        finally:
            # Windows has no fchmod and cannot chmod an open fd: apply the
            # private-file mode after the handle is released. On POSIX this
            # is a no-op because fchmod already ran.
            if not hasattr(os, "fchmod") and os.name == "nt":
                try:
                    os.chmod(temporary, 0o600)
                except OSError:
                    pass
        os.replace(temporary, path)
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        else:
            # Windows cannot fsync a directory handle; the file fsync above
            # plus the atomic replace provide the durability guarantee.
            pass
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


class MemoryExportImport:
    """Versioned AES-256-GCM memory export/import."""

    def __init__(self, passphrase: Optional[str] = None):
        self.pii_guard = PiiGuard()
        self.prompt_shield = PromptShield()
        self.passphrase = passphrase or os.environ.get("KAIRO_MEMORY_PASSPHRASE")
        if not self.passphrase:
            raise ValueError("Set KAIRO_MEMORY_PASSPHRASE or provide an explicit passphrase")

    def _build_export(
        self, memories: List[Dict], *, include_pii: bool, user_id: Optional[str] = None
    ) -> dict:
        if len(memories) > MAX_MEMORIES:
            raise ValueError("Memory export exceeds the record limit")
        scrubbed = []
        for memory in memories:
            entry = dict(memory)
            if not include_pii:
                for key, value in entry.items():
                    if isinstance(value, str):
                        entry[key] = self.pii_guard.redact(value)
            scrubbed.append(entry)
        metadata = {
            "exported_at": time.time(),
            "memory_count": len(scrubbed),
            "pii_included": include_pii,
        }
        if user_id is not None:
            metadata["user_id"] = user_id
        return {
            "format": "kairo-memory",
            "version": FORMAT_VERSION,
            "metadata": metadata,
            "memories": scrubbed,
        }

    def _encrypt(self, export_data: dict) -> bytes:
        plaintext = json.dumps(
            export_data, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        if len(plaintext) > MAX_EXPORT_BYTES:
            raise ValueError("Memory export exceeds the byte limit")
        salt, nonce = os.urandom(SALT_BYTES), os.urandom(NONCE_BYTES)
        ciphertext = AESGCM(_derive_key(self.passphrase, salt)).encrypt(nonce, plaintext, AAD)
        envelope = {
            "format": "kairo-memory-encrypted",
            "version": FORMAT_VERSION,
            "kdf": {"name": "scrypt", "n": 2**14, "r": 8, "p": 1},
            "cipher": "AES-256-GCM",
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }
        return MAGIC + json.dumps(envelope, separators=(",", ":")).encode("ascii")

    def export_to_file(
        self, memories: List[Dict], output_path: str, include_pii: bool = False
    ) -> str:
        payload = self._encrypt(self._build_export(memories, include_pii=include_pii))
        _atomic_private_write(Path(output_path), payload)
        log.info(
            "Exported %d memories with authenticated encryption (include_pii=%s)",
            len(memories),
            include_pii,
        )
        return output_path

    def import_from_file(self, file_path: str) -> List[Dict]:
        raw = _read_private_regular_file(Path(file_path))
        if not raw.startswith(MAGIC):
            raise ValueError(
                "Legacy or plaintext memory exports are disabled; use an explicit migration tool"
            )
        try:
            envelope = json.loads(raw[len(MAGIC) :].decode("ascii"))
            if (
                envelope.get("version") != FORMAT_VERSION
                or envelope.get("cipher") != "AES-256-GCM"
                or envelope.get("kdf", {}).get("name") != "scrypt"
            ):
                raise ValueError("Unsupported memory export format")
            salt = base64.b64decode(envelope["salt"], validate=True)
            nonce = base64.b64decode(envelope["nonce"], validate=True)
            ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
            if len(salt) != SALT_BYTES or len(nonce) != NONCE_BYTES:
                raise ValueError("Invalid memory export parameters")
            plaintext = AESGCM(_derive_key(self.passphrase, salt)).decrypt(
                nonce, ciphertext, AAD
            )
            data = json.loads(plaintext.decode("utf-8"))
        except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid memory export envelope") from exc
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Memory export authentication failed") from exc

        memories = data.get("memories")
        if (
            data.get("format") != "kairo-memory"
            or data.get("version") != FORMAT_VERSION
            or not isinstance(memories, list)
            or len(memories) > MAX_MEMORIES
        ):
            raise ValueError("Invalid decrypted memory export")
        log.info("Imported %d authenticated memory records", len(memories))
        return memories

    def export_to_kairo_memory(
        self,
        memories: List[Dict],
        output_path: str,
        user_id: str = "local",
        include_pii: bool = False,
    ) -> str:
        payload = self._encrypt(
            self._build_export(memories, include_pii=include_pii, user_id=user_id)
        )
        _atomic_private_write(Path(output_path), payload)
        log.info("Exported %d memories in authenticated .kairo-memory format", len(memories))
        return output_path
