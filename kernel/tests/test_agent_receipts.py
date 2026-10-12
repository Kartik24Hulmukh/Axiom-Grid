"""Receipt integrity, pinned trust, concurrent signing, and offline CLI gates."""
import copy
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from hypothesis import given, strategies as st

from kernel.core.agent_receipts import ReceiptError, ReceiptSession, verify_bundle
from kernel.core.receipt_adapters import append_openbot, append_trace


def event(i=0):
    return {"id": f"event-{i}", "actorUserId": None, "initiatorKind": "bot",
            "initiatorId": "bot-id", "eventType": "mcp.call_succeeded",
            "targetType": "tool", "targetId": "read", "payload": {"tool": "read"},
            "createdAt": "2026-10-01T00:00:00Z"}


@pytest.fixture
def signed():
    key = Ed25519PrivateKey.generate()
    session = ReceiptSession(key, "test-session")
    for i in range(3):
        append_openbot(session, event(i))
    return key, session


def test_verify_real_signatures(signed):
    key, session = signed
    report = verify_bundle(session.export(), key.public_key())
    assert report["valid"] and report["entry_count"] == 3


@pytest.mark.parametrize("mutation", [
    "value", "delete", "tail", "reorder", "duplicate", "key", "signature",
    "checkpoint", "checkpoint_signature", "extra", "version", "sequence_bool",
])
def test_mutations_fail_closed(signed, mutation):
    key, session = signed
    bundle = session.export()
    if mutation == "value":
        bundle["entries"][0]["payload"]["action"] = "forged"
    elif mutation == "delete":
        del bundle["entries"][1]
    elif mutation == "tail":
        bundle["entries"].pop()
    elif mutation == "reorder":
        bundle["entries"].reverse()
    elif mutation == "duplicate":
        bundle["entries"][1] = copy.deepcopy(bundle["entries"][0])
    elif mutation == "key":
        key = Ed25519PrivateKey.generate()
    elif mutation == "signature":
        bundle["entries"][0]["signature"] = "00" * 64
    elif mutation == "checkpoint":
        bundle["checkpoint"]["tail_hash"] = ""
    elif mutation == "checkpoint_signature":
        bundle["checkpoint_signature"] = "x"
    elif mutation == "extra":
        bundle["entries"][0]["payload"]["secret"] = "bad"
    elif mutation == "version":
        bundle["checkpoint"]["version"] = "new"
    elif mutation == "sequence_bool":
        bundle["entries"][0]["payload"]["sequence"] = False
    with pytest.raises(ReceiptError):
        verify_bundle(bundle, key.public_key())


def test_retained_checkpoint_detects_old_export(signed):
    key, session = signed
    old = session.export()
    append_openbot(session, event(4))
    with pytest.raises(ReceiptError, match="checkpoint mismatch"):
        verify_bundle(old, key.public_key(), session.export()["checkpoint"])


def test_export_and_returned_entry_do_not_expose_mutable_state(signed):
    key, session = signed
    item = append_openbot(session, event(4))
    item["payload"]["action"] = "mutated"
    bundle = session.export()
    bundle["entries"].clear()
    assert verify_bundle(session.export(), key.public_key())["entry_count"] == 4


def test_100_concurrent_signers_have_one_contiguous_chain(signed):
    key, session = signed
    with ThreadPoolExecutor(max_workers=100) as pool:
        list(pool.map(lambda i: append_openbot(session, event(i)), range(1000)))
    assert verify_bundle(session.export(), key.public_key())["entry_count"] == 1003
    assert [e["payload"]["sequence"] for e in session.export()["entries"]] == list(range(1003))


def test_no_raw_secret_or_prompt_is_exported(signed):
    _, session = signed
    private = event(4)
    private["payload"] = {"api_key": "sensitive-test-value", "prompt": "private customer text"}
    append_openbot(session, private)
    exported = json.dumps(session.export())
    assert "sensitive-test-value" not in exported and "private customer text" not in exported


@pytest.mark.parametrize("field", ["id", "eventType", "targetType", "createdAt", "payload"])
def test_openbot_missing_fields_fail(signed, field):
    _, session = signed
    item = event()
    del item[field]
    with pytest.raises(ReceiptError):
        append_openbot(session, item)


@pytest.mark.parametrize("provider", ["opik", "helicone"])
def test_trace_exports_are_observations_only(signed, provider):
    key, session = signed
    append_trace(session, provider, {"id": "trace-id", "output": {"secret": "not-exported"}})
    assert verify_bundle(session.export(), key.public_key())["entry_count"] == 4
    assert session.export()["entries"][-1]["payload"]["outcome"] == "observed"


@given(st.text(min_size=1, max_size=32).filter(
    lambda s: all(ord(c) >= 32 and not 0xD800 <= ord(c) <= 0xDFFF for c in s)))
def test_unicode_evidence_commitments_round_trip(text):
    key = Ed25519PrivateKey.generate()
    session = ReceiptSession(key)
    session.append(source="test", source_event_id="id", action="read",
                   outcome="observed", evidence={"text": text})
    assert verify_bundle(session.export(), key.public_key())["valid"]


@pytest.mark.parametrize("evidence", [{"x": float("nan")}, {"x": float("inf")},
                                      {"x": object()}, {"x": "a" * 65536}])
def test_invalid_or_oversized_evidence_is_rejected(evidence):
    session = ReceiptSession(Ed25519PrivateKey.generate())
    with pytest.raises(ReceiptError):
        session.append(source="test", source_event_id="id", action="read",
                       outcome="observed", evidence=evidence)


def test_offline_cli_round_trip_and_tamper(tmp_path):
    key = Ed25519PrivateKey.generate()
    private = tmp_path / "private.pem"
    public = tmp_path / "public.pem"
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                         serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    private.chmod(0o600)
    public.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,
                                                   serialization.PublicFormat.SubjectPublicKeyInfo))
    events = tmp_path / "events.json"
    events.write_text(json.dumps([event()]))
    bundle = tmp_path / "receipts.json"
    script = Path(__file__).resolve().parents[2] / "scripts/axiom_receipts.py"
    def run(*args):
        return subprocess.run([sys.executable, str(script), *map(str, args)],
                              capture_output=True, text=True, timeout=10)
    assert run("export", events, "--source", "openbot", "--private-key", private,
               "--output", bundle).returncode == 0
    result = run("verify", bundle, "--public-key", public)
    assert result.returncode == 0 and json.loads(result.stdout)["entry_count"] == 1
    data = json.loads(bundle.read_text())
    data["entries"].clear()
    bundle.write_text(json.dumps(data))
    assert run("verify", bundle, "--public-key", public).returncode == 1
    bundle.write_text('{"checkpoint":{},"checkpoint":{}}')
    assert run("verify", bundle, "--public-key", public).returncode == 1