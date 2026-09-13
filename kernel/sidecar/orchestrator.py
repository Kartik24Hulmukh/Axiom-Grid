"""
Kairo Phantom — Orchestrator State Machine (SPEC §S4)

Pipeline: context_capture → security_filter → intent_gate → router →
          extractor → quality_gate → suggest → (human_review terminal)

Gates HALT and route to human_review — never annotate-and-continue.
Returns an ordered Trace with non-empty stage IO.

The kernel imports NOTHING from /domains or /legacy.
"""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from typing import Any

from kernel.core.contracts import (
    GateVerdict,
    InferenceGateway,
    PackInterface,
    ProvenanceLog,
    QualityGate,
    SecurityFilter,
)
from kernel.core.data_model import (
    Document,
    Extraction,
    ExtractionStatus,
    Trace,
    TraceStage,
)

logger = logging.getLogger(__name__)


class OrchestratorImpl:
    """Concrete Orchestrator implementing the full pipeline.

    Every stage produces non-empty IO. Gates HALT the pipeline
    and route to human_review. Never annotate-and-continue.
    """

    def __init__(
        self,
        ingestor: Any,  # IngestorImpl
        security_filter: SecurityFilter,
        inference_gateway: InferenceGateway,
        quality_gate: QualityGate,
        provenance_log: ProvenanceLog,
        pack: PackInterface,
        memory_store: Any,  # MemoryStoreImpl
    ) -> None:
        self._ingestor = ingestor
        self._security = security_filter
        self._gateway = inference_gateway
        self._quality = quality_gate
        self._provenance = provenance_log
        self._pack = pack
        self._memory = memory_store

    def run(self, doc: Document) -> Trace:
        """Run the full orchestrator pipeline on a document.

        Returns an ordered Trace with non-empty stage IO.
        If a gate halts, the trace is marked halted with the reason.
        """
        stages: list[TraceStage] = []
        all_extractions: list[Extraction] = []
        halted = False
        halt_reason = ""

        # ---- Stage 1: Context Capture (Ingestor) ----
        t0 = time.monotonic()
        try:
            chunks, ingested_doc, pages = self._ingestor.ingest(doc.source_path)
        except Exception as e:
            return Trace(
                stages=(TraceStage(
                    name="context_capture",
                    input_data={"path": doc.source_path},
                    output_data={"error": str(e)},
                    status="halted",
                ),),
                halted=True,
                halt_reason=f"Ingestor failed: {e}",
            )

        elapsed_ms = (time.monotonic() - t0) * 1000
        stages.append(TraceStage(
            name="context_capture",
            input_data={"path": doc.source_path},
            output_data={"chunk_count": len(chunks), "page_count": ingested_doc.page_count},
            duration_ms=elapsed_ms,
        ))

        # Register in provenance + memory
        self._provenance.register_document(ingested_doc)
        self._memory.upsert_document(ingested_doc)
        for page in pages:
            self._memory.upsert_page(page)
        for chunk in chunks:
            self._provenance.register_chunk(chunk)
            self._memory.upsert_chunk(chunk)

        # ---- Stage 2: Security Filter ----
        t0 = time.monotonic()
        all_text = "\n".join(c.text for c in chunks)
        scan_result = self._security.scan(all_text)
        elapsed_ms = (time.monotonic() - t0) * 1000

        stages.append(TraceStage(
            name="security_filter",
            input_data={"text_length": len(all_text)},
            output_data={
                "blocked": scan_result.blocked,
                "reasons": scan_result.reasons,
            },
            duration_ms=elapsed_ms,
            status="halted" if scan_result.blocked else "ok",
        ))

        if scan_result.blocked:
            return Trace(
                stages=tuple(stages),
                halted=True,
                halt_reason=f"Security filter blocked: {scan_result.reasons}",
            )

        # ---- Stage 3: Intent Gate ----
        t0 = time.monotonic()
        # Determine intent: extraction from document
        intent = {
            "type": "extract",
            "pack": self._pack.__class__.__name__,
            "fields": self._pack.fields,
        }
        elapsed_ms = (time.monotonic() - t0) * 1000

        stages.append(TraceStage(
            name="intent_gate",
            input_data={"chunk_count": len(chunks)},
            output_data=intent,
            duration_ms=elapsed_ms,
        ))

        # ---- Stage 4: Router ----
        t0 = time.monotonic()
        # Route to the appropriate Pack based on intent
        router_result = {
            "selected_pack": self._pack.__class__.__name__,
            "fields_to_extract": self._pack.fields,
        }
        elapsed_ms = (time.monotonic() - t0) * 1000

        stages.append(TraceStage(
            name="router",
            input_data=intent,
            output_data=router_result,
            duration_ms=elapsed_ms,
        ))

        # ---- Stage 4.5: Context Compression (Kairo Context Compressor) ----
        t0 = time.monotonic()
        compression_stats = None
        try:
            from kairo.context.compressor import compress_document_chunks, record_compression
            compressed_chunks, compression_stats = compress_document_chunks(chunks)
            record_compression(compression_stats)
            # Use compressed chunks for extraction (preserves bbox/page metadata)
            extraction_chunks = compressed_chunks
        except ImportError:
            extraction_chunks = chunks  # fallback if compressor not available
        elapsed_ms = (time.monotonic() - t0) * 1000
        stages.append(TraceStage(
            name="context_compression",
            input_data={"chunk_count": len(chunks)},
            output_data={
                "compressed_chunk_count": len(extraction_chunks),
                "reduction_pct": compression_stats.reduction_pct if compression_stats else 0.0,
            } if compression_stats else {"status": "skipped"},
            duration_ms=elapsed_ms,
        ))

        # ---- Stage 5: Extractor (Pack) ----
        t0 = time.monotonic()
        # Inject source filename into chunks' source_type for packs that need it
        # (e.g., invoice pack derives invoice number from filename when not in text)
        import os as _os
        _source_filename = _os.path.basename(doc.source_path) if doc.source_path else ""
        if _source_filename:
            from dataclasses import replace as _replace
            chunks = [_replace(c, source_type=_source_filename) for c in chunks]
        try:
            extractions = self._pack.extract(extraction_chunks)
        except Exception as e:
            stages.append(TraceStage(
                name="extractor",
                input_data={"chunk_count": len(chunks)},
                output_data={"error": str(e)},
                duration_ms=(time.monotonic() - t0) * 1000,
                status="halted",
            ))
            return Trace(
                stages=tuple(stages),
                halted=True,
                halt_reason=f"Extractor failed: {e}",
            )

        elapsed_ms = (time.monotonic() - t0) * 1000
        stages.append(TraceStage(
            name="extractor",
            input_data={"chunk_count": len(chunks)},
            output_data={"extraction_count": len(extractions)},
            duration_ms=elapsed_ms,
        ))

        # ---- Stage 5.5: Grounding Verification ----
        from kernel.core.grounding import GroundingVerifierImpl
        verifier = GroundingVerifierImpl()
        grounded_extractions = []
        for ext in extractions:
            method, anchors = verifier.verify(ext.value, ext.source_span, chunks)
            chunk_id = anchors[0].chunk_id if anchors else ext.chunk_id
            ext = replace(ext, method=method, anchors=anchors, chunk_id=chunk_id)
            grounded_extractions.append(ext)
        extractions = grounded_extractions

        # Register extractions in provenance + memory
        for ext in extractions:
            self._provenance.register_extraction(ext)
            self._memory.record_extraction(ext)

        # ---- Stage 6: Quality Gate ----
        t0 = time.monotonic()
        gate_results: list[dict[str, Any]] = []
        passed_extractions: list[Extraction] = []

        for ext in extractions:
            gate_result = self._quality.check(ext)
            gate_results.append({
                "ext_id": ext.ext_id,
                "field": ext.field_name,
                "verdict": gate_result.verdict.value,
                "confidence": gate_result.calibrated_confidence,
            })

            if gate_result.verdict == GateVerdict.BLOCK:
                # HALT to human_review
                halted = True
                halt_reason = (
                    f"Quality gate BLOCKED extraction {ext.ext_id} "
                    f"(field={ext.field_name}): {gate_result.reasons}"
                )
                # Mark as pending_review
                blocked_ext = replace(
                    ext,
                    status=ExtractionStatus.PENDING_REVIEW,
                    confidence=gate_result.calibrated_confidence,
                )
                all_extractions.append(blocked_ext)
            elif gate_result.verdict == GateVerdict.FLAG:
                # Flag for review but don't halt entirely
                flagged_ext = replace(
                    ext,
                    status=ExtractionStatus.PENDING_REVIEW,
                    confidence=gate_result.calibrated_confidence,
                )
                all_extractions.append(flagged_ext)
            else:
                # PASS
                passed_ext = replace(
                    ext,
                    confidence=gate_result.calibrated_confidence,
                )
                passed_extractions.append(passed_ext)
                all_extractions.append(passed_ext)

        elapsed_ms = (time.monotonic() - t0) * 1000
        stages.append(TraceStage(
            name="quality_gate",
            input_data={"extraction_count": len(extractions)},
            output_data={
                "results": gate_results,
                "passed": len(passed_extractions),
                "flagged_or_blocked": len(extractions) - len(passed_extractions),
            },
            duration_ms=elapsed_ms,
            status="halted" if halted else "ok",
        ))

        if halted:
            # Route to human_review terminal
            stages.append(TraceStage(
                name="human_review",
                input_data={
                    "reason": halt_reason,
                    "extractions_needing_review": [
                        e.ext_id for e in all_extractions
                        if e.status == ExtractionStatus.PENDING_REVIEW
                    ],
                },
                output_data={"status": "awaiting_human_review"},
                status="halted",
            ))
            return Trace(
                stages=tuple(stages),
                halted=True,
                halt_reason=halt_reason,
                extractions=tuple(all_extractions),
            )

        # ---- Stage 7: Suggest ----
        t0 = time.monotonic()
        suggestions = []
        for ext in passed_extractions:
            suggestions.append({
                "ext_id": ext.ext_id,
                "field": ext.field_name,
                "value": ext.value,
                "confidence": ext.confidence,
            })
        elapsed_ms = (time.monotonic() - t0) * 1000

        stages.append(TraceStage(
            name="suggest",
            input_data={"passed_count": len(passed_extractions)},
            output_data={"suggestions": suggestions},
            duration_ms=elapsed_ms,
        ))

        return Trace(
            stages=tuple(stages),
            halted=False,
            extractions=tuple(all_extractions),
        )
