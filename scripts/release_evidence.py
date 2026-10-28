#!/usr/bin/env python3
"""Validate scoped, reported metrics; never certify production or authenticity.

CLI: python scripts/release_evidence.py --evidence FILE \
    --expected-revision HEX40 --expected-profile PROFILE
Also available through scripts/verify_production_gate.py with the same arguments.
Stdout is a JSON decision; exits 0 accepted, 1 rejected, 2 invalid CLI.
No report files, repository discovery, network, model or signing operations.

Schema (exact keys; metrics also use exact keys):
{"schema_version": 1, "revision": "<40 hex characters>",
 "profile": "<nonblank string>", "run_id": "<nonblank string>",
 "generated_at": "<UTC YYYY-MM-DDTHH:MM:SS[.ffffff]Z or +00:00>",
 "synthetic": false,
 "metrics": {"passed": 90, "total": 100, "bmc": 0.074,
             "vlm_calls": 4, "total_calls": 100}}

Evidence is limited to 1 MiB of UTF-8 JSON from a regular file. Duplicate keys,
non-finite numbers (including exponent overflow), booleans as numbers, missing
or unknown keys and malformed data are rejected. Timestamps may be at most 24
hours old and at most 5 minutes in the future, relative to the checking clock.
These are fixed policy limits, not user overrides. Revision comparison is
case-insensitive; profile comparison is exact. Counts must be strict integers,
0 <= numerator <= denominator and denominator > 0. Completion >= 90%,
BMC in [0, .074], VLM rate < 5%.

JSON decimal/exponent literals are parsed exactly as Decimal (no binary-float
rounding or underflow). Decimal magnitudes above the largest finite binary64
float are rejected by parser policy; tiny finite decimals are preserved, not
rounded to zero. Unrepresentable Decimal exponents are rejected. Integer
literals remain integers. For direct Python API callers, BMC accepts finite
Decimal, int, or float; a float is interpreted as Decimal(str(value)). The API
cannot recover precision already lost before that float was supplied.

Acceptance means only that supplied reported data passed these checks. It is
not authentication, attestation, model provenance, native UI, offline or
production qualification. The synthetic flag is a declaration, not proof.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, DecimalException
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

MAX_BYTES = 1024 * 1024
MAX_AGE = timedelta(hours=24)
MAX_FUTURE = timedelta(minutes=5)
_MAX_JSON_DECIMAL = Decimal.from_float(sys.float_info.max)
_BMC_MAX = Decimal("0.074")
_TOP_KEYS = {"schema_version", "revision", "profile", "run_id", "generated_at", "synthetic", "metrics"}
_METRIC_KEYS = {"passed", "total", "bmc", "vlm_calls", "total_calls"}
_REVISION = re.compile(r"[0-9a-fA-F]{40}")
_UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", re.ASCII)
_LIMITATIONS = "Reported data only; no authenticity, attestation, native, offline or production qualification."


class EvidenceError(ValueError):
    """A sanitized, fixed-message validation failure."""


def _reject_constant(_value):
    raise EvidenceError("Non-finite JSON number rejected.")


def _exact_decimal(value):
    result = Decimal(value)
    if not result.is_finite() or result.copy_abs() > _MAX_JSON_DECIMAL:
        raise EvidenceError("JSON decimal is non-finite or exceeds parser magnitude limit.")
    return result


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError("Duplicate JSON key rejected.")
        result[key] = value
    return result


def load_evidence(path: str | Path) -> dict:
    """Read bounded strict JSON, without echoing paths or untrusted contents."""
    try:
        # Nonblocking open plus a regular-file check avoids waiting on FIFOs.
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise EvidenceError("Evidence must be a regular file.")
            if info.st_size > MAX_BYTES:
                raise EvidenceError("Evidence exceeds byte limit.")
            with os.fdopen(fd, "rb") as stream:
                fd = None  # The stream now owns and closes the descriptor.
                raw = stream.read(MAX_BYTES + 1)
        finally:
            if fd is not None:
                os.close(fd)
        if len(raw) > MAX_BYTES:
            raise EvidenceError("Evidence exceeds byte limit.")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant, parse_float=_exact_decimal)
    except EvidenceError:
        raise
    except (OSError, ValueError, TypeError, RecursionError, OverflowError, DecimalException):
        raise EvidenceError("Evidence could not be read as bounded strict JSON.") from None
    if type(data) is not dict:
        raise EvidenceError("Evidence must be a JSON object.")
    return data


def _nonblank(value):
    return type(value) is str and bool(value.strip())


def _counts(numerator, denominator):
    return (type(numerator) is int and type(denominator) is int
            and denominator > 0 and 0 <= numerator <= denominator)


def validate_evidence(data: dict, *, expected_revision: str,
                      expected_profile: str, now: datetime | None = None) -> dict:
    """Validate a supplied object; return a scoped acceptance, never a certificate.

    ``now`` is an aware datetime injection for deterministic tests. The CLI uses
    the current UTC clock and exposes no clock or age-policy override. Decimal
    BMC values are exact; finite floats mean Decimal(str(value)), not recovery
    of the original JSON literal. Use load_evidence for exact JSON validation.
    """
    if type(expected_revision) is not str or not _REVISION.fullmatch(expected_revision):
        raise EvidenceError("Expected revision must be 40 hexadecimal characters.")
    if not _nonblank(expected_profile):
        raise EvidenceError("Expected profile must be nonblank.")
    if type(data) is not dict or set(data) != _TOP_KEYS:
        raise EvidenceError("Evidence schema fields are missing or unsupported.")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise EvidenceError("Unsupported schema version.")
    revision = data["revision"]
    if type(revision) is not str or not _REVISION.fullmatch(revision):
        raise EvidenceError("Evidence revision is invalid.")
    if revision.lower() != expected_revision.lower():
        raise EvidenceError("Evidence revision does not match.")
    if not _nonblank(data["profile"]) or data["profile"] != expected_profile:
        raise EvidenceError("Evidence profile does not match.")
    if not _nonblank(data["run_id"]):
        raise EvidenceError("Evidence run identifier is invalid.")
    if type(data["synthetic"]) is not bool or data["synthetic"] is not False:
        raise EvidenceError("Synthetic or undeclared evidence is not accepted.")
    timestamp = data["generated_at"]
    if type(timestamp) is not str or not _UTC_TIMESTAMP.fullmatch(timestamp):
        raise EvidenceError("Evidence requires an explicit UTC timestamp.")
    try:
        generated = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        raise EvidenceError("Evidence UTC timestamp is invalid.") from None
    current = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        raise EvidenceError("Validation clock must be timezone-aware.")
    age = current.astimezone(timezone.utc) - generated
    if age > MAX_AGE or age < -MAX_FUTURE:
        raise EvidenceError("Evidence timestamp is outside the allowed time window.")
    metrics = data["metrics"]
    if type(metrics) is not dict or set(metrics) != _METRIC_KEYS:
        raise EvidenceError("Required metrics are missing or unsupported.")
    passed, total = metrics["passed"], metrics["total"]
    vlm, calls = metrics["vlm_calls"], metrics["total_calls"]
    if not _counts(passed, total) or not _counts(vlm, calls):
        raise EvidenceError("Metric counts must be valid integers with positive denominators.")
    bmc = metrics["bmc"]
    if type(bmc) is float:
        if not math.isfinite(bmc):
            raise EvidenceError("BMC must be a finite number between zero and one.")
        bmc = Decimal(str(bmc))
    elif type(bmc) is int:
        bmc = Decimal(bmc)
    elif type(bmc) is not Decimal:
        raise EvidenceError("BMC must be a finite number between zero and one.")
    if not bmc.is_finite() or not 0 <= bmc <= 1:
        raise EvidenceError("BMC must be a finite number between zero and one.")
    # Exact decimal comparison and integer cross-products avoid rounded passes.
    if passed * 10 < total * 9 or bmc > _BMC_MAX or vlm * 20 >= calls:
        raise EvidenceError("Reported metrics do not meet the scoped thresholds.")
    return {"status": "accepted", "scope": "reported-metrics-v1",
            "production_qualified": False, "limitations": _LIMITATIONS}


class _Parser(argparse.ArgumentParser):
    def error(self, _message):
        # argparse's usual error can repeat arbitrary argument contents.
        self.exit(2, "Invalid command line. Use --help for required explicit inputs.\n")


def main(argv=None) -> int:
    parser = _Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--expected-profile", required=True)
    args = parser.parse_args(argv)
    try:
        result = validate_evidence(load_evidence(args.evidence),
                                   expected_revision=args.expected_revision,
                                   expected_profile=args.expected_profile)
    except EvidenceError as error:
        print(json.dumps({"status": "rejected", "production_qualified": False,
                          "reason": str(error), "limitations": _LIMITATIONS}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
