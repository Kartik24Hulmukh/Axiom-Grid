#!/usr/bin/env python3
"""
Kairo Phantom — OS Keychain Storage Abstraction (P1.2)

Provides a secure key storage interface that uses the OS keychain (via the
`keyring` library) for BYO-key cloud API keys. Keys are NEVER stored in
config files, log files, or the provenance store.

When `keyring` is not available (e.g., headless Linux without Secret Service),
this falls back to an in-memory store with an explicit warning. The fallback
is NOT persistent and is clearly labeled as less secure.

Security invariants enforced:
1. No key material is ever written to disk in plaintext.
2. No key material is ever written to log output.
3. Config files never contain key material.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Service name for keychain entries
KAIRO_KEYCHAIN_SERVICE = "kairo-phantom"

# Prefix for environment variable keys (for testing/CI only)
KAIRO_ENV_PREFIX = "KAIRO_KEY_"


def _backend_is_usable(backend) -> bool:
    """True unless *backend* is keyring's fail/null backend (or a chainer of them).

    keyring >= 23 exposes the no-backend case as ``keyring.backends.fail.Keyring``
    (priority 0), not a class literally named ``FailKeyring``; matching on the
    class name alone let the broken backend through and the first
    ``set_password`` raised ``NoKeyringError`` in production.
    """
    module = type(backend).__module__ or ""
    if module.startswith("keyring.backends.fail") or module.startswith("keyring.backends.null"):
        return False
    try:
        if float(getattr(backend, "priority", 1)) <= 0:
            return False
    except (TypeError, ValueError):
        pass
    backends = getattr(backend, "backends", None)
    if backends is not None:  # ChainerBackend
        return any(_backend_is_usable(b) for b in backends)
    return True


class KeychainStore:
    """OS keychain abstraction for storing BYO-key cloud API keys.

    Uses the `keyring` library to store keys in:
    - macOS: Keychain
    - Linux: Secret Service / GNOME Keyring
    - Windows: Credential Manager

    Keys are NEVER written to config files or logs.
    """

    def __init__(self, service: str = KAIRO_KEYCHAIN_SERVICE):
        self.service = service
        self._keyring = None
        self._fallback_store: dict[str, str] = {}
        self._using_fallback = False

        try:
            import keyring
            from keyring import errors as keyring_errors

            backend = keyring.get_keyring()
            if backend is None or not _backend_is_usable(backend):
                raise keyring_errors.NoKeyringError(
                    "keyring resolved to the fail/null backend"
                )
            # Real round-trip probe: on headless Linux without a Secret Service
            # daemon get_keyring() still returns a backend object, and the
            # failure only surfaces on first use as NoKeyringError. Probe once
            # at construction so callers get the documented fallback instead
            # of an unhandled exception in the request path.
            backend.get_password(self.service, "__kairo_backend_probe__")
            self._keyring = keyring
        except Exception as exc:  # ImportError / keyring.errors.KeyringError / backend RuntimeError
            self._using_fallback = True
            logger.warning(
                "OS keychain not available (%s: %s). "
                "Using in-memory fallback — keys will NOT persist and this is less secure. "
                "Install 'keyring' and configure a backend (Secret Service on Linux, "
                "Keychain on macOS, Credential Manager on Windows).",
                type(exc).__name__, exc,
            )

    @property
    def using_fallback(self) -> bool:
        """True if using in-memory fallback instead of OS keychain."""
        return self._using_fallback

    def store_key(self, key_name: str, key_value: str) -> None:
        """Store a key in the OS keychain.

        SECURITY: This method NEVER writes the key to disk, config files,
        or logs. It only calls the keyring API or stores in memory.

        Args:
            key_name: Logical name for the key (e.g., "openai_api_key")
            key_value: The secret value to store
        """
        if not key_value:
            raise ValueError("Cannot store empty key value")

        # NEVER log the key value
        logger.info("Storing key '%s' in %s", key_name,
                     "OS keychain" if not self._using_fallback else "in-memory fallback")

        if self._keyring:
            self._keyring.set_password(self.service, key_name, key_value)
        else:
            self._fallback_store[key_name] = key_value

    def retrieve_key(self, key_name: str) -> Optional[str]:
        """Retrieve a key from the OS keychain.

        Returns None if the key does not exist.
        NEVER logs the retrieved value.
        """
        if self._keyring:
            return self._keyring.get_password(self.service, key_name)
        return self._fallback_store.get(key_name)

    def delete_key(self, key_name: str) -> bool:
        """Delete a key from the OS keychain. Returns True if deleted."""
        if self._keyring:
            try:
                self._keyring.delete_password(self.service, key_name)
                return True
            except Exception:
                return False
        if key_name in self._fallback_store:
            del self._fallback_store[key_name]
            return True
        return False

    def list_key_names(self) -> list[str]:
        """List stored key names (NOT values). Safe to log."""
        if self._keyring:
            # keyring doesn't have a standard list API; we track known names
            # via a metadata entry
            meta = self._keyring.get_password(self.service, "__key_names__")
            if meta:
                import json
                return json.loads(meta)
            return []
        return list(self._fallback_store.keys())


# ---------------------------------------------------------------------------
# Verification utilities — used by tests to prove no key leakage
# ---------------------------------------------------------------------------

def scan_config_files_for_keys(config_dir: str, key_patterns: list[str]) -> list[str]:
    """Scan config files for any key material. Returns list of violations.

    This is a verification utility used by tests to prove that keys never
    leak into config files. It searches for common key patterns.
    """
    import os
    import re

    violations = []
    if not os.path.isdir(config_dir):
        return violations

    # Patterns that indicate API key material
    key_regexes = [re.compile(p, re.IGNORECASE) for p in key_patterns]

    for root, dirs, files in os.walk(config_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            # Only scan text-based config files
            if not fname.endswith(('.toml', '.json', '.yaml', '.yml', '.env',
                                   '.ini', '.cfg', '.conf', '.txt')):
                continue
            try:
                with open(fpath, 'r', errors='ignore') as f:
                    content = f.read()
                    for regex in key_regexes:
                        matches = regex.findall(content)
                        if matches:
                            violations.append(f"{fpath}: found {len(matches)} match(es)")
            except IOError:
                continue

    return violations


def scan_logs_for_keys(log_dir: str, key_patterns: list[str]) -> list[str]:
    """Scan log files for any key material. Returns list of violations."""
    import os
    import re

    violations = []
    if not os.path.isdir(log_dir):
        return violations

    key_regexes = [re.compile(p, re.IGNORECASE) for p in key_patterns]

    for root, dirs, files in os.walk(log_dir):
        for fname in files:
            if not fname.endswith('.log'):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, 'r', errors='ignore') as f:
                    content = f.read()
                    for regex in key_regexes:
                        matches = regex.findall(content)
                        if matches:
                            violations.append(f"{fpath}: found {len(matches)} match(es)")
            except IOError:
                continue

    return violations


# Singleton instance
_store: Optional[KeychainStore] = None


def get_keychain_store() -> KeychainStore:
    """Get the singleton KeychainStore instance."""
    global _store
    if _store is None:
        _store = KeychainStore()
    return _store