"""OpenBot receipt adapter — emit Axiom-Grid signed receipts for OpenBot agent actions.

Implements the integration surface of the Open Agent Receipt Specification
(specs/open-agent-receipt-spec-v0.1.md) for OpenBot:
every OpenBot bot action is recorded into an Ed25519-signed, hash-chained
audit log that `axiom verify` (and any third-party verifier) can validate.

The adapter is a thin wrapper over the native `kairo.oracles.ed25519_audit_log`
module — no re-implementation, no mocks. It only adapts OpenBot's action model
(read / suggest / write / export) to the audit-log primitives.

Usage in an OpenBot sidecar or supervisor:

    from integrations.openbot.adapter import OpenBotReceiptAdapter

    adapter = OpenBotReceiptAdapter(agent_id="my-bot")
    adapter.log_run_started(doc_hash=doc_hash, playbook_id="openbot-session")
    adapter.log_action(action="read", doc_hash=doc_hash,
                       summary={"url": url, "citations": [{"page": 1, "line": 4}]})
    adapter.export("receipts.jsonl")
    assert adapter.verify()  # chain validates with the adapter's public key
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from kairo.oracles.ed25519_audit_log import (  # noqa: E402
    AuditEntry,
    Ed25519AuditLog,
)


class OpenBotReceiptAdapter:
    """Adapt OpenBot agent actions into the Axiom-Grid signed-receipt chain."""

    def __init__(self, agent_id: str, key_path: str | Path = ".keys/openbot_ed25519.pem") -> None:
        self.agent_id = agent_id
        self.key_path = Path(key_path)
        self.key_path.parent.mkdir(parents=True, exist_ok=True)

        if self.key_path.exists():
            priv = self._load_key()
        else:
            priv, pub = Ed25519AuditLog.generate_keypair()
            self._save_keypair(priv, pub)

        self.log = Ed25519AuditLog(priv)
        self._entries: list[AuditEntry] = []

    # -- key management ----------------------------------------------------

    def _load_key(self):
        from cryptography.hazmat.primitives import serialization

        data = self.key_path.read_bytes()
        return Ed25519AuditLog.load_private_key(data)

    def _save_keypair(self, priv, pub) -> None:
        from cryptography.hazmat.primitives import serialization

        self.key_path.write_bytes(
            priv.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        pub_path = self.key_path.with_suffix(".pub.pem")
        pub_path.write_bytes(
            pub.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )

    # -- OpenBot action surface -------------------------------------------

    def log_run_started(self, doc_hash: str, playbook_id: str = "openbot-session") -> AuditEntry:
        entry = self.log.log_run_started(doc_hash=doc_hash, playbook_id=playbook_id)
        self._entries.append(entry)
        return entry

    def log_action(self, action: str, doc_hash: str, summary: dict | None = None) -> AuditEntry:
        """Record one OpenBot action (read/suggest/write/export) as a signed entry.

        `summary` carries grounding citations (page/line) per the Open Receipt
        Specification so receipts remain verifiable against source documents.
        """
        entry = self.log._make_entry(
            action=f"agent_{action}",
            doc_hash=doc_hash,
            edit_summary=summary or {},
        )
        self._entries.append(entry)
        return entry

    # -- receipt export / verification ------------------------------------

    def export(self, export_path: str | Path = "receipts.jsonl") -> Path:
        """Serialize the signed chain as JSONL (Open Receipt Spec v0.1 shape)."""
        out = Path(export_path)
        with out.open("w", encoding="utf-8") as f:
            # Native serialization of the whole signed chain (entries_from_json
            # round-trips exactly): third-party verifiers see the exact bytes
            # that were signed, per the Open Agent Receipt Specification.
            payload = json.loads(self.log.to_json())
            payload["version"] = 1
            payload["agent_id"] = self.agent_id
            json.dump(payload, f, indent=2)
        return out

    def verify(self, receipts_path: str | Path | None = None) -> bool:
        """Verify the chain with the adapter's own public key.

        When `receipts_path` is given, entries are re-loaded from the exported
        JSONL (simulating a third-party verifier) before chain verification.
        """
        if receipts_path is not None:
            data = Path(receipts_path).read_text(encoding="utf-8")
            self._entries = Ed25519AuditLog.entries_from_json(data)
        pub = self._load_public()
        return Ed25519AuditLog.verify_chain(
            entries=self._entries,
            public_key=pub,
        )

    def _load_public(self):
        pub_path = self.key_path.with_suffix(".pub.pem")
        return Ed25519AuditLog.load_public_key(pub_path.read_bytes())


def _cli() -> int:
    """Demo/verify CLI: emit a sample chain, then verify it."""
    import argparse

    ap = argparse.ArgumentParser(description="OpenBot receipt adapter")
    ap.add_argument("--emit", action="store_true", help="emit a demo receipt chain")
    ap.add_argument("--verify", metavar="RECEIPTS", help="verify an exported chain (requires --key)")
    ap.add_argument("--key", help="path to the adapter keypair PEM")
    args = ap.parse_args()

    base_key = args.key or ".keys/openbot_ed25519.pem"
    if args.emit:
        adapter = OpenBotReceiptAdapter(agent_id="demo-bot", key_path=base_key)
        adapter.log_run_started(doc_hash="abc123", playbook_id="demo")
        adapter.log_action("read", doc_hash="abc123", summary={"url": "https://example.com", "citations": [{"page": 1, "line": 4}]})
        adapter.log_action("suggest", doc_hash="abc123", summary={"citations": [{"page": 2, "line": 10}]})
        out = adapter.export("demo_receipts.jsonl")
        print(f"EMITTED {len(adapter._entries)} receipts -> {out}")
        return 0
    if args.verify:
        adapter = OpenBotReceiptAdapter(agent_id="demo-bot", key_path=base_key)
        ok = adapter.verify(args.verify)
        print("VERIFY: OK" if ok else "VERIFY: FAILED")
        return 0 if ok else 1
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli())
