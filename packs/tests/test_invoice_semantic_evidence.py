"""Direct, synthetic InvoicePack evidence tests; no benchmark/model/network calls."""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from kernel.core.data_model import BBox, Chunk
from packs.invoice.pack import InvoicePack

ROOT = Path(__file__).resolve().parents[2]


def extract(*texts, source_type="text"):
    chunks = [Chunk(chunk_id=f"source-{i}", text=text, source_type=source_type,
                    page=i + 1, bbox=BBox(0, 0, 1, 1)) for i, text in enumerate(texts)]
    result = {entry.field_name: entry for entry in InvoicePack().extract(chunks)}
    # Every emitted field names a real supporting chunk and literal source span.
    for entry in result.values():
        chunk = next(c for c in chunks if c.chunk_id == entry.chunk_id)
        assert entry.source_span
        assert entry.source_span in chunk.text
    return result


def assert_matches(entry, expected):
    if isinstance(expected, (int, float)):
        assert Decimal(entry.value) == Decimal(str(expected))
    elif isinstance(expected, list):
        assert json.loads(entry.value) == expected
    else:
        assert entry.value == expected


NEGATIVE_DIR = ROOT / "fixtures/held_out_negative"
NEGATIVE_CASES = json.loads((NEGATIVE_DIR / "ground_truth.json").read_text())["fixtures"]


@pytest.mark.parametrize("case", NEGATIVE_CASES, ids=lambda case: case["fixture_id"])
def test_existing_negative_evidence_is_absent_or_unambiguous(case):
    result = extract((NEGATIVE_DIR / case["file"]).read_text())
    for field, expected in case["ground_truth"].items():
        if expected is None:
            assert field not in result, (field, result.get(field))
        else:
            assert field in result
            assert_matches(result[field], expected)


POSITIVE_CASES = []
for directory in ("invoice", "held_out", "invoice/partially_scanned", "invoice/merged_cells"):
    root = ROOT / "fixtures" / directory
    for case in json.loads((root / "ground_truth.json").read_text())["fixtures"]:
        POSITIVE_CASES.append((root, case))


@pytest.mark.parametrize("root,case", POSITIVE_CASES, ids=[case["fixture_id"] for _, case in POSITIVE_CASES])
def test_existing_explicit_positive_fields_preserved(root, case):
    result = extract((root / case["file"]).read_text())
    for field, expected in case["ground_truth"].items():
        if expected is not None:
            assert field in result, field
            assert_matches(result[field], expected)


@pytest.mark.parametrize("label", ["Invoice", "Invoice No:", "Invoice Number:", "Invoice #:"])
def test_invoice_number_label_cannot_consume_next_line(label):
    result = extract(f"INVOICE\nNorthstar Binding Studio\n{label}\nNorthstar\n")
    assert "invoice_number" not in result


def test_invoice_filename_and_bare_product_code_do_not_create_identifier():
    result = extract("INVOICE\nNorthstar Binding Studio\nProduct reference AB-2024-1234\n",
                     source_type="inv_1234.txt")
    assert "invoice_number" not in result


@pytest.mark.parametrize("line", ["Due Date: 2026-11-12", "Payment Due: 2026-11-12"])
def test_due_date_is_not_invoice_issue_date(line):
    result = extract("INVOICE\nCopper Finch Repair\n" + line)
    assert "invoice_date" not in result
    assert result["due_date"].value == "2026-11-12"


def test_dates_and_currency_keep_their_own_supporting_chunk():
    result = extract("INVOICE\nVendor: Copper Finch Repair\nInvoice Date: June 10, 2026",
                     "Due Date: July 10, 2026", "Currency: EUR", "Total: €210.00")
    assert result["invoice_date"].chunk_id == "source-0"
    assert result["due_date"].chunk_id == "source-1"
    assert result["currency"].chunk_id == "source-2"
    assert result["total_amount"].chunk_id == "source-3"


@pytest.mark.parametrize("text", ["", "Total: 10.00", "Subtotal: 10.00", "Tax:\n0.00", "Tax rate: 0%"])
def test_absent_or_crossline_tax_is_not_zero(text):
    assert "tax_amount" not in extract("INVOICE\nNorthstar Binding Studio\n" + text)


@pytest.mark.parametrize("text", ["Tax: 0.00", "Tax (0%): $0.00", "VAT: €0.00"])
def test_explicit_zero_tax_is_preserved(text):
    assert extract("INVOICE\nNorthstar Binding Studio\n" + text)["tax_amount"].value == "0.00"


def test_no_default_currency_or_payment_terms():
    result = extract("INVOICE\nNorthstar Binding Studio\nTotal: 10.00")
    assert "currency" not in result
    assert "payment_terms" not in result


def test_dollar_symbol_alone_does_not_establish_usd():
    result = extract("INVOICE\nNorthstar Binding Studio\nTotal: $10.00")
    assert result["total_amount"].value == "10.00"
    assert "currency" not in result


