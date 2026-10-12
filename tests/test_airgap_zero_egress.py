"""
Tests for airgap_proof.py — P1.2 Air-gap zero-egress proof.

These tests run the air-gap proof and assert zero network egress.
The proof uses REAL socket monkey-patching to intercept any attempted
connection — no mocks on the production path.

Tests verify:
1. A document session completes in air-gap mode with zero egress.
2. Zero DNS lookups occur.
3. If code attempts a connection, it is caught and recorded.
4. The egress monitor blocks real socket calls (not a no-op).
5. The grounding pipeline works correctly under air-gap constraints.
"""
import json
import os
import socket
import sys

import pytest

# Ensure the scripts directory is importable
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from airgap_proof import (
    run_airgap_proof,
    run_airgap_session,
    AirGapEgressMonitor,
    EgressReport,
)


# ---------------------------------------------------------------------------
# Core air-gap proof tests
# ---------------------------------------------------------------------------

def test_airgap_session_zero_egress():
    """A document session in air-gap mode must produce zero network egress."""
    report = run_airgap_proof()
    assert report.session_completed is True, \
        f"Air-gap session did not complete: {report.error}"
    assert report.total_egress == 0, \
        f"VIOLATION: {report.total_egress} egress attempts detected in air-gap mode"
    assert report.zero_egress is True


def test_airgap_session_zero_dns():
    """A document session in air-gap mode must produce zero DNS lookups."""
    report = run_airgap_proof()
    assert report.total_dns == 0, \
        f"VIOLATION: {report.total_dns} DNS lookups detected in air-gap mode"
    assert report.zero_egress is True


def test_airgap_session_completes_successfully():
    """The air-gap session must complete without errors."""
    report = run_airgap_proof()
    assert report.session_completed is True
    assert report.error is None


# ---------------------------------------------------------------------------
# Grounding works under air-gap
# ---------------------------------------------------------------------------

def test_airgap_grounding_produces_anchors():
    """The grounding pipeline must produce anchors in air-gap mode."""
    report = run_airgap_proof()
    assert report.session_completed is True
    # The grounding result is stored on the report
    grounding_result = getattr(report, "grounding_result", None)
    assert grounding_result is not None, "Grounding result not stored in report"
    assert grounding_result["grounded"] is True, \
        "Grounding did not produce a grounded answer"
    assert grounding_result["grounding_anchors"] > 0, \
        "No grounding anchors produced"


def test_airgap_refusal_on_unanswerable():
    """The grounding pipeline must refuse (BLOCK) unanswerable queries in air-gap mode."""
    report = run_airgap_proof()
    assert report.session_completed is True
    grounding_result = getattr(report, "grounding_result", None)
    assert grounding_result is not None
    assert grounding_result["refused"] is True, \
        "Grounding did not refuse an unanswerable query"


# ---------------------------------------------------------------------------
# Egress monitor actually intercepts (not a no-op)
# ---------------------------------------------------------------------------

def test_egress_monitor_catches_real_connection_attempt():
    """The egress monitor must catch a REAL socket connection attempt.

    This proves the monitor is not a no-op — it actually intercepts
    real socket calls. We attempt a real connection and verify it's blocked.
    """
    with AirGapEgressMonitor() as monitor:
        try:
            # Attempt a real connection — this MUST be intercepted
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect(("127.0.0.1", 19999))  # unlikely to be open
        except ConnectionError:
            pass  # Expected — the monitor blocks it
        except Exception:
            pass  # Other errors also acceptable as long as no connection happens

    assert monitor.report.total_egress > 0, \
        "Egress monitor did not catch a real connection attempt — it's a no-op!"
    assert monitor.report.attempts[0].function == "socket.socket.connect"


def test_egress_monitor_catches_dns_lookup():
    """The egress monitor must catch a REAL DNS lookup attempt."""
    with AirGapEgressMonitor() as monitor:
        try:
            socket.getaddrinfo("example.com", 80)
        except (socket.gaierror, ConnectionError, OSError):
            pass  # Expected — the monitor blocks it
        except Exception:
            pass

    assert monitor.report.total_dns > 0, \
        "Egress monitor did not catch a real DNS lookup — it's a no-op!"
    assert "example.com" in monitor.report.dns_lookups[0].target


def test_egress_monitor_catches_create_connection():
    """The egress monitor must catch socket.create_connection attempts."""
    with AirGapEgressMonitor() as monitor:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=1)
        except (ConnectionError, OSError):
            pass
        except Exception:
            pass

    assert monitor.report.total_egress > 0, \
        "Egress monitor did not catch create_connection attempt"


def test_egress_monitor_restores_sockets_after_exit():
    """After the monitor exits, socket functions must be restored."""
    original_connect = socket.socket.connect
    original_getaddrinfo = socket.getaddrinfo

    with AirGapEgressMonitor():
        # Inside the monitor — functions are patched
        assert socket.socket.connect is not original_connect
        assert socket.getaddrinfo is not original_getaddrinfo

    # Outside the monitor — functions are restored
    assert socket.socket.connect is original_connect
    assert socket.getaddrinfo is original_getaddrinfo


# ---------------------------------------------------------------------------
# Egress report serialization
# ---------------------------------------------------------------------------

def test_egress_report_json_serializable():
    """The egress report must be JSON serializable for CI consumption."""
    report = run_airgap_proof()
    json_str = report.to_json()
    data = json.loads(json_str)
    assert "total_egress_attempts" in data
    assert "total_dns_lookups" in data
    assert "zero_egress" in data
    assert data["zero_egress"] is True


# ---------------------------------------------------------------------------
# Failing-capable tests: break the behavior and verify the test catches it
# ---------------------------------------------------------------------------

def test_failing_capable_egress_detected_when_not_blocked():
    """This test proves the monitor works by showing it catches egress.

    If the monitor's blocking logic is removed, this test goes RED because
    the connection attempt would succeed instead of being recorded as blocked.
    """
    with AirGapEgressMonitor() as monitor:
        try:
            socket.gethostbyname("localhost")
        except (socket.gaierror, OSError, ConnectionError):
            pass

    # The monitor MUST have recorded this DNS attempt
    assert monitor.report.total_dns > 0, \
        "Regression: egress monitor stopped catching DNS lookups"


def test_failing_capable_zero_egress_invariant():
    """This test FAILS if any code path in the air-gap session tries to connect.

    To verify: add a socket.create_connection call to run_airgap_session()
    and this test will go RED.
    """
    report = run_airgap_proof()
    # This is the core invariant — zero egress in air-gap mode
    assert report.total_egress == 0 and report.total_dns == 0, \
        f"Regression: air-gap session leaked {report.total_egress} connections " \
        f"and {report.total_dns} DNS lookups"