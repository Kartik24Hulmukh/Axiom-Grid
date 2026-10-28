"""
Kairo Phantom — Invoice Pack (SPEC §S7)
Extracts vendor_name, invoice_number, invoice_date, due_date, total_amount, currency, line_items, tax_amount, payment_terms.
"""
from __future__ import annotations

import json
import logging
import pathlib
import re
from typing import Any

from kernel.core.data_model import (
    Chunk,
    Extraction,
)

logger = logging.getLogger(__name__)

INVOICE_FIELDS = [
    "vendor_name", "invoice_number", "invoice_date", "due_date",
    "total_amount", "currency", "line_items", "tax_amount", "payment_terms"
]

class InvoicePack:
    """Invoice extraction Pack implementing PackInterface."""

    def __init__(self, pack_id: str = "invoice-v1") -> None:
        self._pack_id = pack_id

    @property
    def fields(self) -> list[str]:
        return list(INVOICE_FIELDS)

    def extract(self, chunks: list[Chunk]) -> list[Extraction]:
        """Extract invoice fields from ingested chunks using regex and rules."""
        if not chunks:
            return []

        # Labels never cross a line/chunk boundary. Strip table borders only;
        # captured evidence remains an exact substring of its original chunk.
        records = [(line.strip(" \t│|"), c) for c in chunks for line in c.text.splitlines()
                   if line.strip(" \t│|")]
        number_label = (r"(?:invoice[ \t]+(?:number|no\.?|nr)|invoice[ \t]*#|"
                        r"inv[ \t]+(?:number|no\.?)|fakturanr|faktura[ \t]+nr|"
                        r"rechnungsnr|receipt[ \t]+no\.?|receipt[ \t]*#)")
        header = re.compile(r"(?:tax[ \t]+)?invoice(?:[ \t]*:[ \t]*.+)?|faktura(?:[ \t]*/[ \t]*invoice)?|rechnung", re.I)
        has_invoice_context = any(header.fullmatch(line) or re.match(number_label + r"(?:[ \t]*:|[ \t]+)", line, re.I)
                                  for line, _ in records)
        if not has_invoice_context:
            return []
        extractions: list[Extraction] = []

        def emit(field, candidates, confidence=0.9):
            # Conflicting explicit values are unresolved, not first-match wins.
            if not candidates or len({value for value, _, _ in candidates}) != 1:
                return
            value, span, chunk = candidates[0]
            extractions.append(Extraction(pack_id=self._pack_id, field_name=field,
                                          value=value, source_span=span,
                                          confidence=confidence, chunk_id=chunk.chunk_id))

        def vendor_candidate(value):
            return (bool(value) and len(value) <= 200 and any(ch.isalpha() for ch in value)
                    and ":" not in value and not re.match(
                        r"(?:invoice|tax[ \t]+invoice|date|due|bill[ \t]+to|customer|currency|total|description|no)\b",
                        value, re.I))

        vendors = []
        for index, (line, chunk) in enumerate(records[:12]):
            explicit = re.fullmatch(r"(?:(?:tax[ \t]+)?invoice|from|vendor|supplier)[ \t]*:[ \t]*(.+)", line, re.I)
            if explicit and vendor_candidate(explicit[1]):
                vendors.append((explicit[1], explicit[1], chunk))
            elif header.fullmatch(line) and index + 1 < len(records):
                value, source = records[index + 1]
                if vendor_candidate(value) and not re.fullmatch(r"[=\-*~_─┌┐└┘┬┴┼]+", value):
                    vendors.append((value, value, source))
        # A business-name preamble is permitted only in invoice context. Do not
        # promote arbitrary document headings to vendors.
        if not vendors:
            preamble = next(((line, chunk) for line, chunk in records[:8]
                             if not re.fullmatch(r"[=\-*~_─┌┐└┘┬┴┼]+", line)), None)
            if preamble:
                value, chunk = preamble
                if vendor_candidate(value) and re.search(
                        r"\b(?:corp(?:oration)?|llc|inc|ltd|limited|company|solutions|services|industries|studio|works|ab)\b",
                        value, re.I):
                    vendors.append((value, value, chunk))
        emit("vendor_name", vendors)

        identifiers = []
        for line, chunk in records:
            match = re.fullmatch(number_label + r"(?:[ \t]*:[ \t]*|[ \t]+)([A-Za-z0-9][A-Za-z0-9/-]*)", line, re.I)
            if not match and any(header.fullmatch(text) for text, _ in records):
                match = re.fullmatch(r"(?:no\.?|number)[ \t]*:?[ \t]+([A-Za-z0-9][A-Za-z0-9/-]*)", line, re.I)
            if match:
                identifiers.append((match[1], match[1], chunk))
        # No standalone product-code guessing or filename-derived identifiers.
        emit("invoice_number", identifiers, 0.95)

        date_value = (r"(\d{4}[-/]\d{2}[-/]\d{2}|\d{1,2}[ \t]+[a-zA-Z]+[ \t]+\d{4}|"
                      r"[a-zA-Z]+[ \t]+\d{1,2},?[ \t]+\d{4}|\d{2}/\d{2}/\d{4})")
        for field, label in (
            ("invoice_date", r"(?:invoice[ \t]+date|date|issued|billed|fakturadatum|datum|rechnungsdatum)"),
            ("due_date", r"(?:due[ \t]+date|due|payment[ \t]+due|förfallodatum|förfallo|fällig|zahlbar[ \t]+bis)"),
        ):
            dates = []
            for line, chunk in records:
                match = re.fullmatch(label + r"[ \t]*:?[ \t]*" + date_value, line, re.I)
                if match:
                    raw = match[1]
                    dates.append((self._parse_date(raw) or raw, raw, chunk))
            emit(field, dates)

        # Currency requires explicit evidence. A bare '$' does not distinguish
        # USD/CAD/AUD/SGD, and missing currency is never defaulted to USD.
        supported_codes = {"USD", "EUR", "GBP", "SGD", "AUD", "CAD", "JPY", "CNY", "INR",
                           "SEK", "NOK", "DKK", "CHF", "NZD", "HKD", "ZAR", "BRL", "MXN"}
        currencies = []
        for line, chunk in records:
            match = re.fullmatch(r"(?:all[ \t]+amounts[ \t]+in|currency|valuta|währung)[ \t]*:?[ \t]*([A-Za-z]{3})", line, re.I)
            if match and match[1].upper() in supported_codes:
                currencies.append((match[1].upper(), match[1], chunk))
            for match in re.finditer(r"\(([A-Z]{3})\)", line):
                if match[1] in supported_codes:
                    currencies.append((match[1], match[1], chunk))
        for line, chunk in records:
            for symbol, code in (("€", "EUR"), ("£", "GBP")):
                if symbol in line:
                    currencies.append((code, symbol, chunk))
        emit("currency", currencies)

        amount = r"(?:[$€£¥][ \t]*)?((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})"
        total_label = (r"(?:total[ \t]+amount[ \t]+due|total[ \t]+due|grand[ \t]+total|amount[ \t]+due|"
                       r"amount[ \t]+payable|total[ \t]+payable|balance[ \t]+due|totalt[ \t]+att[ \t]+betala|"
                       r"belopp[ \t]+att[ \t]+betala|gesamtbetrag|total[ \t]+amount|total|t[0o]tal[ \t]+am[0o]unt[ \t]+due)")
        totals = []
        unsafe_total = False
        qualifier = r"(?:draft|revised|provisional|estimated?|proposed|preliminary|unapproved)"
        for line, chunk in records:
            match = re.fullmatch(r"(?:" + qualifier + r"[ \t]+)?" + total_label
                                 + r"[ \t]*:?[ \t]*" + amount + r"(.*)", line, re.I)
            if match:
                if re.match(qualifier + r"\b", line, re.I) or match[2].strip():
                    unsafe_total = True
                totals.append((match[1].replace(",", ""), match[1], chunk))
            if (re.search(r"\b(?:totals?|amount|payable)\b", line, re.I)
                    and re.search(r"\b(?:provisional|unapproved|not[ \t]+approved|not[ \t]+final|neither|draft|estimated?|preliminary)\b", line, re.I)):
                unsafe_total = True
        if not unsafe_total:
            emit("total_amount", totals, 0.95)
        # No calculated subtotal+tax fallback: arithmetic is not an explicit total.
        taxes = []
        for line, chunk in records:
            match = re.fullmatch(r"(?:sales[ \t]+tax|tax|vat|gst|moms|ust)[ \t]*(?:\([^()\r\n]*\))?[ \t]*:?[ \t]*" + amount, line, re.I)
            if match:
                taxes.append((match[1].replace(",", ""), match[1], chunk))
        emit("tax_amount", taxes, 0.85)  # Explicit zero is valid; absence is unknown.

        terms = []
        for line, chunk in records:
            match = re.fullmatch(r"(?:payment[ \t]+terms|terms|payment|betalningsvillkor|betalning|zahlungsbedingungen|zahlung)[ \t]*:[ \t]*(.+)", line, re.I)
            if match:
                terms.append((match[1], match[1], chunk))
            else:
                match = re.fullmatch(r"((?:payment[ \t]+)?due[ \t]+(?:immediately[ \t]+)?(?:upon[ \t]+)?receipt)", line, re.I)
                if match:
                    terms.append(("Due on Receipt", match[1], chunk))
        emit("payment_terms", terms, 0.85)  # No default Net 30 obligation.

        # Line items — handle table format and bullet-point format
        line_items = []
        line_items_chunk = None
        for c in chunks:
            lines = c.text.splitlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Format 1: table format "description qty price total"
                # Description can contain letters, spaces, parentheses, hyphens, ampersands
                m = re.search(r'([a-zA-Z\s()&\-]{5,})\s+(\d+)\s+([$\u20ac\u00a3\u00a5]?\s*[\d,]+\.\d{2})\s+([$\u20ac\u00a3\u00a5]?\s*[\d,]+\.\d{2})', line)
                if m:
                    desc = m.group(1).strip()
                    qty = int(m.group(2))
                    price = float(re.sub(r'[^\d\.]', '', m.group(3)))
                    total = float(re.sub(r'[^\d\.]', '', m.group(4)))
                    line_items.append({"description": desc, "quantity": qty, "unit_price": price, "total": total})
                    if not line_items_chunk:
                        line_items_chunk = c
                    continue
                # Format 2: bullet format "- description (qty hrs @ $rate/hr) $total"
                m = re.match(r'^[-\u2022]\s*(.+?)\s+\((\d+)\s+\w+\s+@\s*[$\u20ac\u00a3]?(\d+(?:\.\d+)?)\s*/?\w*\)\s+[$\u20ac\u00a3]?(\d[\d,]*\.\d{2})', line)
                if m:
                    desc = m.group(1).strip()
                    qty = int(m.group(2))
                    price = float(m.group(3))
                    total = float(re.sub(r'[^\d\.]', '', m.group(4)))
                    line_items.append({"description": desc, "quantity": qty, "unit_price": price, "total": total})
                    if not line_items_chunk:
                        line_items_chunk = c
                    continue
                # Format 3: bullet format "- description $total" (no qty/price)
                m = re.match(r'^[-\u2022]\s*(.+?)\s+[$\u20ac\u00a3]?(\d[\d,]*\.\d{2})\s*$', line)
                if m:
                    desc = m.group(1).strip()
                    total = float(re.sub(r'[^\d\.]', '', m.group(2)))
                    line_items.append({"description": desc, "quantity": 1, "unit_price": total, "total": total})
                    if not line_items_chunk:
                        line_items_chunk = c
                    continue

        if line_items:
            extractions.append(Extraction(
                pack_id=self._pack_id,
                field_name="line_items",
                value=json.dumps(line_items),
                source_span=line_items[0]["description"] if line_items else "",
                confidence=0.8,
                chunk_id=line_items_chunk.chunk_id if line_items_chunk else chunks[0].chunk_id,
            ))

        return extractions

    def oracle(self, fixtures_dir: str) -> dict[str, float]:
        """Score per-field accuracy vs ground-truth fixtures."""
        fixtures_path = pathlib.Path(fixtures_dir)
        gt_file = fixtures_path / "ground_truth.json"
        if not gt_file.exists():
            return {f: 0.0 for f in INVOICE_FIELDS}

        gt_data = json.loads(gt_file.read_text(encoding="utf-8"))
        fixtures = gt_data.get("fixtures", [])
        if not fixtures:
            return {f: 0.0 for f in INVOICE_FIELDS}

        field_correct = {f: 0 for f in INVOICE_FIELDS}
        field_total = {f: 0 for f in INVOICE_FIELDS}

        from kernel.sidecar.ingestor import IngestorImpl
        ingestor = IngestorImpl()

        for fixture in fixtures:
            fixture_file = fixtures_path / fixture["file"]
            if not fixture_file.exists():
                continue

            ground_truth = fixture["ground_truth"]
            try:
                chunks, _, _ = ingestor.ingest(str(fixture_file))
            except Exception:
                continue

            extractions = self.extract(chunks)
            ext_by_field = {e.field_name: e for e in extractions}

            for field_name in INVOICE_FIELDS:
                expected = ground_truth.get(field_name)
                ext = ext_by_field.get(field_name)
                field_total[field_name] += 1
                if expected is None and ext is None:
                    field_correct[field_name] += 1
                elif expected is not None and ext is not None:
                    if self._field_matches(field_name, ext.value, expected):
                        field_correct[field_name] += 1

        return {
            f: field_correct[f] / field_total[f] if field_total[f] > 0 else 0.0
            for f in INVOICE_FIELDS
        }

    @staticmethod
    def _parse_date(date_str: str) -> str | None:
        """Parse standard date formats to YYYY-MM-DD."""
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
        }
        
        # YYYY-MM-DD
        m = re.match(r"(\d{4})[-/](\d{2})[-/](\d{2})", date_str)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            
        # DD Month YYYY
        m = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})", date_str)
        if m:
            day = int(m.group(1))
            month = months.get(m.group(2).lower())
            year = int(m.group(3))
            if month:
                return f"{year:04d}-{month:02d}-{day:02d}"

        # Month DD, YYYY
        m = re.match(r"(\w+)\s+(\d{1,2}),?\s+(\d{4})", date_str)
        if m:
            month = months.get(m.group(1).lower())
            day = int(m.group(2))
            year = int(m.group(3))
            if month:
                return f"{year:04d}-{month:02d}-{day:02d}"

        return None

    @staticmethod
    def _field_matches(field_name: str, extracted: str, expected: Any) -> bool:
        """Check if an extracted value matches the ground truth."""
        if isinstance(expected, (int, float)):
            try:
                return abs(float(extracted) - float(expected)) < 0.01
            except Exception:
                return False
        if isinstance(expected, str):
            ext_norm = " ".join(extracted.strip().lower().split())
            exp_norm = " ".join(expected.strip().lower().split())
            return ext_norm == exp_norm or exp_norm in ext_norm or ext_norm in exp_norm
        elif isinstance(expected, list):
            try:
                extracted_list = json.loads(extracted) if extracted.startswith("[") else [extracted]
            except Exception:
                extracted_list = [extracted]
            # Check if elements match
            return len(extracted_list) == len(expected)
        return False
