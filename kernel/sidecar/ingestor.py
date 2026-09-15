"""
Kairo Phantom — Ingestor (SPEC §S2, §S4)

Ingests document files and produces Chunks with non-null page + bbox.
Uses text extraction for .txt/.md files and structured parsing for
.pdf/.docx/.xlsx/.pptx files.

INVARIANT: Every Chunk has non-null page and bbox after ingestion.

The kernel imports NOTHING from /domains or /legacy.
"""

from __future__ import annotations

import hashlib
import logging
import pathlib
import re
from dataclasses import replace
from datetime import datetime, timezone

from kernel.core.data_model import BBox, Chunk, Document, Page

logger = logging.getLogger(__name__)

# Approximate characters per line for bbox estimation in text files
_CHARS_PER_LINE = 80
_LINES_PER_PAGE = 60


class IngestorImpl:
    """Concrete Ingestor implementation.

    Ingests files and produces Chunks with guaranteed page + bbox.
    Supports: .txt, .md, .pdf (local pdfplumber), .docx (python-docx).
    """

    def ingest(self, path: str) -> tuple[list[Chunk], Document, list[Page]]:
        """Ingest a document file and return Chunks, Document, and Pages.

        Every Chunk MUST have non-null page and bbox.
        Raises FileNotFoundError if the file doesn't exist.
        Raises ValueError if the file type is unsupported.
        """
        filepath = pathlib.Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"Document not found: {path}")

        # Compute document metadata
        content_bytes = filepath.read_bytes()
        sha256 = hashlib.sha256(content_bytes).hexdigest()
        suffix = filepath.suffix.lower()

        if suffix in (".txt", ".md"):
            chunks, page_count, pages = self._ingest_text(filepath, sha256)
        elif suffix == ".pdf":
            chunks, page_count, pages = self._ingest_pdf(filepath, sha256)
        elif suffix == ".docx":
            chunks, page_count, pages = self._ingest_docx(filepath, sha256)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

        # Create the Document
        doc = Document(
            source_path=str(filepath),
            sha256=sha256,
            page_count=page_count,
            ingested_at=datetime.now(timezone.utc),
        )

        # Set doc_id on all chunks and pages and verify invariants
        updated_chunks: list[Chunk] = []
        for chunk in chunks:
            updated_chunk = replace(chunk, doc_id=doc.doc_id)
            if updated_chunk.bbox is None:
                raise RuntimeError(
                    f"Ingestor invariant violated: chunk {updated_chunk.chunk_id} has no bbox"
                )
            if updated_chunk.page < 1:
                raise RuntimeError(
                    f"Ingestor invariant violated: chunk {updated_chunk.chunk_id} has page={updated_chunk.page} (must be >= 1)"
                )
            updated_chunks.append(updated_chunk)

        updated_pages: list[Page] = []
        for page in pages:
            updated_page = replace(page, doc_id=doc.doc_id)
            updated_pages.append(updated_page)

        logger.info(
            "Ingested %s: %d chunks, %d pages, sha256=%s",
            filepath.name,
            len(updated_chunks),
            page_count,
            sha256[:16],
        )

        return updated_chunks, doc, updated_pages

    def _ingest_text(
        self, filepath: pathlib.Path, sha256: str
    ) -> tuple[list[Chunk], int, list[Page]]:
        """Ingest a text/markdown file into chunks by paragraph."""
        text = filepath.read_text(encoding="utf-8", errors="replace")
        paragraphs = self._split_paragraphs(text)

        chunks: list[Chunk] = []
        current_line = 0
        page_count = 1

        for para_text in paragraphs:
            if not para_text.strip():
                current_line += 1
                continue

            para_lines = para_text.count("\n") + 1
            page = (current_line // _LINES_PER_PAGE) + 1
            page_count = max(page_count, page)

            # Estimate bbox based on line position within page
            page_offset = current_line % _LINES_PER_PAGE
            y0 = page_offset * (1.0 / _LINES_PER_PAGE)
            y1 = min(1.0, (page_offset + para_lines) * (1.0 / _LINES_PER_PAGE))

            chunk = Chunk(
                page=page,
                bbox=BBox(x0=0.0, y0=y0, x1=1.0, y1=y1),
                text=para_text.strip(),
                source_type="text",
            )
            chunks.append(chunk)
            current_line += para_lines + 1  # +1 for blank line between paragraphs

        # Generate Page objects
        pages: list[Page] = []
        for p in range(1, page_count + 1):
            pages.append(Page(
                doc_id="",
                index=p,
                width_px=800,
                height_px=1000,
                image_sha256="",
            ))

        return chunks, page_count, pages

    def _ingest_pdf(
        self, filepath: pathlib.Path, sha256: str
    ) -> tuple[list[Chunk], int, list[Page]]:
        """Extract text locally; never decode PDF bytes or auto-load model engines.

        Scanned/image-only PDFs fail explicitly: OCR is not in this launch slice.
        pdfplumber supplies measured word boxes, not invented layout coordinates.
        """
        try:
            import pdfplumber
        except ImportError as exc:
            raise RuntimeError("PDF ingestion requires pdfplumber") from exc

        chunks: list[Chunk] = []
        pages: list[Page] = []
        try:
            with pdfplumber.open(filepath) as pdf:
                for number, page in enumerate(pdf.pages, 1):
                    width, height = float(page.width), float(page.height)
                    if width <= 0 or height <= 0:
                        raise ValueError("Invalid PDF page dimensions")
                    words = page.extract_words()
                    pages.append(Page(doc_id="", index=number, width_px=int(width),
                                      height_px=int(height), image_sha256=""))
                    if not words:
                        continue
                    text = page.extract_text() or ""
                    if not text.strip():
                        continue
                    x0 = max(0.0, min(1.0, min(w["x0"] for w in words) / width))
                    x1 = max(x0, min(1.0, max(w["x1"] for w in words) / width))
                    y0 = max(0.0, min(1.0, min(w["top"] for w in words) / height))
                    y1 = max(y0, min(1.0, max(w["bottom"] for w in words) / height))
                    chunks.append(Chunk(page=number, bbox=BBox(x0=x0, y0=y0, x1=x1, y1=y1),
                                        text=text.strip(), source_type="pdf_text"))
        except Exception as exc:  # noqa: BLE001 -- parser boundary, never return binary as text
            raise ValueError("Unable to parse PDF document") from exc
        if not chunks:
            raise ValueError("PDF contains no extractable text; OCR is not enabled")
        return chunks, len(pages), pages

    def _ingest_docx(
        self, filepath: pathlib.Path, sha256: str
    ) -> tuple[list[Chunk], int, list[Page]]:
        """Ingest a DOCX file. Uses python-docx if available."""
        try:
            from docx import Document as DocxDocument
        except ImportError as exc:
            raise RuntimeError("DOCX ingestion requires python-docx") from exc

        try:
            doc = DocxDocument(str(filepath))
        except Exception as exc:  # noqa: BLE001 -- malformed Office container boundary
            raise ValueError("Unable to parse DOCX document") from exc
        chunks: list[Chunk] = []
        current_line = 0
        page_count = 1

        for para in doc.paragraphs:
            if not para.text.strip():
                current_line += 1
                continue

            para_lines = max(1, len(para.text) // _CHARS_PER_LINE + 1)
            page = (current_line // _LINES_PER_PAGE) + 1
            page_count = max(page_count, page)

            page_offset = current_line % _LINES_PER_PAGE
            y0 = page_offset * (1.0 / _LINES_PER_PAGE)
            y1 = min(1.0, (page_offset + para_lines) * (1.0 / _LINES_PER_PAGE))

            chunk = Chunk(
                page=page,
                bbox=BBox(x0=0.0, y0=y0, x1=1.0, y1=y1),
                text=para.text.strip(),
                source_type="docx_paragraph",
            )
            chunks.append(chunk)
            current_line += para_lines + 1

        # Generate Page objects
        pages: list[Page] = []
        for p in range(1, page_count + 1):
            pages.append(Page(
                doc_id="",
                index=p,
                width_px=800,
                height_px=1000,
                image_sha256="",
            ))

        return chunks, page_count, pages

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        """Split text into paragraphs by double newline or single newline
        when lines start with numbered/bulleted items."""
        # Split on double newlines first
        blocks = re.split(r"\n\s*\n", text)
        return [b for b in blocks if b.strip()]
