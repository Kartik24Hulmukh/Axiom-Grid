"""Run inside the release container; exercise authenticated real-file intake."""
import json
import os
import tempfile
import urllib.request
from pathlib import Path

from docx import Document


def write_pdf(path):
    # Minimal valid PDF with compressed content, so decoding bytes is not extraction.
    import zlib
    stream = zlib.compress(b"BT /F1 12 Tf 72 720 Td (CLASSIFICATION: UNCLASSIFIED) Tj 0 -20 Td (SUBJECT: release intake) Tj ET")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" /Filter /FlateDecode >>\nstream\n" + stream + b"\nendstream",
    ]
    data = b"%PDF-1.4\n"
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 6\n0000000000 65535 f \n"
    data += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    data += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(data)
    return path


with tempfile.TemporaryDirectory(prefix="axiom-intake-") as directory:
    root = Path(directory)
    pdf = write_pdf(root / "memo.pdf")
    word = root / "memo.docx"
    doc = Document()
    doc.add_paragraph("CLASSIFICATION: UNCLASSIFIED")
    doc.add_paragraph("SUBJECT: release intake")
    doc.save(word)
    for path in (pdf, word):
        request = urllib.request.Request(
            "http://127.0.0.1:8765/api/extract-document",
            data=json.dumps({"file": str(path)}).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + os.environ["AXIOM_API_KEYS"]},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
        assert data["doc_type"] == "memo", data
        assert data["fields"], data
        print(path.suffix, "authenticated real document intake: PASS")
