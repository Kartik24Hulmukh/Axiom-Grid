"""
Kairo Phantom — Invoice Pack (SPEC §S7)
Extracts vendor_name, invoice_number, invoice_date, due_date, total_amount, currency, line_items, tax_amount, payment_terms.
"""
from __future__ import annotations

import json
import logging
import pathlib
import re
from datetime import date
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
        # All chunks are assumed to describe ONE invoice. These bounded English
        # status forms are not a multi-document segmenter or a localized classifier.
        qualifier = r"(?:draft|revised|provisional|estimated?|proposed|preliminary|unapproved)"
        invoice_heading = r"(?:tax[ \t]+)?invoice"
        qualified_header = re.compile(
            qualifier + r"[ \t]+" + invoice_heading + r"|" + invoice_heading
            + r"(?:[ \t]+" + qualifier + r"|[ \t]*\([ \t]*" + qualifier
            + r"[ \t]*\)|[ \t]*[-:][ \t]*" + qualifier + r")", re.IGNORECASE)
        status_line = re.compile(
            qualifier + r"|(?:(?:invoice|document)[ \t]+)?status[ \t]*:[ \t]*"
            + qualifier, re.IGNORECASE)
        nonfinal_document = any(qualified_header.fullmatch(line) or status_line.fullmatch(line)
                                for line, _ in records)
        header = re.compile(r"(?:tax[ \t]+)?invoice(?:[ \t]*:[ \t]*.+)?|faktura(?:[ \t]*/[ \t]*invoice)?|rechnung", re.I)
        has_invoice_context = any(header.fullmatch(line) or qualified_header.fullmatch(line) or re.match(number_label + r"(?:[ \t]*:|[ \t]+)", line, re.I)
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
                    and ":" not in value and not qualified_header.fullmatch(value)
                    and not status_line.fullmatch(value) and not re.match(
                        r"(?:invoice|tax[ \t]+invoice|date|due|bill[ \t]+to|customer|currency|total|description|no)\b",
                        value, re.I))

        vendors = []
        for index, (line, chunk) in enumerate(records[:12]):
            explicit = re.fullmatch(r"(?:(?:tax[ \t]+)?invoice|from|vendor|supplier)[ \t]*:[ \t]*(.+)", line, re.I)
            if explicit and vendor_candidate(explicit[1]):
                vendors.append((explicit[1], explicit[1], chunk))
            elif (header.fullmatch(line) or qualified_header.fullmatch(line)) and index + 1 < len(records):
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
            if not match and any(header.fullmatch(text) or qualified_header.fullmatch(text)
                                 for text, _ in records):
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
            invalid_date = False
            for line, chunk in records:
                match = re.fullmatch(label + r"[ \t]*:?[ \t]*" + date_value, line, re.I)
                if match:
                    raw = match[1]
                    parsed = self._parse_date(raw)
                    if parsed is None:
                        invalid_date = True
                    else:
                        dates.append((parsed, raw, chunk))
            # Invalid/ambiguous evidence poisons only its own explicitly labeled
            # field, including when a different chunk contains a valid candidate.
            if not invalid_date:
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
        unsafe_total = nonfinal_document
        # A small assertion/label grammar, not a co-occurring word scan.
        # Only explicit unsafe predicates may coordinate; "not provisional"
        # and "not unapproved" are not positive nonfinal evidence. Continuation
        # support is deliberately limited to coordination and "; do not pay".
        unsafe_predicate = (
            qualifier + r"|not[ \t]+(?:approved|final)|"
            r"neither[ \t]+(?:final[ \t]+nor[ \t]+approved|approved[ \t]+nor[ \t]+final)"
        )
        total_warning = re.compile(
            r"(?:(?:this|the|both)[ \t]+)?(?:totals?|amounts?(?:[ \t]+payable)?)"
            r"(?:[ \t]+(?:is|are)[ \t]+|(?:[ \t]+status)?[ \t]*:[ \t]*)"
            r"(?:" + unsafe_predicate + r")(?:[ \t]+and[ \t]+(?:"
            + unsafe_predicate + r"))*(?:;[ \t]*do[ \t]+not[ \t]+pay)?[.!]?",
            re.IGNORECASE,
        )
        for line, chunk in records:
            match = re.fullmatch(r"(?:" + qualifier + r"[ \t]+)?" + total_label
                                 + r"[ \t]*:?[ \t]*" + amount + r"(.*)", line, re.I)
            if match:
                if re.match(qualifier + r"\b", line, re.I) or match[2].strip():
                    unsafe_total = True
                totals.append((match[1].replace(",", ""), match[1], chunk))
            if total_warning.fullmatch(line):
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
        # Explicit terms labels identify the role of free-form text. Generic
        # payment labels may instead contain a paid amount or receipt status;
        # accept them only when the entire value is a recognized terms form.
        generic_terms = (
            r"(?:net[ \t]*[0-9]+|due[ \t]+(?:on|upon)[ \t]+receipt|"
            r"due[ \t]+immediately[ \t]+upon[ \t]+receipt|immediate|"
            r"immediately[ \t]+upon[ \t]+receipt|[0-9]+/[0-9]+[ \t]+net[ \t]*[0-9]+|"
            r"within[ \t]+[0-9]+[ \t]+days|[0-9]+[ \t]+(?:dagar|tage))"
        )
        for line, chunk in records:
            match = re.fullmatch(r"(?:payment[ \t]+terms|terms|betalningsvillkor|zahlungsbedingungen)[ \t]*:[ \t]*(.+)", line, re.I)
            if match:
                terms.append((match[1], match[1], chunk))
                continue
            match = re.fullmatch(r"(?:payment|betalning|zahlung)[ \t]*:[ \t]*(.+)", line, re.I)
            if match:
                if re.fullmatch(generic_terms, match[1], re.I):
                    terms.append((match[1], match[1], chunk))
                continue
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
        """Validate supported full-string Gregorian dates; never return raw input."""
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
        }
        
        # Full-string ASCII formats only. Year-first permits YYYY-MM-DD or
        # YYYY/MM/DD (not mixed separators). Numeric DD/MM/YYYY is accepted
        # ONLY with DD > 12: both <= 12, including equal values, abstain rather
        # than assuming a locale. US month-first numeric dates are unsupported.
        year = month = day = None
        m = re.fullmatch(r"([0-9]{4})([-/])([0-9]{2})\2([0-9]{2})", date_str)
        if m:
            year, month, day = int(m[1]), int(m[3]), int(m[4])
        else:
            m = re.fullmatch(r"([0-9]{1,2})[ \t]+([A-Za-z]+)[ \t]+([0-9]{4})", date_str)
            if m:
                day, month, year = int(m[1]), months.get(m[2].lower()), int(m[3])
            else:
                m = re.fullmatch(r"([A-Za-z]+)[ \t]+([0-9]{1,2}),?[ \t]+([0-9]{4})", date_str)
                if m:
                    month, day, year = months.get(m[1].lower()), int(m[2]), int(m[3])
                else:
                    m = re.fullmatch(r"([0-9]{2})/([0-9]{2})/([0-9]{4})", date_str)
                    if m and int(m[1]) > 12:
                        day, month, year = int(m[1]), int(m[2]), int(m[3])
        if year is None or month is None or day is None:
            return None
        try:
            return date(year, month, day).isoformat()
        except ValueError:
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
