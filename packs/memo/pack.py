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

_MON3 = {m[:3]: i + 1 for i, m in enumerate(["january","february","march","april","may","june","july","august","september","october","november","december"])}

# Wave 5 (AI-002): label-synonym invariance. Measured adversarial F1 0.607 -> see
# packs/memo/eval_adversarial.py. Aliases are normalised (upper, no punctuation).
ALIASES = {
    "originating_org": ["FROM", "ORIGINATOR", "ORIGINATING OFFICE", "ORIGINATING ORGANIZATION",
                         "ORIGINATING ORG", "OFFICE OF ORIGIN", "ORIGIN", "ISSUING OFFICE", "ISSUED BY"],
    "author": ["AUTHOR", "PREPARED BY", "DRAFTED BY", "WRITTEN BY", "ANALYST", "AUTHORED BY"],
    "date_of_information": ["DATE OF INFORMATION", "DATE OF INFO", "INFO AS OF", "INFORMATION AS OF",
                             "INFO CUTOFF", "INFORMATION CUTOFF", "AS OF", "AS OF DATE", "DTG", "DATE"],
    "declassify_on": ["DECLASSIFY ON", "DECLASS ON", "DECLASSIFY", "DECLASSIFICATION DATE",
                       "DECLASSIFICATION", "DECLASSIFY NOT LATER THAN"],
    "subject": ["SUBJECT", "SUBJ", "TOPIC", "RE", "TITLE"],
    "handling_instructions": ["HANDLING INSTRUCTIONS", "HANDLING", "HANDLING CAVEATS",
                               "SPECIAL HANDLING", "HANDLING NOTES", "DISSEMINATION INSTRUCTIONS"],
    "references": ["REFERENCES", "REFERENCE", "REFS", "SOURCES CONSULTED", "SOURCES",
                    "SOURCE REFERENCES", "ENCLOSURES", "RELATED REPORTING"],
}
_LABEL_OF = {a: f for f, al in ALIASES.items() for a in al}
_LABEL_RE = re.compile(r"^\s{0,4}([A-Z][A-Z /&\-]{1,40}?)\s*:\s*(.*)$")


def _norm_label(s: str) -> str:
    return re.sub(r"[^A-Z ]", " ", s.upper()).strip().replace("  ", " ")



_FUZZY = [("DECLASS", "declassify_on"), ("DOWNGRAD", "declassify_on"), ("HANDLING", "handling_instructions"),
          ("DISSEMINATION", "handling_instructions"), ("CAVEAT", "handling_instructions"),
          ("ORIGINAT", "originating_org"), ("PREPARED", "author"), ("DRAFTED", "author"),
          ("SUBJECT", "subject"), ("TOPIC", "subject"), ("REFERENC", "references"), ("SOURCES", "references"),
          ("INFO AS OF", "date_of_information"), ("DATE OF INFO", "date_of_information"),
          ("AS OF", "date_of_information"), ("DTG", "date_of_information"), ("DATE", "date_of_information")]


def _resolve_label(lbl: str):
    """Exact alias first, then fuzzy keyword match (label-synonym invariance, AI-002)."""
    n = _norm_label(lbl)
    if n in _LABEL_OF:
        return _LABEL_OF[n]
    if n.startswith("CLASSIFICATION") or n == "CLASS":
        return None
    for kw, field in _FUZZY:
        if kw in n:
            return field
    return None


def parse_header_blocks(text: str) -> dict:
    """Label -> value, tolerant of synonyms, reordering and wrapped continuation lines."""
    blocks: dict[str, str] = {}
    cur = None
    buf: list[str] = []
    for raw in text.split("\n"):
        m = _LABEL_RE.match(raw)
        label = _resolve_label(m.group(1)) if m else None
        if m and label:
            if cur and cur not in blocks:
                blocks[cur] = " ".join(x.strip() for x in buf).strip()
            cur, buf = label, [m.group(2)]
        elif m and _norm_label(m.group(1)) not in ("",):
            if cur and cur not in blocks:
                blocks[cur] = " ".join(x.strip() for x in buf).strip()
            cur, buf = None, []
        elif cur is not None:
            if not raw.strip() or re.match(r"^\s*(?:\d+|[A-Z])[.)]\s", raw):
                blocks.setdefault(cur, " ".join(x.strip() for x in buf).strip())
                cur, buf = None, []
            else:
                buf.append(raw)
    if cur and cur not in blocks:
        blocks[cur] = " ".join(x.strip() for x in buf).strip()
    return {k: re.sub(r"\s+", " ", v).strip() for k, v in blocks.items() if v.strip()}



