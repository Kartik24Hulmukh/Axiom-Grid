"""DSSE/in-toto envelope wrapper for portable legal-v3 evidence bundles.

Wraps a legal-v3 evidence bundle in a DSSE (Dead Simple Signing Envelope)
statement. Serialization and structural parsing do not authenticate it.
Authentication requires independently trusted keys or a trusted verifier; it
does not replace verify_bundle or establish legal acceptance.

Reference: https://github.com/secure-systems-lab/dsse

DSSE envelope format:
  {
    "payload": "<base64-encoded JSON>",
    "payloadType": "application/vnd.kairo.legal-v3.bundle+json",
    "signatures": [
      {"sig": "<base64 signature>", "keyid": "<key id>"}
    ]
  }

in-toto statement (wrapped inside the DSSE payload):
  {
    "_type": "https://in-toto.io/Statement/v1",
    "subject": [
      {"name": "<output filename>", "digest": {"sha256": "<hash>"}}
    ],
    "predicateType": "https://kairo.phantom/legal-v3/v1",
    "predicate": { <full legal-v3 bundle> }
  }
"""
from __future__ import annotations

import base64
import binascii
import json
import math
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

PAYLOAD_TYPE = "application/vnd.kairo.legal-v3.bundle+json"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://kairo.phantom/legal-v3/v1"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(s: str) -> bytes:
    if not isinstance(s, str):
        raise ValueError("base64 value must be a string")
    try:
        decoded = base64.b64decode(s, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("invalid base64 encoding") from exc
    if _b64(decoded) != s:
        raise ValueError("non-canonical base64 encoding")
    return decoded


def pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE v1 pre-authentication encoding; lengths count UTF-8 bytes."""
    if not isinstance(payload_type, str) or not isinstance(payload, bytes):
        raise ValueError("PAE requires a string type and byte payload")
    type_bytes = payload_type.encode("utf-8")
    return (b"DSSEv1 " + str(len(type_bytes)).encode("ascii") + b" "
            + type_bytes + b" " + str(len(payload)).encode("ascii")
            + b" " + payload)


def create_statement(bundle: dict[str, Any]) -> dict[str, Any]:
    """Create an in-toto v1 Statement wrapping a legal-v3 bundle.

    The bundle's output artifact becomes the Statement subject, and the
    full bundle is embedded as the predicate.
    """
    output_name = bundle.get("proposal", {}).get("output", "output.docx")
    # Output hash is in the ARTIFACT_READBACK event payload (event index 6)
    events = bundle.get("events", [])
    output_sha = ""
    for ev in events:
        if ev.get("event_type") == "ARTIFACT_READBACK":
            output_sha = ev.get("payload", {}).get("output_sha256", "")
            break

    # Also include source and playbook as subjects
    subjects = []
    if output_sha:
        subjects.append(
            {"name": output_name, "digest": {"sha256": output_sha}}
        )
    source_name = bundle.get("proposal", {}).get("source", "source.docx")
    source_sha = bundle.get("proposal", {}).get("source_sha256", "")
    if source_sha:
        subjects.append(
            {"name": source_name, "digest": {"sha256": source_sha}}
        )

    return {
        "_type": STATEMENT_TYPE,
        "subject": subjects,
        "predicateType": PREDICATE_TYPE,
        "predicate": bundle,
    }


def create_envelope(
    bundle: dict[str, Any],
    signatures: list[dict[str, str]],
) -> dict[str, Any]:
    """Create a DSSE envelope wrapping an in-toto Statement.

    *signatures* must sign pae(PAYLOAD_TYPE, decoded_payload), not an event
    or the raw statement. This function only serializes; it authenticates
    nothing. Pass [] explicitly to serialize an unsigned envelope.
    """
    statement = create_statement(bundle)
    payload_bytes = json.dumps(
        statement, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False
    ).encode("utf-8")

    return {
        "payload": _b64(payload_bytes),
        "payloadType": PAYLOAD_TYPE,
        "signatures": signatures,
    }


def _parse_envelope(envelope: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
    if not isinstance(envelope, dict):
        raise ValueError("DSSE envelope must be an object")
    for field in ("payload", "payloadType", "signatures"):
        if field not in envelope:
            raise ValueError(f"DSSE envelope missing '{field}'")
    if envelope["payloadType"] != PAYLOAD_TYPE:
        raise ValueError("unexpected payloadType")
    signatures = envelope["signatures"]
    if not isinstance(signatures, list):
        raise ValueError("signatures must be a list")
    for entry in signatures:
        if not isinstance(entry, dict):
            raise ValueError("signature entry must be an object")
        if not isinstance(entry.get("keyid"), str) or not entry["keyid"]:
            raise ValueError("signature requires a nonempty keyid")
        if not _b64d(entry.get("sig")):
            raise ValueError("signature must not be empty")
    payload = _b64d(envelope["payload"])

    def unique_object(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("duplicate JSON member")
            obj[key] = value
        return obj

    def invalid_constant(value):
        raise ValueError("non-finite JSON constant")

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("non-finite JSON number")
        return number

    try:
        statement = json.loads(payload.decode("utf-8"),
                               object_pairs_hook=unique_object,
                               parse_constant=invalid_constant,
                               parse_float=finite_float)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("invalid UTF-8 statement JSON") from exc
    if not isinstance(statement, dict):
        raise ValueError("statement must be an object")
    if statement.get("_type") != STATEMENT_TYPE:
        raise ValueError("unexpected statement type")
    if statement.get("predicateType") != PREDICATE_TYPE:
        raise ValueError("unexpected predicateType")
    if not isinstance(statement.get("predicate"), dict):
        raise ValueError("statement predicate must be an object")
    if not isinstance(statement.get("subject"), list):
        raise ValueError("statement subject must be a list")
    for subject in statement["subject"]:
        if (not isinstance(subject, dict)
                or not isinstance(subject.get("name"), str)
                or not isinstance(subject.get("digest"), dict)
                or not subject["digest"]
                or not all(isinstance(k, str) and isinstance(v, str)
                           for k, v in subject["digest"].items())):
            raise ValueError("invalid statement subject")
    return statement, payload


def parse_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    """Validate structure and decode an UNAUTHENTICATED statement.

    Empty signatures are allowed here, never by verify_envelope. No bundle
    semantics, artifact digests, or cryptographic signatures are verified.
    """
    return _parse_envelope(envelope)[0]


def verify_envelope(
    envelope: dict[str, Any],
    verify_signature_fn: Callable[[bytes, str, str], bool] | None = None,
    *,
    public_keys: Mapping[str, Ed25519PublicKey | bytes | str] | None = None,
    threshold: int = 1,
) -> dict[str, Any]:
    """Authenticate the exact DSSE PAE bytes, then return the statement.

    Supply exactly one trust source, independent of envelope/bundle contents:
    a callback (pae_bytes, signature_b64, key_id) -> literal True for a valid
    signature by a trusted identity, OR a keyid-to-Ed25519-public-key mapping
    (key objects, raw 32-byte keys, or canonical base64 keys).

    threshold counts distinct authenticated keys (default one). Callback
    callers must enforce a one-to-one keyid/identity mapping; aliases must not
    represent the same key. Public-key mode deduplicates actual key material.
    Unknown/invalid signatures do not count; malformed envelopes always fail.
    No event signature, bundled key, or serialization is implicitly trusted.
    """
    if type(threshold) is not int or threshold < 1:
        raise ValueError("threshold must be a positive integer")
    if (verify_signature_fn is None) == (public_keys is None):
        raise ValueError("provide exactly one trusted verifier or public_keys")
    if verify_signature_fn is not None and not callable(verify_signature_fn):
        raise ValueError("trusted verifier must be callable")
    trusted = {}
    if public_keys is not None:
        if not isinstance(public_keys, Mapping):
            raise ValueError("public_keys must be a mapping")
        for keyid, key in public_keys.items():
            if not isinstance(keyid, str) or not keyid:
                raise ValueError("trusted keyid must be a nonempty string")
            if isinstance(key, str):
                key = _b64d(key)
            if isinstance(key, bytes):
                key = Ed25519PublicKey.from_public_bytes(key)
            if not isinstance(key, Ed25519PublicKey):
                raise ValueError("trusted key must be an Ed25519 public key")
            trusted[keyid] = key
    statement, payload = _parse_envelope(envelope)
    if not envelope["signatures"]:
        raise ValueError("authentication requires signatures")
    message = pae(envelope["payloadType"], payload)
    verified = set()
    for entry in envelope["signatures"]:
        keyid, sig = entry["keyid"], entry["sig"]
        if verify_signature_fn is not None:
            try:
                valid = verify_signature_fn(message, sig, keyid) is True
            except Exception as exc:
                raise ValueError("trusted verifier failed") from exc
            if valid:
                verified.add(keyid)
        elif keyid in trusted:
            key = trusted[keyid]
            try:
                key.verify(_b64d(sig), message)
            except InvalidSignature:
                continue
            verified.add(key.public_bytes(serialization.Encoding.Raw,
                                          serialization.PublicFormat.Raw))
    if len(verified) < threshold:
        raise ValueError("signature authentication threshold not met")
    return statement


def wrap_bundle(
    bundle_path: str,
    output_path: str | None = None,
    signatures: list[dict[str, str]] | None = None,
) -> str:
    """Convenience: load a bundle from disk, wrap in DSSE, write to disk.

    Supply PAE signatures explicitly, or [] for unsigned serialization.
    Event signatures are never copied: they do not sign this statement.
    Writing an envelope does not authenticate it. Returns its file path.
    """
    bp = Path(bundle_path)
    bundle = json.loads((bp / "bundle.json").read_text(encoding="utf-8"))

    if signatures is None:
        raise ValueError("supply DSSE PAE signatures, or [] for unsigned serialization")

    envelope = create_envelope(bundle, signatures)

    if output_path is None:
        output_path = str(bp / "bundle.dsse.json")

    Path(output_path).write_text(
        json.dumps(envelope, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return output_path
