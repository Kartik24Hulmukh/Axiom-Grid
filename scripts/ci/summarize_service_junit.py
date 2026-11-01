"""Bounded diagnostic counts/test identities, never a test or release gate.

Only module/function identifiers are public. Parameter values, failure messages,
tracebacks, properties and captured output are deliberately not rendered. This
is not a general secret scanner: module/function identifiers are trusted repository
metadata and can still disclose a secret if a producer puts one in an identifier.
Parent directories must be trusted; no pathname
sandbox or custody guarantee is made. The original pytest step owns its result.
"""
from __future__ import annotations

import os
import re
import stat
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_BYTES = 4 * 1024 * 1024
MAX_CASES = 20_000
MAX_LABELS = 20
_SCOPE = {"scope": "diagnostic-only", "production_qualified": False}
_UNAVAILABLE = "JUnit report unavailable or invalid."
_HIDDEN = "[test identity unavailable]"
_MODULE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", re.ASCII)
_FUNCTION = re.compile(r"test_[A-Za-z0-9_]+", re.ASCII)


def _unavailable() -> dict:
    return {**_SCOPE, "status": "unavailable", "reason": _UNAVAILABLE}


def _label(module: str, name: str) -> str:
    name = name.split("[", 1)[0]
    if (len(module) > 200 or len(name) > 128 or not _MODULE.fullmatch(module)
            or not _FUNCTION.fullmatch(name)):
        return _HIDDEN
    return f"{module}::{name}"


def _read(path: str | Path) -> bytes:
    # Reject leaf symlinks and avoid blocking on a substituted FIFO on Linux CI.
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_NONBLOCK"):
        raise ValueError("unsupported capture")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise ValueError("invalid report")
        data = bytearray()
        while len(data) <= MAX_BYTES:
            part = os.read(fd, min(65_536, MAX_BYTES + 1 - len(data)))
            if not part:
                break
            data.extend(part)
        if len(data) > MAX_BYTES:
            raise ValueError("oversized report")
        return bytes(data)
    finally:
        os.close(fd)


def summarize(path: str | Path) -> dict:
    """Return diagnostic observations, or a sanitized unavailable result."""
    try:
        text = _read(path).decode("utf-8", errors="strict")
        if "\x00" in text or "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            return _unavailable()
        root = ET.fromstring(text)
        if root.tag not in {"testsuite", "testsuites"}:
            return _unavailable()
        counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
        labels = []
        for case in root.iter("testcase"):
            counts["tests"] += 1
            if counts["tests"] > MAX_CASES:
                return _unavailable()
            flags = {key: len(case.findall(tag)) for key, tag in
                     (("failures", "failure"), ("errors", "error"), ("skipped", "skipped"))}
            if sum(flags.values()) > 1:
                return _unavailable()
            for key, value in flags.items():
                counts[key] += value
            if (flags["failures"] or flags["errors"]) and len(labels) < MAX_LABELS:
                labels.append(_label(case.get("classname", ""), case.get("name", "")))
        return {**_SCOPE, "status": "available", "counts": counts,
                "failed_tests": labels,
                "omitted_failures": counts["failures"] + counts["errors"] - len(labels)}
    except (OSError, ValueError, TypeError, UnicodeError, ET.ParseError, OverflowError):
        return _unavailable()


def render(result: dict) -> str:
    """Render defensively, including when called with an untrusted API object."""
    prefix = "## Service test diagnostics (not qualification)\n\n"
    unavailable = prefix + _UNAVAILABLE + " See the preserved full-service-results artifact.\n"
    if not isinstance(result, dict) or result.get("status") != "available":
        return unavailable
    counts = result.get("counts")
    if (not isinstance(counts, dict) or set(counts) != {"tests", "failures", "errors", "skipped"}
            or any(type(v) is not int or not 0 <= v <= MAX_CASES for v in counts.values())
            or counts["failures"] + counts["errors"] + counts["skipped"] > counts["tests"]):
        return unavailable
    labels = result.get("failed_tests")
    omitted = result.get("omitted_failures")
    total = counts["failures"] + counts["errors"]
    if (not isinstance(labels, list) or len(labels) > MAX_LABELS
            or type(omitted) is not int or omitted < 0 or omitted + len(labels) != total):
        return unavailable
    safe_labels = []
    for value in labels:
        if not isinstance(value, str):
            return unavailable
        if value == _HIDDEN:
            safe_labels.append(value)
            continue
        fields = value.split("::")
        if len(fields) != 2 or _label(*fields) != value:
            safe_labels.append(_HIDDEN)
        else:
            safe_labels.append(value)
    lines = [prefix, "Observed testcase elements: " + ", ".join(f"{k}={v}" for k, v in counts.items()) + ".\n"]
    lines.extend(f"- `{name}`\n" for name in safe_labels)
    if omitted:
        lines.append(f"- Additional failing/error cases omitted: {omitted}.\n")
    lines.append("\nCounts and identifiers only; messages, parameters and captured output are excluded. "
                 "The original test step and preserved artifact remain authoritative.\n")
    return "".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    result = summarize(args[0]) if isinstance(args, (list, tuple)) and len(args) == 1 and isinstance(args[0], str) else _unavailable()
    text = render(result)
    print(text, end="")
    # These limited notices are visible via the public check annotations endpoint.
    if result["status"] == "available":
        counts = result["counts"]
        print("::notice title=Service test diagnostics::" + ", ".join(f"{k}={v}" for k, v in counts.items()))
        for label in result["failed_tests"]:
            print(f"::notice title=Service test case::{label}")
        if result["omitted_failures"]:
            print(f"::notice title=Service test diagnostics::omitted_failures={result['omitted_failures']}")
    else:
        print("::notice title=Service test diagnostics::JUnit report unavailable or invalid; inspect preserved artifact.")
    destination = os.environ.get("GITHUB_STEP_SUMMARY")
    if destination:
        try:
            with open(destination, "a", encoding="utf-8") as output:
                if output.write(text) != len(text):
                    raise OSError("short write")
        except (OSError, ValueError, UnicodeError):
            print("::notice title=Service test diagnostics::Step-summary write unavailable.")
    # Diagnostic only. This does not change or replace the preceding test result.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
