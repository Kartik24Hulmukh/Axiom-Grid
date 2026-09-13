"""
Tests for Orchestrator state machine.
"""

from typing import Any

from kernel.core.contracts import GateResult, GateVerdict, ScanResult
from kernel.core.data_model import (
    BBox,
    Chunk,
    Document,
    Extraction,
    ExtractionStatus,
    Trace,
)
from kernel.core.provenance import ProvenanceLogImpl
from kernel.sidecar.orchestrator import OrchestratorImpl


class MockIngestor:
    def __init__(self, chunks: list[Chunk], doc: Document):
        self.chunks = chunks
        self.doc = doc
        from kernel.core.data_model import Page
        self.pages = [Page(doc_id=doc.doc_id, index=1, width_px=800, height_px=1000)]

    def ingest(self, path: str):
        return self.chunks, self.doc, self.pages


class MockSecurityFilter:
    def __init__(self, blocked: bool, reasons: list[str]):
        self.blocked = blocked
        self.reasons = reasons

    def scan(self, text: str) -> ScanResult:
        return ScanResult(blocked=self.blocked, reasons=self.reasons)


class MockInferenceGateway:
    def complete(self, role: str, prompt: str, tier: Any = None):
        from kernel.core.contracts import InferenceResult
        return InferenceResult(text="completion", call_id="call-123")


class MockQualityGate:
    def __init__(self, verdict: GateVerdict, confidence: float, reasons: list[str]):
        self.verdict = verdict
        self.confidence = confidence
        self.reasons = reasons

    def check(self, extraction: Extraction) -> GateResult:
        return GateResult(
            verdict=self.verdict,
            calibrated_confidence=self.confidence,
            reasons=self.reasons,
        )


class MockPack:
    def __init__(self, fields: list[str], extractions: list[Extraction]):
        self._fields = fields
        self._extractions = extractions

    @property
    def fields(self) -> list[str]:
        return self._fields

    def extract(self, chunks: list[Chunk]) -> list[Extraction]:
        return self._extractions


class MockMemoryStore:
    def __init__(self):
        self.docs = []
        self.pages = []
        self.chunks = []
        self.extractions = []

    def upsert_document(self, doc: Document):
        self.docs.append(doc)

    def upsert_page(self, page: Any):
        self.pages.append(page)

    def upsert_chunk(self, chunk: Chunk):
        self.chunks.append(chunk)

    def record_extraction(self, ext: Extraction):
        self.extractions.append(ext)


def test_orchestrator_pipeline_success():
    """Test full successful orchestrator pipeline run."""
    doc = Document(doc_id="doc-123", source_path="memo.txt", sha256="abc", page_count=1)
    chunk = Chunk(chunk_id="chunk-1", doc_id="doc-123", page=1, bbox=BBox(0,0,1,1), text="classified memo info")
    ext = Extraction(ext_id="ext-1", pack_id="wedge", field_name="author", value="Margaret Chen", chunk_id="chunk-1")
    
    ingestor = MockIngestor([chunk], doc)
    security = MockSecurityFilter(blocked=False, reasons=[])
    gateway = MockInferenceGateway()
    quality = MockQualityGate(GateVerdict.PASS, 0.9, [])
    provenance = ProvenanceLogImpl()
    pack = MockPack(["author"], [ext])
    memory = MockMemoryStore()

    orchestrator = OrchestratorImpl(
        ingestor=ingestor,
        security_filter=security,
        inference_gateway=gateway,
        quality_gate=quality,
        provenance_log=provenance,
        pack=pack,
        memory_store=memory,
    )

    trace = orchestrator.run(doc)
    assert isinstance(trace, Trace)
    assert not trace.halted
    assert len(trace.stages) == 8  # capture, security, intent, router, compression, extractor, quality, suggest
    assert len(trace.extractions) == 1
    assert trace.extractions[0].confidence == 0.9
    assert trace.extractions[0].status == ExtractionStatus.SUGGESTED

    # Check that it registered in provenance
    assert provenance.get_provenance("ext-1").is_complete
    assert len(memory.docs) == 1
    assert len(memory.chunks) == 1
    assert len(memory.extractions) == 1


def test_orchestrator_pipeline_halt_security():
    """Test that pipeline halts immediately on security filter blocking."""
    doc = Document(doc_id="doc-123", source_path="memo.txt", sha256="abc", page_count=1)
    chunk = Chunk(chunk_id="chunk-1", doc_id="doc-123", page=1, bbox=BBox(0,0,1,1), text="classified memo info")
    
    ingestor = MockIngestor([chunk], doc)
    security = MockSecurityFilter(blocked=True, reasons=["PROMPT_INJECTION"])
    gateway = MockInferenceGateway()
    quality = MockQualityGate(GateVerdict.PASS, 0.9, [])
    provenance = ProvenanceLogImpl()
    pack = MockPack(["author"], [])
    memory = MockMemoryStore()

    orchestrator = OrchestratorImpl(
        ingestor=ingestor,
        security_filter=security,
        inference_gateway=gateway,
        quality_gate=quality,
        provenance_log=provenance,
        pack=pack,
        memory_store=memory,
    )

    trace = orchestrator.run(doc)
    assert trace.halted
    assert "Security filter blocked" in trace.halt_reason
    assert len(trace.stages) == 2  # capture, security
    assert trace.stages[-1].status == "halted"


def test_orchestrator_pipeline_halt_quality_block():
    """Test that pipeline halts on quality gate BLOCK."""
    doc = Document(doc_id="doc-123", source_path="memo.txt", sha256="abc", page_count=1)
    chunk = Chunk(chunk_id="chunk-1", doc_id="doc-123", page=1, bbox=BBox(0,0,1,1), text="classified memo info")
    ext = Extraction(ext_id="ext-1", pack_id="wedge", field_name="author", value="Margaret Chen", chunk_id="chunk-1")

    ingestor = MockIngestor([chunk], doc)
    security = MockSecurityFilter(blocked=False, reasons=[])
    gateway = MockInferenceGateway()
    quality = MockQualityGate(GateVerdict.BLOCK, 0.1, ["UNGROUNDED"])
    provenance = ProvenanceLogImpl()
    pack = MockPack(["author"], [ext])
    memory = MockMemoryStore()

    orchestrator = OrchestratorImpl(
        ingestor=ingestor,
        security_filter=security,
        inference_gateway=gateway,
        quality_gate=quality,
        provenance_log=provenance,
        pack=pack,
        memory_store=memory,
    )

    trace = orchestrator.run(doc)
    assert trace.halted
    assert "Quality gate BLOCKED" in trace.halt_reason
    assert len(trace.stages) == 8  # capture, security, intent, router, compression, extractor, quality, human_review
    assert trace.stages[-1].name == "human_review"
    assert trace.extractions[0].status == ExtractionStatus.PENDING_REVIEW
