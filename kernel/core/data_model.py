"""
Kairo Phantom — Data Model (SPEC §S2)

Immutable dataclasses for the MemoryStore graph.
All types are frozen and use proper validation.

The kernel imports NOTHING from /domains or /legacy.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _gen_id() -> str:
    """Generate a unique ID."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class ExtractionStatus(enum.Enum):
    SUGGESTED = "suggested"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    PENDING_REVIEW = "pending_review"


class GroundingMethod(enum.Enum):
    """How a value was grounded to source text (SPEC §S3 cascade)."""
    EXACT = "exact"
    FUZZY = "fuzzy"
    SEMANTIC = "semantic"
    VISUAL = "visual"  # IoU ≥ 0.5 on stored geometry
    BLOCK = "block"  # none of the above passed → value is blocked


class ActionKind(enum.Enum):
    READ = "read"
    SUGGEST = "suggest"


class ActionStatus(enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    APPLIED = "applied"
    REJECTED = "rejected"
    REFUSED = "refused"  # out-of-allowlist


class ClassificationMarking(enum.Enum):
    UNCLASSIFIED = "UNCLASSIFIED"
    CONFIDENTIAL = "CONFIDENTIAL"
    SECRET = "SECRET"
    TOP_SECRET = "TOP_SECRET"


# ---------------------------------------------------------------------------
# Core Graph Nodes (§S2)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BBox:
    """Bounding box coordinates for source localization."""
    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        if self.x0 > self.x1 or self.y0 > self.y1:
            raise ValueError(
                f"Invalid bbox: ({self.x0},{self.y0}) to ({self.x1},{self.y1})"
            )


@dataclass(frozen=True)
class Document:
    """A source document ingested into the system."""
    doc_id: str = field(default_factory=_gen_id)
    source_path: str = ""
    sha256: str = ""
    page_count: int = 0
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Page:
    """A page from a Document."""
    doc_id: str
    index: int  # 1-indexed
    width_px: int
    height_px: int
    image_sha256: str = ""


@dataclass(frozen=True)
class Chunk:
    """A piece of a document with source localization.
    INVARIANT: page and bbox are NEVER None after ingestion."""
    chunk_id: str = field(default_factory=_gen_id)
    doc_id: str = ""
    page: int = 0  # 1-indexed
    bbox: BBox | None = None
    text: str = ""
    source_type: str = ""  # e.g., "text", "table", "image_ocr"
    embedding: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.page < 0:
            raise ValueError(f"page must be >= 0, got {self.page}")


@dataclass(frozen=True)
class Entity:
    """A named entity extracted from chunks."""
    entity_id: str = field(default_factory=_gen_id)
    kind: str = ""  # person, org, location, equipment
    value: str = ""
    normalized: str = ""


@dataclass(frozen=True)
class ModelVersion:
    """Tracks which model version produced an extraction."""
    model_id: str = field(default_factory=_gen_id)
    name: str = ""
    weights_hash: str = ""
    tier: int = 1  # 1=local, 3=cloud


@dataclass(frozen=True)
class Anchor:
    """A grounding anchor linking a value to a specific location in the source.
    SPEC §S3: the bbox stored at index time is the auditable record."""
    chunk_id: str = ""
    char_span: tuple[int, int] = (0, 0)  # start, end offsets within chunk text
    page: int = 0
    bbox: BBox | None = None


@dataclass(frozen=True)
class Extraction:
    """A field value extracted by a Pack.
    Links to the source Chunk for provenance.
    RULE: an Extraction with zero anchors is blocked and never rendered as fact."""
    ext_id: str = field(default_factory=_gen_id)
    pack_id: str = ""
    field_name: str = ""
    value: str = ""
    source_span: str = ""  # exact text from source (LangExtract pattern)
    confidence: float = 0.0
    model_version: str = ""
    status: ExtractionStatus = ExtractionStatus.SUGGESTED
    chunk_id: str = ""  # Links to Chunk for provenance chain
    method: GroundingMethod = GroundingMethod.BLOCK  # default blocked until grounded
    anchors: tuple[Anchor, ...] = ()  # grounding anchors


@dataclass(frozen=True)
class Correction:
    """A human correction to an extraction (flywheel input)."""
    corr_id: str = field(default_factory=_gen_id)
    ext_id: str = ""
    original: str = ""
    corrected: str = ""
    reason: str = ""
    by: str = ""  # user_id
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Action:
    """A CUA action: READ or SUGGEST only.
    Never autonomous writes without human confirmation."""
    action_id: str = field(default_factory=_gen_id)
    ext_id: str = ""
    kind: ActionKind = ActionKind.SUGGEST
    target_app: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    status: ActionStatus = ActionStatus.PENDING


@dataclass(frozen=True)
class User:
    """A user of the system."""
    user_id: str = field(default_factory=_gen_id)


# ---------------------------------------------------------------------------
# Provenance Chain (§S3)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Chain:
    """Complete provenance chain: Action → Extraction → Chunk → Document.
    RULE: nothing is suggested without a complete, resolvable chain.
    """
    action: Action | None = None
    extraction: Extraction | None = None
    chunk: Chunk | None = None
    document: Document | None = None

    @property
    def is_complete(self) -> bool:
        """A chain is complete if all 4 nodes are present and linked."""
        if self.document is None or self.chunk is None:
            return False
        if self.extraction is None:
            return False
        if self.chunk.doc_id != self.document.doc_id:
            return False
        if self.extraction.chunk_id != self.chunk.chunk_id:
            return False
        return self.chunk.bbox is not None


# ---------------------------------------------------------------------------
# Orchestrator Trace (§S4)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TraceStage:
    """One stage of the orchestrator pipeline with non-empty IO."""
    name: str
    input_data: Any = None
    output_data: Any = None
    duration_ms: float = 0.0
    status: str = "ok"  # "ok", "halted", "blocked"


@dataclass(frozen=True)
class Trace:
    """Ordered trace of the full orchestrator pipeline.
    Every stage has non-empty IO."""
    stages: tuple[TraceStage, ...] = ()
    halted: bool = False
    halt_reason: str = ""
    extractions: tuple[Extraction, ...] = ()

    @property
    def is_complete(self) -> bool:
        return len(self.stages) > 0 and all(
            s.input_data is not None and s.output_data is not None
            for s in self.stages
        )


# ---------------------------------------------------------------------------
# Answer (Q&A with grounded citations — SPEC §S2)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Answer:
    """A grounded answer to a query.
    RULE: grounded=True only if ALL citations resolve.
    If the query cannot be answered from the source, text is a refusal."""
    answer_id: str = field(default_factory=_gen_id)
    query: str = ""
    text: str = ""
    citations: tuple[Anchor, ...] = ()
    grounded: bool = False
    refused: bool = False  # True when Kairo declined to answer
    refusal_stage: str = ""  # which cascade stage blocked (e.g. "BLOCK", "FUZZY")
    refusal_reason: str = ""  # human-readable explanation of why it was blocked
    refusal_suggestion: str = ""  # actionable suggestion for the user


# ---------------------------------------------------------------------------
# Suggestion (ActionExecutor output)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Suggestion:
    """A suggested action with provenance and confidence.
    NOT auto-applied — requires human confirmation."""
    action: Action
    provenance: Chain
    confidence: float = 0.0
    display_text: str = ""
