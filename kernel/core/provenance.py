"""
Kairo Phantom — ProvenanceLog (SPEC §S3)

Implements the provenance chain: Action → Extraction → Chunk → Document(page, bbox).
get_provenance(id) returns the complete chain — or the value is BLOCKED.

RULES:
- Nothing is suggested without a complete, resolvable chain.
- Provenance coverage on any demo/bench run = 100% (measured, in CI).

The kernel imports NOTHING from /domains or /legacy.
"""

from __future__ import annotations

import logging

from kernel.core.data_model import (
    Action,
    Chain,
    Chunk,
    Document,
    Extraction,
)

logger = logging.getLogger(__name__)


class ProvenanceLogImpl:
    """Concrete ProvenanceLog implementation.

    Maintains an in-memory registry of all graph nodes and resolves
    provenance chains on demand. Chains are verified for completeness
    before any value is allowed to be suggested.
    """

    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}
        self._chunks: dict[str, Chunk] = {}
        self._extractions: dict[str, Extraction] = {}
        self._actions: dict[str, Action] = {}

    # ---- Registration ----

    def register_document(self, doc: Document) -> None:
        """Register a document in the provenance graph."""
        self._documents[doc.doc_id] = doc

    def register_chunk(self, chunk: Chunk) -> None:
        """Register a chunk. INVARIANT: chunk.bbox must not be None."""
        if chunk.bbox is None:
            raise ValueError(
                f"Chunk {chunk.chunk_id} has no bbox — "
                "every chunk MUST have source localization"
            )
        self._chunks[chunk.chunk_id] = chunk

    def register_extraction(self, extraction: Extraction) -> None:
        """Register an extraction linked to a chunk."""
        self._extractions[extraction.ext_id] = extraction

    def register_action(self, action: Action) -> None:
        """Register a CUA action linked to an extraction."""
        self._actions[action.action_id] = action

    # ---- Chain Resolution ----

    def get_provenance(self, entity_id: str) -> Chain:
        """Resolve the full provenance chain for an entity ID.

        Attempts to find the entity as an Action, then Extraction,
        and walks the chain: Action → Extraction → Chunk → Document.

        Returns a Chain — check chain.is_complete to verify it's valid.
        An incomplete chain means the value should be BLOCKED.
        """
        action: Action | None = None
        extraction: Extraction | None = None
        chunk: Chunk | None = None
        document: Document | None = None

        # Try to resolve as an Action first
        if entity_id in self._actions:
            action = self._actions[entity_id]
            extraction = self._extractions.get(action.ext_id)
        elif entity_id in self._extractions:
            extraction = self._extractions[entity_id]
        else:
            logger.warning("Entity %s not found in provenance graph", entity_id)
            return Chain()

        # Walk the chain
        if extraction is not None:
            chunk = self._chunks.get(extraction.chunk_id)

        if chunk is not None:
            document = self._documents.get(chunk.doc_id)

        chain = Chain(
            action=action,
            extraction=extraction,
            chunk=chunk,
            document=document,
        )

        if not chain.is_complete:
            logger.warning(
                "Incomplete provenance chain for %s: "
                "action=%s, extraction=%s, chunk=%s, document=%s",
                entity_id,
                action is not None,
                extraction is not None,
                chunk is not None,
                document is not None,
            )

        return chain

    def verify_provenance_coverage(
        self, extractions: list[Extraction]
    ) -> tuple[float, list[str]]:
        """Verify provenance coverage for a set of extractions.

        Returns (coverage_pct, list_of_ungrounded_ext_ids).
        Coverage must be 100% for any demo/bench run.
        """
        if not extractions:
            return 100.0, []

        ungrounded: list[str] = []
        for ext in extractions:
            chain = self.get_provenance(ext.ext_id)
            if not chain.is_complete:
                ungrounded.append(ext.ext_id)

        total = len(extractions)
        grounded = total - len(ungrounded)
        coverage = (grounded / total) * 100.0

        return coverage, ungrounded

    # ---- Introspection ----

    @property
    def stats(self) -> dict[str, int]:
        return {
            "documents": len(self._documents),
            "chunks": len(self._chunks),
            "extractions": len(self._extractions),
            "actions": len(self._actions),
        }
