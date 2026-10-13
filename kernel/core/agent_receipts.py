"""Open Receipt v0.1: bounded, offline, pinned-key verification.

Signs observations, not their truth or completeness. A signed checkpoint binds
the exported count and tail; only an independently retained checkpoint detects
replacement by an older, otherwise valid export.
"""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

VERSION = "axiom.receipts/0.1"
MAX_EVENT_BYTES = 65536
MAX_EXPORT_BYTES = 16 * 1024 * 1024
MAX_EVENTS = 10000
_FIELDS = {"version", "session_id", "sequence", "event_id", "observed_at",
           "source", "source_event_id", "action", "outcome", "evidence_sha256",
           "prev_hash"}


class ReceiptError(ValueError):
    """Invalid or untrusted receipt material."""


def canonical(value) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (ValueError, TypeError, RecursionError) as exc:
        raise ReceiptError("receipt must contain bounded finite JSON") from exc


def _digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _text(value, label, limit=256):
    if not isinstance(value, str) or not value or len(value) > limit:
        raise ReceiptError(f"{label} must be non-empty text of at most {limit} characters")
    if any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ReceiptError(f"{label} contains invalid control characters")
    return value


def _verify_signature(key, signature, value):
    try:
        if not isinstance(signature, str) or len(signature) != 128:
            raise ValueError("signature length")
        key.verify(bytes.fromhex(signature), canonical(value))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise ReceiptError("invalid Ed25519 signature") from exc


class ReceiptSession:
    """Thread-safe, bounded single-process signer; export snapshots are copies.

    A deployment must supply its own persisted private key. No automatic key
    creation, embedded private key, network client, or shared global signer.
    """
    def __init__(self, key: Ed25519PrivateKey, session_id: str | None = None):
        if not isinstance(key, Ed25519PrivateKey):
            raise ReceiptError("an Ed25519 private key is required")
        self._key = key
        self.session_id = _text(session_id or uuid.uuid4().hex, "session_id")
        self._lock = threading.Lock()
        self._entries = []
        self._bytes = 0

    def append(self, *, source, source_event_id, action, outcome, evidence):
        # Minimise disclosure: commit to evidence; never copy raw prompts,
        # credentials, results, or document text into the exported receipt.
        for label, value in (("source", source), ("source_event_id", source_event_id),
                             ("action", action), ("outcome", outcome)):
            _text(value, label)
        encoded = canonical(evidence)
        if len(encoded) > MAX_EVENT_BYTES:
            raise ReceiptError("event exceeds evidence byte budget")
        with self._lock:
            if len(self._entries) >= MAX_EVENTS:
                raise ReceiptError("session exceeds event count budget")
            payload = {
                "version": VERSION, "session_id": self.session_id,
                "sequence": len(self._entries), "event_id": uuid.uuid4().hex,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "source": source, "source_event_id": source_event_id,
                "action": action, "outcome": outcome,
                "evidence_sha256": hashlib.sha256(encoded).hexdigest(),
                "prev_hash": self._entries[-1]["entry_hash"] if self._entries else "",
            }
            entry = {"payload": payload, "entry_hash": _digest(payload),
                     "signature": self._key.sign(canonical(payload)).hex()}
            size = len(canonical(entry))
            if self._bytes + size > MAX_EXPORT_BYTES - 4096:
                raise ReceiptError("session exceeds export byte budget")
            self._entries.append(entry)
            self._bytes += size
            return json.loads(canonical(entry))

    def export(self):
        with self._lock:
            checkpoint = {"version": VERSION, "session_id": self.session_id,
                          "entry_count": len(self._entries),
                          "tail_hash": self._entries[-1]["entry_hash"] if self._entries else ""}
            bundle = {"checkpoint": checkpoint,
                      "checkpoint_signature": self._key.sign(canonical(checkpoint)).hex(),
                      "entries": self._entries}
            return json.loads(canonical(bundle))


def verify_bundle(bundle, key: Ed25519PublicKey, expected_checkpoint=None):
    """Fail closed; key comes from the caller, never from the untrusted bundle."""
    if not isinstance(key, Ed25519PublicKey):
        raise ReceiptError("a pinned Ed25519 public key is required")
    if not isinstance(bundle, dict) or set(bundle) != {
        "checkpoint", "checkpoint_signature", "entries"
    }:
        raise ReceiptError("invalid receipt envelope")
    if len(canonical(bundle)) > MAX_EXPORT_BYTES:
        raise ReceiptError("export exceeds byte budget")
    checkpoint = bundle["checkpoint"]
    if not isinstance(checkpoint, dict) or set(checkpoint) != {
        "version", "session_id", "entry_count", "tail_hash"
    } or checkpoint["version"] != VERSION:
        raise ReceiptError("invalid checkpoint schema")
    _text(checkpoint["session_id"], "session_id")
    _verify_signature(key, bundle["checkpoint_signature"], checkpoint)
    entries = bundle["entries"]
    if not isinstance(entries, list) or len(entries) > MAX_EVENTS:
        raise ReceiptError("invalid entry count")
    if type(checkpoint["entry_count"]) is not int or checkpoint["entry_count"] != len(entries):
        raise ReceiptError("checkpoint count mismatch")
    if expected_checkpoint is not None and canonical(checkpoint) != canonical(expected_checkpoint):
        raise ReceiptError("externally retained checkpoint mismatch")
    previous = ""
    ids = set()
    for sequence, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {"payload", "entry_hash", "signature"}:
            raise ReceiptError("invalid entry envelope")
        payload = entry["payload"]
        if not isinstance(payload, dict) or set(payload) != _FIELDS:
            raise ReceiptError("invalid event schema")
        if (payload["version"] != VERSION or payload["session_id"] != checkpoint["session_id"]
                or type(payload["sequence"]) is not int or payload["sequence"] != sequence
                or payload["prev_hash"] != previous):
            raise ReceiptError("broken session or sequence chain")
        for label in ("event_id", "observed_at", "source", "source_event_id", "action", "outcome"):
            _text(payload[label], label)
        digest = payload["evidence_sha256"]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ReceiptError("invalid evidence digest")
        if payload["event_id"] in ids:
            raise ReceiptError("duplicate event identifier")
        ids.add(payload["event_id"])
        if entry["entry_hash"] != _digest(payload):
            raise ReceiptError("entry hash mismatch")
        _verify_signature(key, entry["signature"], payload)
        previous = entry["entry_hash"]
    if checkpoint["tail_hash"] != previous:
        raise ReceiptError("checkpoint tail mismatch")
    return {"valid": True, "version": VERSION, "session_id": checkpoint["session_id"],
            "entry_count": len(entries), "tail_hash": previous,
            "scope": "signed observations; not proof of execution, completeness, or zero egress"}