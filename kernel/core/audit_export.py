"""
Kairo Phantom — Audit Export (X1: compliance infrastructure)

Produces regulator/partner-acceptable export formats from a SignedAuditLog:
- JSON: machine-readable, structured for ingestion by compliance systems.
- Markdown: human-readable, PDF-ready for legal/IT review.

The export says: 'here is exactly what the AI cited, and here is what it
refused to answer and why.'
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from kernel.core.audit_log import SignedAuditLog


def export_json(audit_log: SignedAuditLog) -> str:
    """Export the audit log as structured JSON for compliance systems.

    Includes a summary header and the full entry list with chain verification
    status.
    """
    chain_valid = audit_log.verify_chain()
    entries = []
    for e in audit_log.entries:
        entries.append({
            "entry_id": e.entry_id,
            "timestamp": e.timestamp,
            "question": e.question,
            "document_hash": e.document_hash,
            "outcome": e.outcome,
            "grounded": e.grounded,
            "source_region": e.source_region if e.source_region else None,
            "cascade_stage": e.cascade_stage,
            "model_id": e.model_id,
            "signature": e.signature,
            "prev_signature": e.prev_signature,
        })

    export = {
        "export_metadata": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "entry_count": len(entries),
            "chain_integrity": "VALID" if chain_valid else "BROKEN",
            "format_version": "1.0",
            "system": "Kairo Phantom",
        },
        "summary": {
            "total_answers": sum(1 for e in audit_log.entries if e.outcome == "answer"),
            "total_refusals": sum(1 for e in audit_log.entries if e.outcome == "refusal"),
            "grounded_answers": sum(1 for e in audit_log.entries if e.outcome == "answer" and e.grounded),
            "ungrounded_answers": sum(1 for e in audit_log.entries if e.outcome == "answer" and not e.grounded),
        },
        "entries": entries,
    }
    return json.dumps(export, indent=2)


def export_markdown(audit_log: SignedAuditLog) -> str:
    """Export the audit log as human-readable, PDF-ready markdown.

    Format: 'here is exactly what the AI cited, and here is what it refused
    to answer and why.'
    """
    chain_valid = audit_log.verify_chain()
    entries = audit_log.entries
    answers = [e for e in entries if e.outcome == "answer"]
    refusals = [e for e in entries if e.outcome == "refusal"]

    lines: list[str] = []
    lines.append("# Kairo Phantom — Audit Log Export")
    lines.append("")
    lines.append(f"**Exported:** {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"**Total entries:** {len(entries)}")
    lines.append(f"**Chain integrity:** {'✅ VALID (untampered)' if chain_valid else '❌ BROKEN (tampered)'}")
    lines.append(f"**Grounded answers:** {sum(1 for e in answers if e.grounded)}")
    lines.append(f"**Refusals:** {len(refusals)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 1: What the AI cited (answers)
    lines.append("## 1. Answers — What the AI Cited")
    lines.append("")
    if not answers:
        lines.append("_No answers were recorded._")
        lines.append("")
    else:
        for i, e in enumerate(answers, 1):
            lines.append(f"### Answer {i}")
            lines.append(f"- **Question:** {e.question}")
            lines.append(f"- **Timestamp:** {e.timestamp}")
            lines.append(f"- **Model:** {e.model_id}")
            lines.append(f"- **Document hash:** `{e.document_hash}`")
            lines.append(f"- **Grounded:** {'Yes' if e.grounded else 'No'}")
            lines.append(f"- **Grounding method:** {e.cascade_stage}")
            if e.source_region:
                region = e.source_region
                lines.append("- **Source region:**")
                lines.append(f"  - Page: {region.get('page', 'N/A')}")
                lines.append(f"  - Chunk ID: {region.get('chunk_id', 'N/A')}")
                lines.append(f"  - Character span: {region.get('char_span', 'N/A')}")
                if "bbox" in region:
                    bbox = region["bbox"]
                    lines.append(f"  - Bounding box: ({bbox['x0']}, {bbox['y0']}) → ({bbox['x1']}, {bbox['y1']})")
            lines.append(f"- **Signature:** `{e.signature[:16]}...`")
            lines.append("")

    lines.append("---")
    lines.append("")

    # Section 2: What the AI refused to answer and why
    lines.append("## 2. Refusals — What the AI Refused to Answer and Why")
    lines.append("")
    if not refusals:
        lines.append("_No refusals were recorded._")
        lines.append("")
    else:
        for i, e in enumerate(refusals, 1):
            lines.append(f"### Refusal {i}")
            lines.append(f"- **Question:** {e.question}")
            lines.append(f"- **Timestamp:** {e.timestamp}")
            lines.append(f"- **Model:** {e.model_id}")
            lines.append(f"- **Document hash:** `{e.document_hash}`")
            lines.append("- **Refusal reason:** Could not ground the answer to source text")
            lines.append(f"- **Cascade stage that blocked:** {e.cascade_stage}")
            lines.append(f"- **Signature:** `{e.signature[:16]}...`")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Chain Verification")
    lines.append("")
    lines.append("The audit log uses HMAC-SHA256 hash chaining. Each entry's signature "
                 "covers its content plus the previous entry's signature.")
    lines.append("")
    lines.append(f"**Chain status:** {'VALID — no tampering detected' if chain_valid else 'BROKEN — tampering detected'}")
    lines.append("")
    lines.append("## Cryptographic Details")
    lines.append("")
    lines.append("- **Algorithm:** HMAC-SHA256")
    lines.append("- **Chaining:** Each entry signs (content + previous entry signature)")
    lines.append("- **Genesis entry:** Previous signature is empty string")
    lines.append("- **Tamper detection:** Modifying any field in any entry invalidates "
                 "the chain from that entry forward")
    lines.append("")

    return "\n".join(lines)


def export_to_files(audit_log: SignedAuditLog, output_dir: str) -> tuple[str, str]:
    """Export both JSON and markdown to files in output_dir.
    Returns (json_path, markdown_path).
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, "audit_export.json")
    md_path = os.path.join(output_dir, "audit_export.md")

    with open(json_path, "w") as f:
        f.write(export_json(audit_log))
    with open(md_path, "w") as f:
        f.write(export_markdown(audit_log))

    return json_path, md_path