"""
Kairo Phantom — Reproducibility Receipt (X3: determinism guarantee)

Generates a receipt: corpus hash + model id + result hash. The user can
re-verify by re-running with the same inputs and comparing receipts.

Pins seeds/model versions in the receipt. Asserts byte-identical
answers/refusals across runs.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from kernel.core.data_model import Answer


@dataclass(frozen=True)
class ReproducibilityReceipt:
    """A receipt that proves a run is reproducible.

    Fields:
        receipt_id:      Unique identifier.
        created_at:      ISO-8601 UTC timestamp.
        corpus_hash:     SHA-256 over all input document texts (sorted).
        model_id:        Model identifier used for the run.
        model_version:   Pinned model version / weights hash.
        seed:            Random seed pinned for the run.
        result_hash:     SHA-256 over all answer/refusal outputs (canonical).
        answer_count:    Number of answers in the run.
        refusal_count:   Number of refusals in the run.
        config_hash:     SHA-256 over run configuration (thresholds, etc).
    """
    receipt_id: str
    created_at: str
    corpus_hash: str
    model_id: str
    model_version: str
    seed: int
    result_hash: str
    answer_count: int
    refusal_count: int
    config_hash: str

    def to_json(self) -> str:
        """Serialize receipt to canonical JSON (sorted keys for determinism)."""
        return json.dumps({
            "receipt_id": self.receipt_id,
            "created_at": self.created_at,
            "corpus_hash": self.corpus_hash,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "seed": self.seed,
            "result_hash": self.result_hash,
            "answer_count": self.answer_count,
            "refusal_count": self.refusal_count,
            "config_hash": self.config_hash,
        }, sort_keys=True, indent=2)

    def verify(self, corpus_hash: str, result_hash: str, model_id: str,
               model_version: str, seed: int, config_hash: str) -> bool:
        """Verify that the given parameters match this receipt.

        Returns True only if ALL fields match exactly.
        """
        return (
            self.corpus_hash == corpus_hash
            and self.result_hash == result_hash
            and self.model_id == model_id
            and self.model_version == model_version
            and self.seed == seed
            and self.config_hash == config_hash
        )


class ReproducibilityReceiptBuilder:
    """Builds reproducibility receipts for a run.

    Usage:
        builder = ReproducibilityReceiptBuilder(
            model_id="ollama-llama3",
            model_version="v8b-Q4_K_M",
            seed=42,
            config={"fuzzy_threshold": 0.92, "semantic_threshold": 0.86},
        )
        receipt = builder.build(corpus_texts=[...], answers=[...], refusals=[...])
        # Later: re-run with same inputs, compare receipts
    """

    def __init__(
        self,
        model_id: str,
        model_version: str,
        seed: int = 42,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.model_id = model_id
        self.model_version = model_version
        self.seed = seed
        self.config = config or {}

    @staticmethod
    def _hash_corpus(corpus_texts: list[str]) -> str:
        """Compute SHA-256 over sorted corpus texts for deterministic hashing."""
        sorted_texts = sorted(corpus_texts)
        combined = "\n".join(sorted_texts)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    @staticmethod
    def _hash_config(config: dict[str, Any]) -> str:
        """Compute SHA-256 over canonical JSON of config."""
        canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _canonical_answer(answer: Answer) -> dict[str, Any]:
        """Convert an Answer to a canonical dict for hashing."""
        citations = []
        for c in answer.citations:
            cit = {
                "chunk_id": c.chunk_id,
                "char_span": list(c.char_span),
                "page": c.page,
            }
            if c.bbox is not None:
                cit["bbox"] = [c.bbox.x0, c.bbox.y0, c.bbox.x1, c.bbox.y1]
            citations.append(cit)
        return {
            "query": answer.query,
            "text": answer.text,
            "grounded": answer.grounded,
            "refused": answer.refused,
            "citations": citations,
        }

    @staticmethod
    def _hash_results(answers: list[Answer], refusals: list[str]) -> str:
        """Compute SHA-256 over canonical representation of all outputs.

        Answers are sorted by query for determinism. Refusals are sorted
        alphabetically.
        """
        canonical_answers = [
            ReproducibilityReceiptBuilder._canonical_answer(a) for a in answers
        ]
        # Sort by query for deterministic ordering
        canonical_answers.sort(key=lambda x: x["query"])
        sorted_refusals = sorted(refusals)

        payload = {
            "answers": canonical_answers,
            "refusals": sorted_refusals,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def build(
        self,
        corpus_texts: list[str],
        answers: list[Answer],
        refusals: list[str],
    ) -> ReproducibilityReceipt:
        """Build a reproducibility receipt for this run.

        Args:
            corpus_texts:  List of document texts that form the input corpus.
            answers:       List of Answer objects produced by the run.
            refusals:      List of refused questions (strings).

        Returns:
            A ReproducibilityReceipt that can be saved and compared later.
        """
        import uuid

        corpus_hash = self._hash_corpus(corpus_texts)
        result_hash = self._hash_results(answers, refusals)
        config_hash = self._hash_config(self.config)

        return ReproducibilityReceipt(
            receipt_id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            corpus_hash=corpus_hash,
            model_id=self.model_id,
            model_version=self.model_version,
            seed=self.seed,
            result_hash=result_hash,
            answer_count=len(answers),
            refusal_count=len(refusals),
            config_hash=config_hash,
        )

    def pin_seed(self) -> int:
        """Pin and return the random seed for this run."""
        random.seed(self.seed)
        return self.seed


def compare_receipts(r1: ReproducibilityReceipt, r2: ReproducibilityReceipt) -> dict[str, bool]:
    """Compare two receipts field by field.

    Returns a dict mapping field names to whether they match.
    A fully reproducible run has all fields True (except receipt_id and
    created_at which are expected to differ).
    """
    fields_to_compare = [
        "corpus_hash", "model_id", "model_version", "seed",
        "result_hash", "answer_count", "refusal_count", "config_hash",
    ]
    result = {}
    for f in fields_to_compare:
        result[f] = getattr(r1, f) == getattr(r2, f)
    return result


def assert_byte_identical(
    r1: ReproducibilityReceipt, r2: ReproducibilityReceipt
) -> None:
    """Assert that two receipts are byte-identical in all meaningful fields.

    Raises AssertionError with details if any field differs.
    receipt_id and created_at are allowed to differ (they are per-run metadata).
    """
    comparison = compare_receipts(r1, r2)
    mismatches = [f for f, match in comparison.items() if not match]
    if mismatches:
        details = []
        for f in mismatches:
            details.append(f"  {f}: {getattr(r1, f)!r} != {getattr(r2, f)!r}")
        raise AssertionError(
            "Receipts are not byte-identical. Mismatched fields:\n" + "\n".join(details)
        )