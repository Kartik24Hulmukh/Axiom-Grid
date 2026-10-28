#!/usr/bin/env python3
"""Quarantined legacy entrypoint: no production certification or launch clearance.

Importing this module performs no checks or writes. Running it always refuses;
legacy hardcoded claims must not be used as production qualification evidence.
For scoped reported-metric validation, use scripts/release_evidence.py --help.
That checker does not authenticate evidence or qualify native/offline production.
"""
from __future__ import annotations


def main(argv=None) -> int:
    import sys
    print("BLOCKED: legacy production certification/launch clearance is quarantined. "
          "Use scripts/release_evidence.py --help for scoped reported-data checks only; "
          "production remains unqualified.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
