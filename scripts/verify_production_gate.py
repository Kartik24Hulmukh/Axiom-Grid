#!/usr/bin/env python3
"""Compatibility CLI for scoped reported-evidence checking, NOT production qualification.

Requires --evidence FILE --expected-revision HEX40 --expected-profile PROFILE.
See release_evidence.py for schema, fixed freshness limits and limitations.
No automatic CWD/HOME evidence, secret scans, SBOM writes, models or networking.
"""
from __future__ import annotations


def main(argv=None) -> int:
    if __package__:
        from .release_evidence import main as check
    else:
        from release_evidence import main as check
    return check(argv)


if __name__ == "__main__":
    raise SystemExit(main())
