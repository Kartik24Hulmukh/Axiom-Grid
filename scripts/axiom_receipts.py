"""Offline `export` and `verify` CLI; trust keys supplied separately."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives import serialization
from kernel.core.agent_receipts import MAX_EXPORT_BYTES, ReceiptError, ReceiptSession, verify_bundle
from kernel.core.receipt_adapters import append_openbot, append_trace


def read_json(path):
    with open(path, "rb") as stream:
        data = stream.read(MAX_EXPORT_BYTES + 1)
    if len(data) > MAX_EXPORT_BYTES:
        raise ReceiptError("input exceeds byte budget")
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ReceiptError("duplicate JSON key")
            result[k] = v
        return result
    return json.loads(data, object_pairs_hook=unique)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Axiom-Grid offline signed observations")
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export")
    export.add_argument("input")
    export.add_argument("--source", choices=["openbot", "opik", "helicone"], required=True)
    export.add_argument("--private-key", required=True)
    export.add_argument("--output", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("input")
    verify.add_argument("--public-key", required=True)
    verify.add_argument("--checkpoint", help="Independently retained checkpoint JSON")
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            key = serialization.load_pem_public_key(Path(args.public_key).read_bytes())
            report = verify_bundle(read_json(args.input), key,
                                   read_json(args.checkpoint) if args.checkpoint else None)
            print(json.dumps(report))
        else:
            private_path = Path(args.private_key)
            if os.name == "posix" and private_path.stat().st_mode & 0o077:
                raise ReceiptError("private key permissions must be 0600 or stricter")
            key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
            session = ReceiptSession(key)
            records = read_json(args.input)
            if not isinstance(records, list):
                raise ReceiptError("export input must be a JSON array of events")
            for record in records:
                if args.source == "openbot":
                    append_openbot(session, record)
                else:
                    append_trace(session, args.source, record)
            # Exclusive create prevents clobbering a previous evidence export.
            with open(args.output, "x", encoding="utf-8") as stream:
                json.dump(session.export(), stream, indent=2)
            print(json.dumps({"exported": len(records), "source": args.source}))
        return 0
    except (ReceiptError, OSError, ValueError, TypeError, RecursionError):
        print("FAIL: invalid, untrusted, or unavailable receipt/key material", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())