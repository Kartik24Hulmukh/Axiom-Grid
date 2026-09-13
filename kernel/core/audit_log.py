"""
Kairo Phantom — Signed Audit Log (X1: compliance infrastructure)

Tamper-evident, cryptographically signed log entries for every answer AND
every refusal. Each entry contains: question, document hash, the exact
grounded source region (or the cascade stage that blocked), model id,
timestamp, and an HMAC-SHA256 signature.

The log forms a hash chain: each entry's signature covers its own content
plus the previous entry's signature. Modifying any entry invalidates the
chain from that point forward — tamper-evident by construction.

This is the Contract/Compliance Pack's headline feature: a regulator-
acceptable record of exactly what the AI cited and exactly what it refused
to answer and why.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from kernel.core.data_model import Answer, Anchor

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuditEntry:
    """A single tamper-evident audit log entry.

    Fields:
        entry_id:       Unique identifier for this entry.
        timestamp:      ISO-8601 UTC timestamp.
        question:       The user's question.
        document_hash:  SHA-256 of the source document content.
        outcome:        'answer' or 'refusal'.
        grounded:       True if the answer was grounded to source.
        source_region:  For answers: the exact bbox/char_span cited.
                        For refusals: empty.
        cascade_stage:  For refusals: the cascade stage that blocked
                        (e.g. 'BLOCK'). For answers: the method used
                        (e.g. 'EXACT', 'FUZZY', 'SEMANTIC').
        model_id:       Identifier of the model that produced the answer.
        signature:      HMAC-SHA256 over (content + prev_signature).
        prev_signature: Signature of the previous entry in the chain
                        (empty string for the genesis entry).
    """
    entry_id: str
    timestamp: str
    question: str
    document_hash: str
    outcome: str  # 'answer' or 'refusal'
    grounded: bool
    source_region: dict[str, Any]
    cascade_stage: str
    model_id: str
    signature: str = ""
    prev_signature: str = ""

    def content_bytes(self) -> bytes:
        """Return the canonical bytes that are signed (excludes signature fields)."""
        payload = {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "question": self.question,
            "document_hash": self.document_hash,
            "outcome": self.outcome,
            "grounded": self.grounded,
            "source_region": self.source_region,
            "cascade_stage": self.cascade_stage,
            "model_id": self.model_id,
            "prev_signature": self.prev_signature,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


class SignedAuditLog:
    """Tamper-evident audit log using HMAC-SHA256 hash chaining.

    Every answer and every refusal produces a log entry. Entries are
    chained: each entry's signature covers its content plus the previous
    entry's signature. Tampering with any entry breaks the chain.

    Usage:
        log = SignedAuditLog(session_key=b"my-secret-key")
        log.log_answer(answer, document_hash="abc...", model_id="ollama-llama3")
        log.log_refusal(question="What is X?", document_hash="abc...",
                        cascade_stage="BLOCK", model_id="ollama-llama3")
        assert log.verify_chain()  # True if untampered
    """

    def __init__(self, session_key: bytes) -> None:
        if not session_key:
            raise ValueError("session_key must not be empty")
        self._session_key = session_key
        self._entries: list[AuditEntry] = []
        self._last_signature: str = ""

    def _sign(self, content: bytes) -> str:
        """Compute HMAC-SHA256 signature over content."""
        return hmac.new(self._session_key, content, hashlib.sha256).hexdigest()

    def _anchor_to_region(self, anchor: Anchor) -> dict[str, Any]:
        """Convert an Anchor to a serializable source region dict."""
        region: dict[str, Any] = {
            "chunk_id": anchor.chunk_id,
            "char_span": list(anchor.char_span),
            "page": anchor.page,
        }
        if anchor.bbox is not None:
            region["bbox"] = {
                "x0": anchor.bbox.x0,
                "y0": anchor.bbox.y0,
                "x1": anchor.bbox.x1,
                "y1": anchor.bbox.y1,
            }
        return region

    def log_answer(
        self,
        answer: Answer,
        document_hash: str,
        model_id: str,
        cascade_stage: str = "",
    ) -> AuditEntry:
        """Log a grounded answer. Every answer produces an entry.

        Args:
            answer:         The Answer object (with citations).
            document_hash:  SHA-256 hash of the source document.
            model_id:       Model that produced the answer.
            cascade_stage:  Grounding method used (e.g. 'EXACT').
                            Auto-detected from answer.grounded if empty.
        """
        if not cascade_stage:
            cascade_stage = "EXACT" if answer.grounded else "BLOCK"

        source_region: dict[str, Any] = {}
        if answer.citations:
            source_region = self._anchor_to_region(answer.citations[0])
            if len(answer.citations) > 1:
                source_region["additional_citations"] = [
                    self._anchor_to_region(a) for a in answer.citations[1:]
                ]

        entry = AuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            question=answer.query,
            document_hash=document_hash,
            outcome="answer",
            grounded=answer.grounded,
            source_region=source_region,
            cascade_stage=cascade_stage,
            model_id=model_id,
            prev_signature=self._last_signature,
        )
        signature = self._sign(entry.content_bytes())
        # frozen dataclass — use object.__setattr__ to set signature
        object.__setattr__(entry, "signature", signature)
        self._entries.append(entry)
        self._last_signature = signature
        logger.debug("Audit log: answer entry %s for query '%s'", entry.entry_id, answer.query[:50])
        return entry

    def log_refusal(
        self,
        question: str,
        document_hash: str,
        cascade_stage: str,
        model_id: str,
    ) -> AuditEntry:
        """Log a refusal. Every refusal produces an entry.

        Args:
            question:       The question that was refused.
            document_hash:  SHA-256 hash of the source document.
            cascade_stage:  The cascade stage that blocked (e.g. 'BLOCK').
            model_id:       Model that attempted the answer.
        """
        entry = AuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            question=question,
            document_hash=document_hash,
            outcome="refusal",
            grounded=False,
            source_region={},
            cascade_stage=cascade_stage,
            model_id=model_id,
            prev_signature=self._last_signature,
        )
        signature = self._sign(entry.content_bytes())
        object.__setattr__(entry, "signature", signature)
        self._entries.append(entry)
        self._last_signature = signature
        logger.debug("Audit log: refusal entry %s for query '%s'", entry.entry_id, question[:50])
        return entry

    @property
    def entries(self) -> list[AuditEntry]:
        """Return all log entries (read-only view)."""
        return list(self._entries)

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def verify_entry(self, entry: AuditEntry) -> bool:
        """Verify a single entry's signature against the session key."""
        expected = self._sign(entry.content_bytes())
        return hmac.compare_digest(entry.signature, expected)

    def verify_chain(self) -> bool:
        """Verify the entire hash chain: every signature is valid AND
        every prev_signature links correctly.

        Returns True only if the chain is completely untampered.
        """
        expected_prev = ""
        for entry in self._entries:
            # Check signature is valid
            if not self.verify_entry(entry):
                logger.warning("Chain broken: invalid signature on entry %s", entry.entry_id)
                return False
            # Check chain linkage
            if entry.prev_signature != expected_prev:
                logger.warning("Chain broken: prev_signature mismatch on entry %s", entry.entry_id)
                return False
            expected_prev = entry.signature
        return True

    def verify_chain_with_key(self, session_key: bytes) -> bool:
        """Verify the chain using a different key (should fail if key differs)."""
        expected_prev = ""
        for entry in self._entries:
            expected_sig = hmac.new(
                session_key, entry.content_bytes(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(entry.signature, expected_sig):
                return False
            if entry.prev_signature != expected_prev:
                return False
            expected_prev = entry.signature
        return True

    def to_json(self) -> str:
        """Serialize the entire log to JSON."""
        entries = []
        for e in self._entries:
            entries.append({
                "entry_id": e.entry_id,
                "timestamp": e.timestamp,
                "question": e.question,
                "document_hash": e.document_hash,
                "outcome": e.outcome,
                "grounded": e.grounded,
                "source_region": e.source_region,
                "cascade_stage": e.cascade_stage,
                "model_id": e.model_id,
                "signature": e.signature,
                "prev_signature": e.prev_signature,
            })
        return json.dumps({"entries": entries}, indent=2)

    @classmethod
    def from_json(cls, data: str, session_key: bytes) -> "SignedAuditLog":
        """Reconstruct a SignedAuditLog from JSON. Raises if chain is broken."""
        obj = json.loads(data)
        log = cls(session_key)
        for e_dict in obj["entries"]:
            entry = AuditEntry(
                entry_id=e_dict["entry_id"],
                timestamp=e_dict["timestamp"],
                question=e_dict["question"],
                document_hash=e_dict["document_hash"],
                outcome=e_dict["outcome"],
                grounded=e_dict["grounded"],
                source_region=e_dict["source_region"],
                cascade_stage=e_dict["cascade_stage"],
                model_id=e_dict["model_id"],
                signature=e_dict["signature"],
                prev_signature=e_dict["prev_signature"],
            )
            log._entries.append(entry)
            log._last_signature = entry.signature
        if not log.verify_chain():
            raise ValueError("Loaded audit log chain is broken (tampered)")
        return log