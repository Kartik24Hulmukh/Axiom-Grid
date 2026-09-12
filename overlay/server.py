"""
Kairo Phantom — Overlay Server (SPEC §S8)

FastAPI service serving the premium glass-chrome UX for de-identification triage.
Allows viewing source documents, highlights bbox, and accept/edit/reject.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import pathlib

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from kernel.core.data_model import (
    Action,
    ActionKind,
    ActionStatus,
    Correction,
    Document,
    ExtractionStatus,
)
from kernel.core.provenance import ProvenanceLogImpl
from kernel.sidecar.action_executor import ActionExecutorImpl
from kernel.sidecar.inference_gateway import TieredInferenceGateway
from kernel.sidecar.ingestor import IngestorImpl
from kernel.sidecar.memory_store import MemoryStoreImpl
from kernel.sidecar.orchestrator import OrchestratorImpl
from kernel.sidecar.quality_gate import LocalQualityGate
from kernel.sidecar.security_filter import LocalSecurityFilter
from packs.contract.pack import ContractPack
from packs.generic.pack import GenericPack
from packs.invoice.pack import InvoicePack
from packs.paper.pack import PaperPack
from pydantic import BaseModel, Field, field_validator

# Initialize FastAPI
app = FastAPI(title="Kairo Phantom Web Overlay")
logger = logging.getLogger("overlay.server")

# Paths
BASE_DIR = pathlib.Path(__file__).parents[1]
FIXTURES_DIR = BASE_DIR / "fixtures" / "wedge"
TEMPLATES_DIR = BASE_DIR / "overlay" / "templates"

# Initialize Core Services
provenance_log = ProvenanceLogImpl()
memory_store = MemoryStoreImpl(BASE_DIR / ".kairo" / "overlay_store.db")
ingestor = IngestorImpl()
security_filter = LocalSecurityFilter(enable_pii_scan=False)

# Gateway in test mode (no LiteLLM/Ollama needed for overlay demonstration)
os.environ["KAIRO_GATEWAY_TEST_MODE"] = "true"
inference_gateway = TieredInferenceGateway(tier3_enabled=False)

quality_gate = LocalQualityGate(memory_store)
wedge_pack = GenericPack()

orchestrator = OrchestratorImpl(
    ingestor=ingestor,
    security_filter=security_filter,
    inference_gateway=inference_gateway,
    quality_gate=quality_gate,
    provenance_log=provenance_log,
    pack=wedge_pack,
    memory_store=memory_store,
)

action_executor = ActionExecutorImpl(provenance_log)


class DemoRequest(BaseModel):
    """Strict schema: a non-blank, bounded file reference (no NUL bytes)."""

    file: str = Field(min_length=1, max_length=4096, pattern=r"^[^\x00]+$")

    @field_validator("file")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("file must not be blank")
        return value


class ApplyRequest(BaseModel):
    ext_id: str
    accept: bool


class CorrectionRequest(BaseModel):
    ext_id: str
    field_name: str
    original: str
    corrected: str
    reason: str


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the primary HTML overlay template."""
    template_path = TEMPLATES_DIR / "index.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template not found")
    content = await asyncio.to_thread(template_path.read_text, encoding="utf-8")
    return HTMLResponse(content=content)


