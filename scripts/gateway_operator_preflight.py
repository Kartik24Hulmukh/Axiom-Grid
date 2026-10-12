#!/usr/bin/env python3
"""Offline, zero-dispatch operator gate. Never imports/instantiates the router."""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import stat
from urllib.parse import urlsplit

LIMIT = 65536
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}\Z")


def safe_origin(value: str, *, origin_only: bool = False) -> str:
    """Structural screen only: no DNS or claim of provider ownership."""
    if not value or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise ValueError
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or parsed.port not in (None, 443) or "\\" in value
            or parsed.path not in ("", "/") and origin_only):
        raise ValueError
    # Path must be literal, not encoded traversal or a guessed query endpoint.
    if parsed.path and not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)*/?", parsed.path):
        raise ValueError
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if (not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host)
                or "." not in host or ".." in host
                or host.endswith((".localhost", ".local", ".internal", ".test", ".invalid"))):
            raise ValueError from None
    else:
        # IP literals, even public ones, are not provider identity evidence.
        raise ValueError
    return "https://" + host


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def catalog_matches(path: str, models: tuple[str, ...]) -> bool:
    """Bounded regular local file; a snapshot is NOT a fresh live discovery."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return False
            raw = stream.read(LIMIT + 1)
        if len(raw) > LIMIT:
            return False
        data = json.loads(raw, object_pairs_hook=unique_object)
        entries = data.get("data") if isinstance(data, dict) else None
        if not isinstance(entries, list) or not 1 <= len(entries) <= 4096:
            return False
        ids = [entry.get("id") if isinstance(entry, dict) else None for entry in entries]
        if any(not isinstance(item, str) or not MODEL.fullmatch(item) for item in ids):
            return False
        return len(set(ids)) == len(ids) and all(model in ids for model in models)
    except (OSError, ValueError, RecursionError):
        return False


def evaluate(env, *, live=False, catalog_file=None):
    gates = []
    models = tuple(env.get("MELIOUS_MODELS", "").split(","))
    model_valid = (1 <= len(models) <= 16 and len(set(models)) == len(models)
                   and all(MODEL.fullmatch(item) for item in models))
    if not model_valid:
        gates.append("explicit_exact_model_ids_required")
    try:
        origin = safe_origin(env.get("MELIOUS_BASE_URL", ""))
        approved = env.get("MELIOUS_PREFLIGHT_ALLOWED_ORIGINS", "").split(",")
        if len(approved) > 16 or origin not in {safe_origin(item, origin_only=True) for item in approved}:
            raise ValueError
    except ValueError:
        gates.append("https_destination_and_exact_origin_allowlist_required")
    if any(env.get(name) for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                                      "http_proxy", "https_proxy", "all_proxy")):
        gates.append("ambient_proxy_configuration_requires_operator_review")
    if not env.get("MELIOUS_API_KEY"):
        gates.append("privately_configured_rotated_key_required")
    ceiling = env.get("MELIOUS_TOKEN_CEILING", "")
    if not ceiling.isascii() or not ceiling.isdecimal() or not 1 <= int(ceiling[:12]) <= 10000 or len(ceiling) > 5:
        gates.append("bounded_local_token_admission_required")
    snapshot = bool(model_valid and catalog_file and catalog_matches(catalog_file, models))
    if not snapshot:
        gates.append("exact_local_catalog_snapshot_missing_or_invalid")
    # No generic adapter is safe here: ownership, DNS targets, official endpoint,
    # billing and provider cap are unknown. Even --live cannot override these.
    gates.extend(["official_provider_endpoint_and_ownership_unverified",
                  "public_dns_targets_and_rebinding_controls_unverified",
                  "provider_hard_monetary_cap_and_error_billing_unverified",
                  "fresh_exact_catalog_and_model_quality_unverified"])
    if live:
        gates.append("live_adapter_not_approved_no_dispatch")
    return {"decision": "BLOCKED", "mode": "live_requested_but_refused" if live else "offline",
            "outbound_call_limit": 0, "outbound_calls": 0, "maximum_script_spend": 0,
            "local_catalog_exact_match": snapshot, "launch_approved": False, "gates": gates}


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # Do not echo unknown arguments or paths: operators may accidentally
        # paste a credential. Environment values likewise never enter output.
        self.exit(2, "Invalid preflight arguments; use --help.\n")


def main(argv=None):
    parser = SafeParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Request live mode; refused until provider-specific review.")
    parser.add_argument("--catalog-file", help="Optional bounded local catalog JSON snapshot; not fresh discovery.")
    args = parser.parse_args(argv)
    print(json.dumps(evaluate(os.environ, live=args.live, catalog_file=args.catalog_file), sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
