"""
Kairo Phantom — Frozen Contracts (SPEC §S4)

These 9 Protocol definitions are the coordination layer for all kernel modules.
Signatures are FROZEN: do not change without amending SPEC.md first.
Bodies are implemented in their respective modules under kernel/sidecar/ and packs/.

The kernel imports NOTHING from /domains or /legacy.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from kernel.core.data_model import (
    Action,
    Chain,
    Chunk,
    Correction,
    Document,
    Extraction,
    Suggestion,
    Trace,
    GroundingMethod,
    Anchor,
)


# ---------------------------------------------------------------------------
# 1. Ingestor — §S4 line 1
# ---------------------------------------------------------------------------
@runtime_checkable
class Ingestor(Protocol):
    """Ingest a document file and return Chunks, each with non-null page+bbox."""

    def ingest(self, path: str) -> list[Chunk]:
        """Every returned Chunk MUST have non-null page and bbox."""
        ...


# ---------------------------------------------------------------------------
# 2. MemoryStore — §S4 line 2
# ---------------------------------------------------------------------------
@runtime_checkable
class MemoryStore(Protocol):
    """Persistent store for documents, extractions, and corrections."""

    def upsert_document(self, doc: Document) -> None: ...

    def record_extraction(self, extraction: Extraction) -> None: ...

    def record_correction(self, correction: Correction) -> None: ...

    def search_similar_corrections(
        self, field_name: str, value: str, k: int = 5
    ) -> list[Correction]: ...


# ---------------------------------------------------------------------------
# 3. InferenceGateway — §S4 line 3
# ---------------------------------------------------------------------------
class InferenceTier(enum.IntEnum):
    """Tier1 = on-device (default), Tier3 = cloud (DEFAULT OFF)."""
    TIER1_LOCAL = 1
    TIER3_CLOUD = 3


@dataclass(frozen=True)
class InferenceResult:
    text: str
    call_id: str


@runtime_checkable
class InferenceGateway(Protocol):
    """Tiered inference with logging. Air-gap safe when Tier3 is off."""

    def complete(
        self,
        role: str,
        prompt: str,
        tier: InferenceTier = InferenceTier.TIER1_LOCAL,
    ) -> InferenceResult: ...


# ---------------------------------------------------------------------------
# 4. Orchestrator — §S4 line 4
# ---------------------------------------------------------------------------
@runtime_checkable
class Orchestrator(Protocol):
    """Runs the full pipeline: capture → security → intent → router →
    extractor → quality → suggest → (human_review terminal).
    Gates HALT and route to human_review — never annotate-and-continue.
    """

    def run(self, doc: Document) -> Trace: ...


# ---------------------------------------------------------------------------
# 5. SecurityFilter — §S4 line 5
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScanResult:
    blocked: bool
    reasons: list[str] = field(default_factory=list)


@runtime_checkable
class SecurityFilter(Protocol):
    """Scans text for prompt injection and PII. BLOCKS, never soft-warns."""

    def scan(self, text: str) -> ScanResult: ...


# ---------------------------------------------------------------------------
# 6. QualityGate — §S4 line 6
# ---------------------------------------------------------------------------
class GateVerdict(enum.Enum):
    PASS = "pass"
    FLAG = "flag"
    BLOCK = "block"


@dataclass(frozen=True)
class GateResult:
    verdict: GateVerdict
    calibrated_confidence: float
    reasons: list[str] = field(default_factory=list)


@runtime_checkable
class QualityGate(Protocol):
    """Checks extraction quality: grounding, corrections history,
    calibrated confidence. Routes low-confidence to human_review."""

    def check(self, extraction: Extraction) -> GateResult: ...


# ---------------------------------------------------------------------------
# 7. ProvenanceLog — §S4 line 7
# ---------------------------------------------------------------------------
@runtime_checkable
class ProvenanceLog(Protocol):
    """Provenance chain: Action → Extraction → Chunk → Document(page, bbox).
    get_provenance returns the complete chain or the value is BLOCKED."""

    def get_provenance(self, entity_id: str) -> Chain: ...


# ---------------------------------------------------------------------------
# 8. ActionExecutor — §S4 line 8 (READ+SUGGEST ONLY)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ApplyResult:
    success: bool
    post_state: Any = None
    error: str | None = None


@runtime_checkable
class ActionExecutor(Protocol):
    """CUA: READ+SUGGEST only. Never writes autonomously.
    apply() requires human_confirm=True and re-reads field to verify post-state.
    """

    def suggest(self, action: Action) -> Suggestion: ...

    def apply(
        self, action: Action, human_confirm: bool = True
    ) -> ApplyResult: ...


# ---------------------------------------------------------------------------
# 8.5. GroundingVerifier — SPEC §S3
# ---------------------------------------------------------------------------
@runtime_checkable
class GroundingVerifier(Protocol):
    """Deterministic grounding verifier (SPEC §S3 cascade)."""

    def verify(
        self, value: str, source_span: str, chunks: list[Chunk]
    ) -> tuple[GroundingMethod, tuple[Anchor, ...]]: ...


# ---------------------------------------------------------------------------
# 9. PackInterface — §S4 line 9, §S7
# ---------------------------------------------------------------------------
@runtime_checkable
class PackInterface(Protocol):
    """Domain-specific extraction pack.
    The kernel is domain-agnostic; all vertical logic lives behind this interface.
    """

    @property
    def fields(self) -> list[str]:
        """List of field names this Pack extracts."""
        ...

    def extract(self, chunks: list[Chunk]) -> list[Extraction]:
        """Extract domain-specific fields from ingested chunks."""
        ...

    def oracle(self, fixtures_dir: str) -> dict[str, float]:
        """Score per-field accuracy vs ground-truth fixtures.
        Returns {field_name: accuracy} — reported honestly, even if low."""
        ...