@app.post("/demo")
async def run_demo(req: DemoRequest):
    """Run the pipeline on a document and return data for the overlay."""
    candidates = (pathlib.Path(req.file), FIXTURES_DIR / req.file, BASE_DIR / req.file)
    file_path = next((c for c in candidates if c.is_file()), None)
    if file_path is None:
        raise HTTPException(status_code=404, detail=f"File {req.file} not found")

    try:
        # 1. Create target document
        # Real provenance digest of the exact bytes fed to the pipeline.
        try:
            file_bytes = await asyncio.to_thread(file_path.read_bytes)
            digest = hashlib.sha256(file_bytes).hexdigest()
        except OSError as exc:
            raise HTTPException(status_code=422, detail=f"Unable to read {req.file}: {exc}") from exc
        doc = Document(
            source_path=str(file_path),
            sha256=digest,
        )

        # 2. Run Orchestrator
        trace = orchestrator.run(doc)

        # 3. Read raw file contents to return to UI
        if file_path.suffix.lower() in (".txt", ".md"):
            document_text = await asyncio.to_thread(file_path.read_text, encoding="utf-8", errors="replace")
        else:
            # Reconstruct document text from the registered chunks
            doc_chunks = [c for c in provenance_log._chunks.values() if c.doc_id == doc.doc_id]
            if not doc_chunks:
                doc_chunks = list(provenance_log._chunks.values())
            document_chunks = sorted(
                doc_chunks,
                key=lambda c: (c.page, c.bbox.y0 if c.bbox else 0)
            )
            document_text = "\n\n".join(chunk.text for chunk in document_chunks)

        # 4. Format suggestions with bbox + page mapping
        suggestions = []
        for ext in trace.extractions:
            if ext.status == ExtractionStatus.BLOCKED:
                continue
            
            chain = provenance_log.get_provenance(ext.ext_id)
            if not chain.is_complete:
                continue

            suggestions.append({
                "ext_id": ext.ext_id,
                "field_name": ext.field_name,
                "value": ext.value,
                "confidence": ext.confidence,
                "page": chain.chunk.page if chain.chunk else 1,
                "chunk_id": chain.chunk.chunk_id if chain.chunk else "",
                "bbox": {
                    "x0": chain.chunk.bbox.x0 if chain.chunk and chain.chunk.bbox else 0,
                    "y0": chain.chunk.bbox.y0 if chain.chunk and chain.chunk.bbox else 0,
                    "x1": chain.chunk.bbox.x1 if chain.chunk and chain.chunk.bbox else 1,
                    "y1": chain.chunk.bbox.y1 if chain.chunk and chain.chunk.bbox else 1,
                }
            })

            # Register proposed action for each suggestion
            action = Action(
                ext_id=ext.ext_id,
                kind=ActionKind.SUGGEST,
                target_app="notepad",
                payload={"value": ext.value},
                confidence=ext.confidence,
                status=ActionStatus.PENDING,
            )
            provenance_log.register_action(action)

        # 5. Format trace details
        formatted_trace = {
            "halted": trace.halted,
            "halt_reason": trace.halt_reason,
            "stages": [
                {
                    "name": s.name,
                    "input_data": s.input_data,
                    "output_data": s.output_data,
                    "duration_ms": s.duration_ms,
                    "status": s.status,
                }
                for s in trace.stages
            ]
        }

        return {
            "success": True,
            "document_text": document_text,
            "suggestions": suggestions,
            "trace": formatted_trace,
        }

    except Exception as e:
        logger.exception("unhandled error in overlay endpoint: %s", e)
        return {"success": False, "error": str(e)}


@app.post("/apply")
async def apply_cua(req: ApplyRequest):
    """Execute a confirmed CUA action and verify post-state."""
    # Retrieve action from provenance log
    action_id = None
    for act_id, act in provenance_log._actions.items():
        if act.ext_id == req.ext_id:
            action_id = act_id
            break

    if not action_id:
        return {"success": False, "error": "No pending action found for this extraction"}

    action = provenance_log._actions[action_id]
    
    # Kairo ActionExecutor requires human_confirm=True
    result = action_executor.apply(action, human_confirm=req.accept)
    return {
        "success": result.success,
        "error": result.error,
        "post_state": result.post_state,
    }


@app.post("/correct")
async def record_flywheel_correction(req: CorrectionRequest):
    """Record a correction to memory store, triggering the local flywheel."""
    try:
        corr = Correction(
            ext_id=req.ext_id,
            original=req.original,
            corrected=req.corrected,
            reason=req.reason,
            by="overlay-user",
        )
        memory_store.record_correction(corr)
        return {"success": True}
    except Exception as e:
        logger.exception("unhandled error in overlay endpoint: %s", e)
        return {"success": False, "error": str(e)}


# Mount static directory for serving page images
if pathlib.Path(".kairo").exists():
    app.mount("/static", StaticFiles(directory=".kairo"), name="static")


@app.get("/api/compression/stats")
async def get_compression_stats():
    """Return aggregate context compression statistics."""
    try:
        from kairo.context.compressor import get_compression_stats
        return get_compression_stats()
    except ImportError:
        return {"error": "Context compressor not available", "total_runs": 0}


