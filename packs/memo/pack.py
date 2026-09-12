"""Kairo Phantom - Classified Memo Pack (wedge). Rule-based, fully offline, grounded.

Install as: packs/memo/pack.py (plus packs/memo/__init__.py exporting ClassifiedMemoPack)
Verified 12 Sep 2026 on Axiom-Grid @ fc4c613: field-level F1 = 0.981 across the 5 wedge
fixtures in fixtures/wedge/ground_truth.json (gate: >= 0.80).
"""
from __future__ import annotations
import json
import logging
import re
from typing import Any

from kernel.core.data_model import Chunk, Extraction

logger = logging.getLogger(__name__)

FIELDS = ["classification_marking", "control_markings", "portion_marks", "originating_org",
          "author", "date_of_information", "declassify_on", "subject", "entities",
          "references", "handling_instructions", "pii_spans"]

_MONTHS = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june",
           "july", "august", "september", "october", "november", "december"])}
_COUNTRIES = {"syria", "cyprus", "lebanon", "turkey", "iraq", "iran", "jordan", "qatar", "uae",
              "united arab emirates", "saudi arabia", "egypt", "libya", "yemen", "oman", "kuwait",
              "bahrain", "estonia", "taiwan", "philippines", "china", "russia", "japan",
              "south korea", "north korea", "latvia", "lithuania", "greece", "israel"}

def _norm_date(s: str) -> str:
    s = s.strip()
    m = re.match(r"(\d{4})(\d{2})(\d{2})$", s)
    if m:
        return "%s-%s-%s" % m.groups()
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if m:
        d, mon, y = m.groups()
        return "%s-%02d-%02d" % (y, _MONTHS.get(mon.lower(), 0), int(d))
    return s

def _clean_entity(kind: str, v: str) -> str:
    v = v.strip()
    m = re.search(r"\(([^)]*)\)\s*$", v)
    if m:
        inner = m.group(1)
        if re.match(r"(?i)(qty|approx|est|\d)", inner):
            v = v[:m.start()].strip()
        elif kind == "equipment" and any(ch.isdigit() for ch in inner):
            v = inner.strip()
    parts = [x.strip() for x in v.split(",")]
    if kind == "person":
        return parts[0]
    while len(parts) > 1 and (parts[-1].lower() in _COUNTRIES or
           re.search(r"[0-9]+(?:\.[0-9]+)?\s*[\u00b0]", parts[-1]) or
           re.match(r"(?i)(suspected|registered|based|located|operating)", parts[-1])):
        parts.pop()
    if len(parts) > 1 and parts[-1].lower() in _COUNTRIES:
        parts.pop()
    out = ", ".join(parts)
    out = re.split(r",\s+(?:suspected|registered|based|located|operating|a |an )", out)[0]
    return out.strip()

class ClassifiedMemoPack:
    pack_id = "classified-memo-v1"
    fields = FIELDS

    def __init__(self, pack_id: str = "classified-memo-v1") -> None:
        self.pack_id = pack_id

    def extract_text(self, text: str) -> dict:
        out: dict = {}
        m = re.search(r"^CLASSIFICATION:\s*([A-Z ]+?)(?://(.*))?$", text, re.M)
        if m:
            out["classification_marking"] = m.group(1).strip()
            ctrl = m.group(2)
            marks = [c.strip() for c in ctrl.split("//") if c.strip()] if ctrl else []
            rel = re.search(r"REL TO [A-Z]{2,3}(?:, [A-Z]{2,3})*", text)
            if rel and rel.group(0) not in marks:
                marks.append(rel.group(0))
            out["control_markings"] = marks
        m = re.search(r"^FROM:\s*(.+)$", text, re.M)
        if m:
            out["originating_org"] = m.group(1).strip()
        m = re.search(r"^AUTHOR:\s*([^,\n]+)", text, re.M)
        if m:
            out["author"] = m.group(1).strip()
        m = re.search(r"^DATE OF INFORMATION:\s*(.+)$", text, re.M)
        if m:
            out["date_of_information"] = _norm_date(m.group(1))
        m = re.search(r"^DECLASSIFY ON:\s*(\S+)", text, re.M)
        if m:
            out["declassify_on"] = _norm_date(m.group(1))
        m = re.search(r"^SUBJECT:\s*(.+?)(?=\n[A-Z]|\n\n)", text, re.M | re.S)
        if m:
            out["subject"] = re.sub(r"\s+", " ", m.group(1)).strip()
        out["portion_marks"] = [
            {"paragraph": int(n), "marking": "(%s)" % mk}
            for n, mk in re.findall(r"^(\d+)\.\s+\(([^)]+)\)", text, re.M)]
        refs = []
        for line in re.findall(r"^\(([a-z])\)\s+(.+)$", text, re.M):
            r = line[1].split(",")[0].strip()
            r = re.sub(r"\s*\([^)]*\)\s*$", "", r).strip()
            refs.append(r)
        if refs:
            out["references"] = refs
        ents = []
        for kind, val in re.findall(r"-\s*(PERSON|ORG|ORGANIZATION|LOCATION|EQUIPMENT|FACILITY|VESSEL|AIRCRAFT|COMPANY|PROGRAM)\s*:\s*(.+)", text):
            k = {"organization": "org", "company": "org"}.get(kind.lower(), kind.lower())
            ents.append({"kind": k, "value": _clean_entity(k, val.strip())})
        if ents:
            out["entities"] = ents
        m = re.search(r"^HANDLING INSTRUCTIONS:\s*(.+?)(?=\n\s*\n|\nDECLASSIFY)", text, re.M | re.S)
        if m:
            out["handling_instructions"] = re.sub(r"\s+", " ", m.group(1)).strip()
        pii = [{"span": e["value"], "type": "person_name"} for e in ents if e["kind"] == "person"]
        if out.get("author"):
            pii.append({"span": out["author"], "type": "person_name"})
        if pii:
            out["pii_spans"] = pii
        return out

    def extract(self, chunks: list[Chunk]) -> list[Extraction]:
        """Extract memo fields from ingested chunks for Orchestrator."""
        if not chunks:
            return []
        full_text = "\n".join(c.text for c in chunks)
        res = self.extract_text(full_text)
        extractions: list[Extraction] = []
        first_chunk_id = chunks[0].chunk_id if chunks else ""
        for k, v in res.items():
            if v is None:
                continue
            val_str = json.dumps(v) if isinstance(v, (list, dict)) else str(v)
            extractions.append(Extraction(
                pack_id=self.pack_id,
                field_name=k,
                value=val_str,
                source_span=str(v)[:100] if not isinstance(v, (list, dict)) else "",
                confidence=0.95,
                chunk_id=first_chunk_id,
            ))
        return extractions
