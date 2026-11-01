"""Bounded synthetic calendar/status evidence checks; no models or benchmarks."""
import pytest

from kernel.core.data_model import BBox, Chunk
from packs.invoice.pack import InvoicePack


def extract(*texts):
    chunks = [Chunk(chunk_id=f"calendar-status-{i}", text=text, page=i + 1,
                    bbox=BBox(0, 0, 1, 1)) for i, text in enumerate(texts)]
    result = {e.field_name: e for e in InvoicePack().extract(chunks)}
    for entry in result.values():
        source = next(c for c in chunks if c.chunk_id == entry.chunk_id)
        assert entry.source_span
        assert entry.source_span in source.text
    return result


VALID_DATES = [
    ("2024-02-29", "2024-02-29"), ("2000/02/29", "2000-02-29"),
    ("2026-12-31", "2026-12-31"), ("0001-01-01", "0001-01-01"),
    ("9999-12-31", "9999-12-31"), ("29 February 2024", "2024-02-29"),
    ("February 29, 2000", "2000-02-29"), ("Feb 28 1900", "1900-02-28"),
    ("10 June 2026", "2026-06-10"), ("jUn 10, 2026", "2026-06-10"),
    ("13/04/2026", "2026-04-13"), ("31/12/2026", "2026-12-31"),
]
INVALID_DATES = [
    "2025-02-29", "1900-02-29", "2100-02-29", "2026-04-31",
    "2026-00-10", "2026-13-10", "2026-01-00", "2026-01-32",
    "0000-01-01", "2026/02-28", "2026-02/28", "31 April 2026",
    "February 29, 2025", "29 Feb 1900", "0 June 2026", "32 June 2026",
    "10 Smarch 2026", "Smarch 10, 2026", "03/04/2026", "04/03/2026",
    "12/12/2026", "01/01/2026", "04/13/2026", "31/04/2026", "00/04/2026",
]


@pytest.mark.parametrize("raw,expected", VALID_DATES)
@pytest.mark.parametrize("field,label", [("invoice_date", "Invoice Date"), ("due_date", "Due Date")])
def test_valid_calendar_dates_keep_literal_evidence(raw, expected, field, label):
    assert InvoicePack._parse_date(raw) == expected
    result = extract("INVOICE\nVendor: Copper Finch Repair", f"{label}: {raw}")
    assert result[field].value == expected
    assert result[field].source_span == raw
    assert result[field].chunk_id == "calendar-status-1"
    assert ({"invoice_date", "due_date"} - {field}).isdisjoint(result)


@pytest.mark.parametrize("raw", INVALID_DATES)
@pytest.mark.parametrize("field,label", [("invoice_date", "Invoice Date"), ("due_date", "Due Date")])
def test_invalid_or_ambiguous_date_poison_is_role_local(raw, field, label):
    assert InvoicePack._parse_date(raw) is None
    other = "Due Date" if field == "invoice_date" else "Invoice Date"
    other_field = "due_date" if field == "invoice_date" else "invoice_date"
    result = extract("INVOICE", f"{label}: {raw}", f"{other}: 2026-06-10")
    assert field not in result
    assert result[other_field].value == "2026-06-10"
    assert result[other_field].chunk_id == "calendar-status-2"


@pytest.mark.parametrize("raw", INVALID_DATES)
@pytest.mark.parametrize("label,field", [("Date", "invoice_date"), ("Payment Due", "due_date")])
@pytest.mark.parametrize("reverse", [False, True])
def test_bad_evidence_cannot_be_dropped_for_valid_candidate(raw, label, field, reverse):
    texts = [f"{label}: {raw}", f"{label}: 2026-06-10"]
    if reverse:
        texts.reverse()
    assert field not in extract("INVOICE", *texts)


@pytest.mark.parametrize("raw", [
    "2026-06-10 garbage", "2026-06-10T12:00:00", "10 June 2026 extra",
    "June 10, 2026 extra", " 2026-06-10", "2026-06-10\n", "２０２６-０６-１０",
])
def test_parser_requires_complete_ascii_date(raw):
    assert InvoicePack._parse_date(raw) is None


@pytest.mark.parametrize("label,field", [("Issued", "invoice_date"), ("Due", "due_date")])
def test_different_valid_dates_abstain_and_equivalent_dates_agree(label, field):
    assert field not in extract("INVOICE", f"{label}: 2026-06-10", f"{label}: 2026-06-11")
    result = extract("INVOICE", f"{label}: 10 June 2026", f"{label}: 2026-06-10")
    assert result[field].value == "2026-06-10"
    assert result[field].source_span == "10 June 2026"
    assert result[field].chunk_id == "calendar-status-1"


STATUSES = [
    "DRAFT", "PROVISIONAL", "ESTIMATE", "ESTIMATED", "PROPOSED", "PRELIMINARY",
    "UNAPPROVED", "REVISED", "DRAFT INVOICE", "PROVISIONAL INVOICE",
    "DRAFT TAX INVOICE", "Invoice (Draft)", "Tax Invoice (Provisional)",
    "Invoice Draft", "Invoice - Draft", "Invoice: Draft", "Status: Draft",
    "Invoice Status: Provisional", "Document Status: Draft",
]