@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the Kairo Grounding Trace dashboard."""
    dashboard_path = BASE_DIR / "kairo" / "observability" / "dashboard.html"
    if dashboard_path.exists():
        content = await asyncio.to_thread(dashboard_path.read_text)
        return HTMLResponse(content=content, status_code=200)
    return HTMLResponse(content="<h1>Dashboard not found</h1>", status_code=404)


@app.get("/api/traces")
async def get_traces(limit: int = 50):
    """Return recent grounding traces for the dashboard."""
    try:
        from kairo.observability.trace import get_traces
        return get_traces(limit=limit)
    except ImportError:
        return []


@app.get("/api/traces/stats")
async def get_trace_stats():
    """Return aggregate grounding trace statistics."""
    try:
        from kairo.observability.trace import get_trace_stats
        return get_trace_stats()
    except ImportError:
        return {"total_traces": 0, "grounded_pct": 0.0}


# ---- Phase 3: Connector Protocol ----

class ExtractDocumentRequest(BaseModel):
    file: str  # path to document file
    extraction_schema: dict | None = None  # optional extraction schema


@app.post("/api/extract-document")
async def extract_document(req: ExtractDocumentRequest):
    """Extract fields from a document with grounding metadata.

    Returns fields with value, grounded status, bbox, cascade method,
    confidence, and source_link for each extracted field.
    """
    import os
    filepath = req.file
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"File not found: {filepath}")

    # Read and classify (blocking I/O off the event loop)
    def _read(fp):
        with open(fp, "r", errors="ignore") as f:
            return f.read()
    text = await asyncio.to_thread(_read, filepath)

    from kairo.core.classifier import build_source_link, classify_document
    doc_type = classify_document(text)

    # Select pack based on type
    pack_map = {
        "invoice": InvoicePack,
        "contract": ContractPack,
        "paper": PaperPack,
        "generic": GenericPack,
    }
    pack_class = pack_map.get(doc_type, GenericPack)

    # Run extraction pipeline
    from kernel.core.data_model import Document
    from kernel.core.provenance import ProvenanceLogImpl
    from kernel.sidecar.inference_gateway import TieredInferenceGateway
    from kernel.sidecar.ingestor import IngestorImpl
    from kernel.sidecar.memory_store import MemoryStoreImpl
    from kernel.sidecar.quality_gate import LocalQualityGate
    from kernel.sidecar.security_filter import LocalSecurityFilter

    memory_store = MemoryStoreImpl(":memory:")
    provenance = ProvenanceLogImpl()
    ingestor = IngestorImpl()
    security = LocalSecurityFilter(enable_pii_scan=False)
    gateway = TieredInferenceGateway(tier3_enabled=False)
    quality_gate = LocalQualityGate(memory_store)
    orchestrator = OrchestratorImpl(
        ingestor=ingestor, security_filter=security, inference_gateway=gateway,
        quality_gate=quality_gate, provenance_log=provenance,
        pack=pack_class(), memory_store=memory_store,
    )

    doc = Document(source_path=filepath)
    trace = orchestrator.run(doc)

    # Build response with grounding metadata
    fields = {}
    refused_fields = []
    for ext in trace.extractions:
        bbox = None
        page = 1
        if ext.anchors:
            a = ext.anchors[0]
            bbox = [a.bbox.x0, a.bbox.y0, a.bbox.x1 - a.bbox.x0, a.bbox.y1 - a.bbox.y0]
            page = a.page

        grounded = ext.method.value != "block"
        if grounded:
            fields[ext.field_name] = {
                "value": ext.value,
                "grounded": True,
                "bbox": bbox,
                "page": page,
                "cascade": ext.method.value.upper(),
                "confidence": ext.confidence,
                "source_link": build_source_link(doc.doc_id, page, bbox or [0, 0, 0, 0]),
            }
        else:
            refused_fields.append(ext.field_name)

    return {
        "doc_id": doc.doc_id,
        "doc_type": doc_type,
        "fields": fields,
        "refused_fields": refused_fields,
        "processing_time_ms": sum(s.duration_ms for s in trace.stages),
    }


@app.post("/api/ask-document")
async def ask_document(req: dict):
    """Ask a question about a document. Returns answer with bbox or refusal."""
    filepath = req.get("file", "")
    question = req.get("question", "")

    if not filepath:
        raise HTTPException(status_code=400, detail="file is required")

    import os
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"File not found: {filepath}")

    # For now, extract all fields and check if the question matches any
    extract_req = ExtractDocumentRequest(file=filepath)
    result = await extract_document(extract_req)

    # Simple keyword matching: find field whose name or value matches question keywords
    question_lower = question.lower()
    for field_name, field_data in result["fields"].items():
        if field_name.replace("_", " ") in question_lower or field_name in question_lower:
            return {
                "question": question,
                "answer": field_data["value"],
                "grounded": True,
                "bbox": field_data["bbox"],
                "page": field_data["page"],
                "source_link": field_data["source_link"],
            }

    # No match -> refusal
    return {
        "question": question,
        "answer": None,
        "grounded": False,
        "refusal_reason": "No grounded answer found for this question in the document.",
    }


@app.get("/api/source/{doc_id}")
async def get_source_render(doc_id: str, page: int = 1, x: float = 0, y: float = 0, w: float = 0, h: float = 0):
    """Render a document page with bbox highlight overlay.

    For text documents, returns the text with the highlighted region marked.
    For PDFs, would render via PyMuPDF (requires the source file path).
    """
    # In a full implementation, this would render the page as PNG via PyMuPDF
    # and overlay an SVG bbox. For now, return metadata.
    return {
        "doc_id": doc_id,
        "page": page,
        "highlight_bbox": [x, y, w, h] if w > 0 and h > 0 else None,
        "render_url": f"kairo://doc/{doc_id}?page={page}&x={x}&y={y}&w={w}&h={h}",
    }


# ---- Phase 4: Knowledge Graph ----

@app.post("/api/graph/query")
async def query_graph(req: dict):
    """Query the grounded knowledge graph by keyword.

    NOT an LLM call — pure keyword + entity matching + graph traversal.
    Returns matching nodes with bbox provenance.
    """
    keyword = req.get("keyword", req.get("query", ""))
    if not keyword:
        raise HTTPException(status_code=400, detail="keyword or query is required")
    try:
        from kairo.graph.store import GroundedKnowledgeGraph
        g = GroundedKnowledgeGraph()
        g.load()  # load persisted graph if available
        results = g.query(keyword)
        return {"keyword": keyword, "results": results, "count": len(results)}
    except Exception as e:
        logger.exception("unhandled error in /api/graph/query: %s", e)
        return {"keyword": keyword, "results": [], "count": 0, "error": str(e)}


@app.get("/api/graph")
async def get_graph():
    """Get the full knowledge graph for visualization."""
    try:
        from kairo.graph.store import GroundedKnowledgeGraph
        g = GroundedKnowledgeGraph()
        g.load()
        return g.to_dict()
    except Exception as e:
        logger.exception("unhandled error in /api/graph: %s", e)
        return {"nodes": [], "edges": [], "stats": {"total_nodes": 0, "total_edges": 0}, "error": str(e)}


# ---- Phase 5: Figure Extraction ----

@app.get("/api/figures/{doc_id}")
async def get_figures(doc_id: str, file: str = ""):
    """Get figures extracted from a document.

    For PDFs: uses PyMuPDF to detect images, find captions, classify.
    For text: extracts Figure/Table references from text.
    """
    filepath = file
    if not filepath:
        raise HTTPException(status_code=400, detail="file parameter is required")

    import os
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"File not found: {filepath}")

    if filepath.lower().endswith(".pdf"):
        from kairo.core.figure_extractor import extract_figures_from_pdf
        figures = extract_figures_from_pdf(filepath)
    else:
        def _read(fp):
            with open(fp, "r", errors="ignore") as f:
                return f.read()
        text = await asyncio.to_thread(_read, filepath)
        from kairo.core.figure_extractor import extract_figures_from_text
        figures = extract_figures_from_text(text)

    return {
        "doc_id": doc_id,
        "file": filepath,
        "figure_count": len(figures),
        "figures": [f.to_dict() for f in figures],
    }


# ---- Phase 6: Eval + Monitoring ----

@app.get("/api/eval/report")
async def get_eval_report():
    """Get the full eval report with regression and drift alerts."""
    from kairo.observability.eval import get_eval_report
    return get_eval_report()


@app.get("/source/{extraction_id}")
async def get_source_provenance(extraction_id: str):
    """Retrieve bounding box and page reference for click-to-source verification."""
    ext = memory_store.get_extraction(extraction_id)
    if not ext:
        ext = provenance_log.get_provenance(extraction_id).extraction
        if not ext:
            raise HTTPException(status_code=404, detail="Extraction not found")

    chain = provenance_log.get_provenance(ext.ext_id)
    if not chain.is_complete or not chain.chunk:
        if ext.anchors:
            anchor = ext.anchors[0]
            bbox = {
                "x0": anchor.bbox.x0 if anchor.bbox else 0,
                "y0": anchor.bbox.y0 if anchor.bbox else 0,
                "x1": anchor.bbox.x1 if anchor.bbox else 1,
                "y1": anchor.bbox.y1 if anchor.bbox else 1,
            }
            page = anchor.page
            doc_id = ext.pack_id
        else:
            raise HTTPException(status_code=404, detail="Provenance chain is incomplete")
    else:
        page = chain.chunk.page
        bbox = {
            "x0": chain.chunk.bbox.x0 if chain.chunk.bbox else 0,
            "y0": chain.chunk.bbox.y0 if chain.chunk.bbox else 0,
            "x1": chain.chunk.bbox.x1 if chain.chunk.bbox else 1,
            "y1": chain.chunk.bbox.y1 if chain.chunk.bbox else 1,
        }
        doc_id = chain.document.doc_id if chain.document else ""

    pages = memory_store.get_pages(doc_id)
    image_ref = ""
    for p in pages:
        if p.index == page:
            image_ref = f"/static/page_images/{p.image_sha256}.png" if p.image_sha256 else ""
            break

    return {
        "page": page,
        "bbox": bbox,
        "image_ref": image_ref,
    }

