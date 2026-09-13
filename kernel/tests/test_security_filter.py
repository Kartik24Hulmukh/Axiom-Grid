"""
Tests for LocalSecurityFilter.
"""

import json
from pathlib import Path

from kernel.sidecar.security_filter import LocalSecurityFilter


def test_clean_text_passes():
    """Test that normal, clean text passes the security filter."""
    security = LocalSecurityFilter(enable_pii_scan=True)
    result = security.scan("This is a normal sentence discussing document classification.")
    assert not result.blocked
    assert len(result.reasons) == 0


def test_pii_detection():
    """Test that various forms of PII are detected and scanned."""
    security = LocalSecurityFilter(enable_pii_scan=True)

    # SSN
    res1 = security.scan("My SSN is 123-45-6789.")
    assert res1.blocked
    assert any("ssn" in reason.lower() for reason in res1.reasons)

    # Email
    res2 = security.scan("Contact me at user@example.com.")
    assert res2.blocked
    assert any("email" in reason.lower() for reason in res2.reasons)

    # Phone
    res3 = security.scan("Call 123-456-7890 for details.")
    assert res3.blocked
    assert any("phone" in reason.lower() for reason in res3.reasons)

    # Name
    res4 = security.scan("This document is authorized by Jane Doe.")
    assert res4.blocked
    assert any("name" in reason.lower() for reason in res4.reasons)


def test_pii_redaction():
    """Test that redact_pii correctly redacts PII fields."""
    security = LocalSecurityFilter(enable_pii_scan=True)
    raw_text = "John Smith (email: john@gmail.com, phone: 555-123-4567, SSN: 000-12-3456) is here."
    redacted = security.redact_pii(raw_text)
    
    assert "[NAME_REDACTED]" in redacted
    assert "[EMAIL_REDACTED]" in redacted
    assert "[PHONE_REDACTED]" in redacted
    assert "[SSN_REDACTED]" in redacted
    assert "john@gmail.com" not in redacted
    assert "555-123-4567" not in redacted
    assert "000-12-3456" not in redacted
    assert "John Smith" not in redacted


def test_injection_corpus():
    """Test that all prompt injection payloads in injection_corpus.json are blocked."""
    security = LocalSecurityFilter(enable_pii_scan=False)
    corpus_path = Path(__file__).parents[2] / "fixtures" / "injection_corpus.json"
    
    with open(corpus_path, "r", encoding="utf-8") as f:
        corpus = json.load(f)

    for item in corpus:
        payload = item["payload"]
        result = security.scan(payload)
        assert result.blocked, f"Failed to block payload {item['id']}: {payload}"
        assert any("INJECTION_BLOCKED" in reason for reason in result.reasons)