@pytest.mark.parametrize("status", STATUSES)
@pytest.mark.parametrize("position", ["before", "between", "after"])
def test_document_status_suppresses_total_across_chunks(status, position):
    texts = ["INVOICE\nVendor: Copper Finch Repair\nInvoice No: C-1", "Total: $120.00"]
    texts.insert({"before": 0, "between": 1, "after": 2}[position], status)
    result = extract(*texts)
    assert "total_amount" not in result
    assert result["vendor_name"].value == "Copper Finch Repair"
    assert result["invoice_number"].value == "C-1"
    assert "payment_terms" not in result
    assert "currency" not in result


@pytest.mark.parametrize("header", ["DRAFT INVOICE", "PROVISIONAL INVOICE", "Invoice (Draft)",
                                     "Invoice: Draft", "Draft Tax Invoice"])
def test_qualified_header_alone_supplies_context_not_vendor(header):
    result = extract(header, "Copper Finch Repair", "Number: C-1\nDate: June 10, 2026", "Total: 120.00")
    assert result["vendor_name"].value == "Copper Finch Repair"
    assert result["vendor_name"].chunk_id == "calendar-status-1"
    assert result["invoice_number"].value == "C-1"
    assert result["invoice_date"].value == "2026-06-10"
    assert "total_amount" not in result


@pytest.mark.parametrize("status", STATUSES)
@pytest.mark.parametrize("final_first", [False, True])
def test_final_cannot_override_nonfinal_evidence(status, final_first):
    statuses = ["Status: FINAL", status] if final_first else [status, "Status: FINAL"]
    assert "total_amount" not in extract("INVOICE", *statuses, "Total: 120.00")


@pytest.mark.parametrize("text", [
    "Vendor: Draft Works Ltd", "Vendor: Estimate Services", "Vendor: Draft Total Works Ltd",
    "- Draft total illustration $20.00", "Description: estimate total preparation",
    "Drafting services 1 20.00 20.00", "Please draft the total summary for our records.",
    "This estimate includes a total for review.", "The word provisional appears in the item description.",
    "Status: Not Draft", "Status: Not Provisional", "Not a draft invoice", "FINAL INVOICE",
    "Status: FINAL", "This total is not unapproved.", "This total is not provisional.",
    "This total is not drafted.", "Invoice Status: Drafting complete",
])
def test_incidental_words_and_negations_are_not_document_status(text):
    result = extract("INVOICE\nInvoice No: C-1", text, "Total: $120.00")
    assert result["total_amount"].value == "120.00"
    assert result["total_amount"].source_span == "120.00"
    assert result["total_amount"].chunk_id == "calendar-status-2"


def test_status_without_invoice_context_cannot_create_obligations():
    assert extract("DRAFT", "Total: 120.00") == {}


TOTAL_WARNINGS = [
    "This amount is provisional.",
    "Amount is not approved.",
    "Amount is not final.",
    "This total is provisional and not approved.",
    "Total is provisional; do not pay.",
    "Total: provisional",
    "Total status: provisional",
    "This total is neither final nor approved.",
]


@pytest.mark.parametrize("warning", TOTAL_WARNINGS)
@pytest.mark.parametrize("layout", ["same_chunk", "before_total", "after_total"])
def test_explicit_amount_total_warnings_suppress_payable(warning, layout):
    context = "INVOICE\nVendor: Copper Finch Repair\nInvoice No: C-1"
    total = "Total: 120.00"
    if layout == "same_chunk":
        texts = [context, f"{total}\n{warning}"]
    elif layout == "before_total":
        texts = [context, warning, total]
    else:
        texts = [context, total, warning]
    result = extract(*texts)
    assert "total_amount" not in result
    assert result["vendor_name"].value == "Copper Finch Repair"
    assert result["vendor_name"].chunk_id == "calendar-status-0"
    assert result["invoice_number"].value == "C-1"
    assert "payment_terms" not in result
    assert "currency" not in result


@pytest.mark.parametrize("text", [
    "This amount is not provisional.",
    "Amount is not unapproved.",
    "Amount is not drafted.",
    "This total is not provisional and not unapproved.",
    "Total: not provisional",
    "Total status: not provisional",
    "Total status: not unapproved",
    "Total is final and approved.",
    "This amount is final.",
    "This total is neither provisional nor unapproved.",
    "Vendor: Total Provisional Services Ltd",
    "Vendor: Amount Not Approved Ltd",
    "Description: This amount is provisional.",
    "Item: Total is provisional; do not pay.",
    "- This amount is provisional. 120.00",
    "Notes: This total is neither final nor approved.",
    "Please check whether this amount is provisional.",
    "This amount is provisionally approved.",
    "Total status: provisional analysis services",
    "This total is provisional wording in a training example.",
])
@pytest.mark.parametrize("layout", ["same_chunk", "before_total", "after_total"])
def test_total_warning_grammar_excludes_negations_and_incidental_text(text, layout):
    total = "Total: 120.00"
    if layout == "same_chunk":
        texts, total_chunk = [f"{text}\n{total}"], "calendar-status-1"
    elif layout == "before_total":
        texts, total_chunk = [text, total], "calendar-status-2"
    else:
        texts, total_chunk = [total, text], "calendar-status-1"
    result = extract("INVOICE\nInvoice No: C-1", *texts)
    assert result["total_amount"].value == "120.00"
    assert result["total_amount"].source_span == "120.00"
    assert result["total_amount"].chunk_id == total_chunk
