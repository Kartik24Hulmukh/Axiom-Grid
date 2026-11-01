"""Bounded diagnostic counts/test identities, never a test or release gate.

Only module/function identifiers are public. Parameter values, failure messages,
tracebacks, arbitrary properties and captured output are deliberately not rendered.
One exact testcase may expose a fixed enum checkpoint from future reports only;
this is not a failing-assertion or root-cause verdict. This
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
MAX_PHASES = 1
MAX_OUTPUT_BYTES = 16 * 1024
_BURST_MODULE = "overlay.tests.test_surrogate_encode_zero_day"
_BURST_NAME = "test_surrogate_burst_100_workers_zero_5xx_and_recovery_slo"
_BURST_ID = f"{_BURST_MODULE}::{_BURST_NAME}"
_PHASE_KEY = "axiom_surrogate_burst_phase"
_PHASES = frozenset({"workload", "no_5xx", "health", "quantiles", "p50", "complete"})
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


def _phase(case: ET.Element) -> str | None:
    """Extract only an unambiguous, owned enum; ignore every other value."""
    containers = case.findall("properties")
    if len(containers) != 1 or containers[0].attrib:
        return None
    container = containers[0]
    if container.text and container.text.strip():
        return None
    if any(child.tag != "property" or set(child.attrib) != {"name", "value"}
           or len(child) or child.text not in (None, "")
           or (child.tail and child.tail.strip()) for child in container):
        return None
    matches = [child for child in container if child.get("name") == _PHASE_KEY]
    if len(matches) != 1:
        return None
    value = matches[0]
    if (set(value.attrib) != {"name", "value"} or len(value)
            or value.text not in (None, "")):
        return None
    phase = value.get("value")
    return phase if phase in _PHASES else None


def _safe_phases(value, labels: list[str]) -> list[dict]:
    """Revalidate optional observations, even for direct forged render inputs."""
    if (not isinstance(value, list) or len(value) > MAX_PHASES
            or len(labels) + len(value) > MAX_LABELS
            or labels.count(_BURST_ID) != 1):
        return []
    result = []
    for item in value:
        if (not isinstance(item, dict) or set(item) != {"test", "phase"}
                or not isinstance(item["test"], str) or item["test"] != _BURST_ID
                or item["test"] not in labels
                or not isinstance(item["phase"], str) or item["phase"] not in _PHASES):
            return []
        result.append({"test": _BURST_ID, "phase": item["phase"]})
    return result


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
        target_cases = 0
        phases = []
        # Preserve historical count traversal, but never attribute a checkpoint
        # to a testcase hidden inside failure text, properties or output nodes.
        suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
        eligible = set()
        while suites:
            suite = suites.pop()
            for child in suite:
                if child.tag == "testsuite":
                    suites.append(child)
                elif child.tag == "testcase":
                    eligible.add(id(child))
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
            raw_target = case.get("classname") == _BURST_MODULE and case.get("name") == _BURST_NAME
            if raw_target:
                target_cases += 1
            if (flags["failures"] or flags["errors"]) and len(labels) < MAX_LABELS:
                labels.append(_label(case.get("classname", ""), case.get("name", "")))
                if raw_target and id(case) in eligible:
                    phase = _phase(case)
                    if phase is not None:
                        phases.append({"test": _BURST_ID, "phase": phase})
        return {**_SCOPE, "status": "available", "counts": counts,
                "failed_tests": labels,
                "failure_phases": _safe_phases(phases, labels) if target_cases == 1 else [],
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
    for item in _safe_phases(result.get("failure_phases", []), safe_labels):
        lines.append(f"- Last recorded burst phase: `{item['phase']}` "
                     "(diagnostic checkpoint; not a failing-assertion or root-cause verdict).\n")
    if omitted:
        lines.append(f"- Additional failing/error cases omitted: {omitted}.\n")
    lines.append("\nCounts, identifiers and an optional fixed checkpoint only; messages, parameters, arbitrary properties and captured output are excluded. "
                 "The original test step and preserved artifact remain authoritative.\n")
    text = "".join(lines)
    return text if len(text.encode("utf-8")) <= MAX_OUTPUT_BYTES else unavailable


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
        for item in _safe_phases(result.get("failure_phases", []), result["failed_tests"]):
            print("::notice title=Service diagnostic checkpoint::surrogate_burst_phase=" + item["phase"])
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