@pytest.mark.parametrize("text", [
    "Total: 120.00\nTotal: 145.00",
    "Draft total: $120.00\nRevised total: $145.00",
    "Total: 120.00 provisional",
    "Total: 120.00\nThis total is not approved.",
    "Provisional total: 120.00",
    "Subtotal: 100.00\nTax: 20.00",
])
def test_ambiguous_provisional_or_calculated_totals_are_not_asserted(text):
    assert "total_amount" not in extract("INVOICE\nNorthstar Binding Studio\n" + text)


def test_conflicting_totals_across_chunks_are_not_first_match_wins():
    result = extract("INVOICE\nNorthstar Binding Studio\nTotal: 120.00", "Total: 145.00")
    assert "total_amount" not in result


def test_identical_repeated_total_evidence_is_unambiguous():
    result = extract("INVOICE\nNorthstar Binding Studio\nTotal: $120.00\nTotal: $120.00")
    assert result["total_amount"].value == "120.00"


def test_amount_evidence_preserves_comma_span():
    result = extract("INVOICE\nNorthstar Binding Studio\nTotal: $1,200.00")
    assert result["total_amount"].value == "1200.00"
    assert result["total_amount"].source_span == "1,200.00"


@pytest.mark.parametrize("field,text", [
    ("invoice_number", "Invoice Number: A-1\nInvoice Number: B-2"),
    ("invoice_date", "Invoice Date: 2026-10-20\nInvoice Date: 2026-10-21"),
    ("tax_amount", "Tax: 1.00\nTax: 2.00"),
    ("currency", "Currency: USD\nCurrency: EUR"),
    ("payment_terms", "Terms: Net 30\nTerms: Net 60"),
])
def test_conflicting_labelled_fields_abstain(field, text):
    assert field not in extract("INVOICE\nNorthstar Binding Studio\n" + text)


def test_field_observation_is_not_an_invoice_vendor_or_default_fields():
    assert extract("FIELD OBSERVATION\nTotal herons counted: 3\nNo payment is requested.") == {}


def test_tax_invoice_short_number_label_and_explicit_currency():
    result = extract("TechFlow Solutions Ltd\nTAX INVOICE\nNo. TF-0892\nAll amounts in SGD\nAmount Payable: 9,483.00")
    assert result["vendor_name"].value == "TechFlow Solutions Ltd"
    assert result["invoice_number"].value == "TF-0892"
    assert result["currency"].value == "SGD"


def test_invoice_hash_label_establishes_context_without_header():
    result = extract("GLOBAL SERVICES INC\nInvoice #: GSI-4471\nGrand Total: 19,063.50")
    assert result["invoice_number"].value == "GSI-4471"
    assert result["vendor_name"].value == "GLOBAL SERVICES INC"


def test_conflicting_currency_symbol_does_not_override_explicit_code():
    assert "currency" not in extract("INVOICE\nNorthstar Binding Studio\nCurrency: USD\nTotal: €10.00")


@pytest.mark.parametrize("label", ["Payment", "Betalning", "Zahlung"])
@pytest.mark.parametrize("value", ["$120.00", "120.00", "EUR 120.00", "Received", "Paid", "Pending",
                                   "Received Net 30", "Net 30 received", "Due on Receipt; paid $120.00"])
def test_generic_payment_amounts_and_statuses_are_not_terms(label, value):
    result = extract(f"INVOICE\nNorthstar Binding Studio\n{label}: {value}")
    assert "payment_terms" not in result


@pytest.mark.parametrize("label", ["Payment", "Betalning", "Zahlung"])
@pytest.mark.parametrize("value", ["Net30", "Net 30", "Due on Receipt", "Due upon receipt", "2/10 Net 30",
                                   "within 14 days"])
def test_generic_payment_recognized_terms_preserved(label, value):
    result = extract(f"INVOICE\nNorthstar Binding Studio\n{label}: {value}")
    assert result["payment_terms"].value == value
    assert result["payment_terms"].source_span == value


@pytest.mark.parametrize("label,value", [("Betalning", "30 dagar"), ("Zahlung", "30 Tage")])
def test_translated_generic_payment_duration_terms(label, value):
    assert extract(f"INVOICE\nNorthstar Binding Studio\n{label}: {value}")["payment_terms"].value == value


@pytest.mark.parametrize("label", ["Payment Terms", "Terms", "Betalningsvillkor", "Zahlungsbedingungen"])
def test_explicit_terms_labels_preserve_freeform_terms(label):
    value = "Half on signing; balance on delivery"
    assert extract(f"INVOICE\nNorthstar Binding Studio\n{label}: {value}")["payment_terms"].value == value


def test_generic_payment_label_cannot_consume_next_line_terms():
    assert "payment_terms" not in extract("INVOICE\nNorthstar Binding Studio\nPayment:\nNet 30")