def _norm_date(s: str) -> str:
    s = s.strip().strip(".")
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})$", s)
    if m:
        return s
    m = re.match(r"(\d{4})(\d{2})(\d{2})$", s)
    if m:
        return "%s-%s-%s" % m.groups()
    m = re.match(r"(?i)(\d{1,2})\s+([A-Za-z]{3,})\.?\s+(\d{2,4})", s)
    if m:
        d, mon, y = m.groups()
        mo = _MONTHS.get(mon.lower()) or _MON3.get(mon.lower()[:3], 0)
        y = int(y)
        if y < 100:
            y += 2000 if y <= 30 else 1900
        return "%04d-%02d-%02d" % (y, mo, int(d))
    m = re.match(r"(?i)([A-Za-z]{3,})\.?\s+(\d{1,2}),?\s+(\d{4})", s)
    if m:
        mon, d, y = m.groups()
        mo = _MONTHS.get(mon.lower()) or _MON3.get(mon.lower()[:3], 0)
        return "%s-%02d-%02d" % (y, mo, int(d))
    m = re.match(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", s)
    if m:
        d, mo, y = m.groups()
        return "%s-%02d-%02d" % (y, int(mo), int(d))
    m = re.search(r"(\d{6})Z?\s*([A-Z]{3})\s*(\d{2})", s)
    if m:
        dd, mon, yy = m.groups()
        return "%04d-%02d-%02d" % (2000 + int(yy) if int(yy) <= 30 else 1900 + int(yy), _MON3.get(mon.lower(), 0), int(dd[:2]))
    return s

_CORP = re.compile(r"(?i)\b(company|corp|corporation|inc|llc|ltd|limited|gmbh|group|solutions|technologies|holdings|industries|shipping|trading|enterprises|systems|ag|sa|bv|plc)\b\.?$")


def _strip_trailing_place(kind: str, v: str) -> str:
    """AI-002: drop a trailing city/place appended to an org or facility name."""
    if kind not in ("org", "facility", "location"):
        return v
    parts = [x.strip() for x in v.split(",")]
    while len(parts) > 1:
        tail = parts[-1]
        head = ", ".join(parts[:-1])
        if (kind != "location" and len(tail.split()) <= 3 and not _CORP.search(tail)
                and tail[:1].isupper() and _CORP.search(head)):
            parts.pop()
            continue
        break
    return ", ".join(parts)


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
    out = re.sub(r"(?i),\s*(?:qty|quantity|approx|approximately|est|x)\.?\s*\d+.*$", "", out)
    return _strip_trailing_place(kind, out.strip())

class ClassifiedMemoPack:
    pack_id = "classified-memo-v1"
    fields = FIELDS

    def __init__(self, pack_id: str = "classified-memo-v1") -> None:
        self.pack_id = pack_id

    def extract_text(self, text: str) -> dict:
        out: dict = {}
        hdr = parse_header_blocks(text)
        m = re.search(r"^\s*(?:CLASSIFICATION|CLASSIFICATION LEVEL|CLASS)\s*:\s*([A-Z ]+?)(?://(.*))?$", text, re.M)
        if not m:
            m = re.search(r"^\s*(TOP SECRET|SECRET|CONFIDENTIAL|UNCLASSIFIED)(?://(.*))?$", text, re.M)
        if m:
            out["classification_marking"] = m.group(1).strip()
            ctrl = m.group(2)
            marks = [c.strip() for c in ctrl.split("//") if c.strip()] if ctrl else []
            rel = re.search(r"REL TO [A-Z]{2,3}(?:, [A-Z]{2,3})*", text)
            if rel and rel.group(0) not in marks:
                marks.append(rel.group(0))
            out["control_markings"] = marks
        if hdr.get("originating_org"):
            out["originating_org"] = re.sub(r"\s+\(", " (", hdr["originating_org"]).strip()
        if hdr.get("author"):
            out["author"] = hdr["author"].split(",")[0].strip()
        if hdr.get("date_of_information"):
            out["date_of_information"] = _norm_date(hdr["date_of_information"])
        if hdr.get("declassify_on"):
            dv = hdr["declassify_on"]
            dm = re.search(r"(\d{8}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]{3,}\.?\s+\d{2,4}|[A-Za-z]{3,}\.?\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{4})", dv)
            out["declassify_on"] = _norm_date(dm.group(1)) if dm else _norm_date(dv)
        if hdr.get("subject"):
            out["subject"] = hdr["subject"]
        if hdr.get("handling_instructions"):
            out["handling_instructions"] = hdr["handling_instructions"]
        marks = re.findall(r"^\s*(?:\(?(?:\d{1,2}|[A-Z]|[ivxIVX]{1,4})\)?[.)])\s+\(([A-Z][A-Z/ ]{0,20})\)", text, re.M)
        if marks:
            out["portion_marks"] = [{"paragraph": i + 1, "marking": "(%s)" % mk.strip()}
                                    for i, mk in enumerate(marks)]
        refs = []
        for _lbl, body in re.findall(r"^\s*\(([a-z])\)\s+(.+(?:\n\s{2,}.+)*)$", text, re.M):
            r = re.sub(r"\s+", " ", body).split(",")[0].strip()
            r = re.sub(r"\s*\([^)]*\)\s*$", "", r).strip()
            refs.append(r)
        if refs:
            out["references"] = refs
        ents = []
        ent_re = re.compile(r"^\s*(?:[-*\u2022\u00b7o]|\d+[.)])?\s*(PERSON|ORG|ORGANIZATION|LOCATION|LOC|EQUIPMENT|EQPT|FACILITY|VESSEL|AIRCRAFT|COMPANY|PROGRAM)\s*:\s*(.+(?:\n\s{4,}(?![-*\u2022])\S.*)*)", re.M)
        for kind, val in ent_re.findall(text):
            k = {"organization": "org", "company": "org", "loc": "location", "eqpt": "equipment"}.get(kind.lower(), kind.lower())
            v = re.sub(r"\s+", " ", val).strip()
            ents.append({"kind": k, "value": _clean_entity(k, v)})
        seen = set()
        uniq = []
        for e in ents:
            key = (e["kind"], e["value"])
            if key not in seen:
                seen.add(key)
                uniq.append(e)
        if uniq:
            out["entities"] = uniq
        pii = [{"span": e["value"], "type": "person_name"} for e in uniq if e["kind"] == "person"]
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
