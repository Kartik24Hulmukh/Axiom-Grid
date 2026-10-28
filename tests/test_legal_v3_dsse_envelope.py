"""Tests for DSSE/in-toto envelope wrapping of legal-v3 evidence bundles."""
import base64
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from kairo.legal_v3.dsse_envelope import (
    PAYLOAD_TYPE,
    PREDICATE_TYPE,
    STATEMENT_TYPE,
    create_envelope,
    create_statement,
    pae,
    parse_envelope,
    verify_envelope,
    wrap_bundle,
)
from kairo.legal_v3.transaction import (
    approve,
    execute,
    generate_keypair,
    propose,
)


# Canonical base64, structurally valid only: not an authentic signature.
STRUCTURAL_SIGNATURE = base64.b64encode(b"structural-only-placeholder").decode("ascii")

def _build_bundle(work: Path) -> Path:
    """Build a valid evidence bundle and return its path."""
    repo = Path(__file__).resolve().parents[1]
    shutil.copy2(repo / "fixtures/demo/sample_nda.docx", work / "nda.docx")
    shutil.copy2(
        repo / "fixtures/demo/nda_playbook.json", work / "playbook.json"
    )
    prod = generate_keypair("producer")
    app = generate_keypair("approver")
    obs = generate_keypair("observer")
    proposal = propose(str(work), "nda.docx", "playbook.json", "out.docx", prod)
    approval = approve(proposal, app)
    keys = {
        prod["key_id"]: prod["public"],
        app["key_id"]: app["public"],
    }
    bundle_path = work / "bundle"
    execute(str(work), proposal, approval, keys, obs, str(bundle_path))
    return bundle_path


class DSSEEnvelopeTests(unittest.TestCase):
    def setUp(self) -> None:
        # Independent test trust root, never taken from the bundle/envelope.
        self.dsse_key = Ed25519PrivateKey.generate()
        self.trusted_keys = {"test-key": self.dsse_key.public_key()}
        self.t = Path(tempfile.mkdtemp())
        self.bundle_path = _build_bundle(self.t)
        self.bundle = json.loads(
            (self.bundle_path / "bundle.json").read_text()
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.t, ignore_errors=True)

    def verify_signature(self, message_bytes, signature_b64, key_id):
        key = self.trusted_keys.get(key_id)
        if key is None:
            return False
        try:
            key.verify(base64.b64decode(signature_b64, validate=True), message_bytes)
        except InvalidSignature:
            return False
        return True

    def test_create_statement(self) -> None:
        """Statement has correct in-toto v1 structure."""
        stmt = create_statement(self.bundle)
        self.assertEqual(stmt["_type"], STATEMENT_TYPE)
        self.assertEqual(stmt["predicateType"], PREDICATE_TYPE)
        self.assertIsInstance(stmt["subject"], list)
        self.assertGreaterEqual(len(stmt["subject"]), 1)
        # Subject should have sha256 digest
        for subj in stmt["subject"]:
            self.assertIn("sha256", subj["digest"])
        # Predicate is the full bundle
        self.assertEqual(stmt["predicate"], self.bundle)

    def test_create_envelope(self) -> None:
        """Envelope has correct DSSE structure."""
        sigs = [{"sig": STRUCTURAL_SIGNATURE, "keyid": "test-key"}]
        env = create_envelope(self.bundle, sigs)
        self.assertEqual(env["payloadType"], PAYLOAD_TYPE)
        self.assertIn("payload", env)
        self.assertIn("signatures", env)
        self.assertEqual(len(env["signatures"]), 1)
        self.assertEqual(env["signatures"][0]["keyid"], "test-key")

    def test_parse_envelope_structure(self) -> None:
        """Structural parsing succeeds without claiming authentication."""
        sigs = [{"sig": STRUCTURAL_SIGNATURE, "keyid": "test-key"}]
        env = create_envelope(self.bundle, sigs)
        stmt = parse_envelope(env)
        self.assertEqual(stmt["_type"], STATEMENT_TYPE)
        self.assertEqual(stmt["predicateType"], PREDICATE_TYPE)

    def test_verify_envelope_wrong_payload_type(self) -> None:
        """Wrong payloadType is rejected."""
        sigs = [{"sig": STRUCTURAL_SIGNATURE, "keyid": "test-key"}]
        env = create_envelope(self.bundle, sigs)
        env["payloadType"] = "wrong-type"
        with self.assertRaises(ValueError):
            parse_envelope(env)
        with self.assertRaises(ValueError):
            verify_envelope(env, self.verify_signature)

    def test_verify_envelope_missing_payload(self) -> None:
        """Missing payload field is rejected."""
        env = {"payloadType": PAYLOAD_TYPE, "signatures": []}
        with self.assertRaises(ValueError):
            parse_envelope(env)
        with self.assertRaises(ValueError):
            verify_envelope(env, self.verify_signature)

    def test_verify_envelope_missing_signatures(self) -> None:
        """Missing signatures field is rejected."""
        env = create_envelope(self.bundle, [])
        del env["signatures"]
        with self.assertRaises(ValueError):
            parse_envelope(env)
        with self.assertRaises(ValueError):
            verify_envelope(env, self.verify_signature)

    def test_verify_envelope_with_callback(self) -> None:
        """Callback verifies real PAE signatures against external test trust."""
        env = create_envelope(self.bundle, [])
        payload = base64.b64decode(env["payload"], validate=True)
        # Independently frame bytes so a raw-payload regression cannot pass.
        payload_type = PAYLOAD_TYPE.encode("utf-8")
        expected_pae = (b"DSSEv1 " + str(len(payload_type)).encode("ascii")
                        + b" " + payload_type + b" "
                        + str(len(payload)).encode("ascii") + b" " + payload)
        self.assertEqual(pae(PAYLOAD_TYPE, payload), expected_pae)
        env["signatures"] = [{
            "sig": base64.b64encode(self.dsse_key.sign(expected_pae)).decode("ascii"),
            "keyid": "test-key",
        }]
        seen = []

        def verify_fn(message_bytes, signature_b64, key_id):
            seen.append(message_bytes)
            return self.verify_signature(message_bytes, signature_b64, key_id)

        stmt = verify_envelope(env, verify_signature_fn=verify_fn)
        self.assertEqual(stmt["predicateType"], PREDICATE_TYPE)
        self.assertEqual(seen, [expected_pae])
        with self.assertRaises(ValueError):
            verify_envelope(env)  # Even a real signature supplies no trust root.

    def test_verify_envelope_callback_rejects(self) -> None:
        """Failing signature callback raises ValueError."""
        sigs = [{"sig": STRUCTURAL_SIGNATURE, "keyid": "test-key"}]
        env = create_envelope(self.bundle, sigs)

        called = []

        def verify_fn(payload_bytes, sig_b64, key_id):
            called.append(key_id)
            return False

        with self.assertRaises(ValueError):
            verify_envelope(env, verify_signature_fn=verify_fn)
        self.assertEqual(called, ["test-key"])

    def test_wrap_bundle_to_disk(self) -> None:
        """wrap_bundle writes a DSSE envelope file to disk."""
        output = wrap_bundle(str(self.bundle_path), signatures=[])
        env = json.loads(Path(output).read_text())
        self.assertEqual(env["payloadType"], PAYLOAD_TYPE)
        self.assertIn("payload", env)
        self.assertEqual(env["signatures"], [])
        self.assertEqual(parse_envelope(env)["predicate"], self.bundle)
        with self.assertRaises(ValueError):
            verify_envelope(env, self.verify_signature)

    def test_wrap_bundle_custom_output(self) -> None:
        """wrap_bundle writes to a custom output path."""
        custom = str(self.t / "custom.dsse.json")
        output = wrap_bundle(str(self.bundle_path), output_path=custom, signatures=[])
        self.assertEqual(output, custom)
        env = json.loads(Path(custom).read_text())
        self.assertEqual(env["payloadType"], PAYLOAD_TYPE)
        self.assertEqual(env["signatures"], [])
        with self.assertRaises(ValueError):
            verify_envelope(env, public_keys=self.trusted_keys)

    def test_roundtrip_preserves_bundle(self) -> None:
        """Unauthenticated serialization/parsing preserves the original bundle."""
        sigs = [{"sig": STRUCTURAL_SIGNATURE, "keyid": "k"}]
        env = create_envelope(self.bundle, sigs)
        stmt = parse_envelope(env)
        self.assertEqual(stmt["predicate"], self.bundle)
        # Check preserved fields; parsing does not verify bundle semantics.
        self.assertEqual(stmt["predicate"]["profile"], "kairo-legal-v3")
        self.assertEqual(len(stmt["predicate"]["events"]), 8)

    def test_missing_trust_and_empty_signatures_never_authenticate(self) -> None:
        env = create_envelope(self.bundle, [])
        self.assertEqual(parse_envelope(env)["predicate"], self.bundle)
        with self.assertRaises(ValueError):
            verify_envelope(env)
        with self.assertRaises(ValueError):
            verify_envelope(env, self.verify_signature)
        with self.assertRaises(ValueError):
            verify_envelope(env, public_keys=self.trusted_keys)

    def test_wrap_bundle_requires_explicit_signatures(self) -> None:
        with self.assertRaises(ValueError):
            wrap_bundle(str(self.bundle_path))
        self.assertFalse((self.bundle_path / "bundle.dsse.json").exists())

    def test_raw_and_event_signatures_never_authenticate_statement(self) -> None:
        env = create_envelope(self.bundle, [])
        payload = base64.b64decode(env["payload"], validate=True)
        event_bytes = json.dumps(self.bundle["events"][-1], sort_keys=True,
                                 separators=(",", ":")).encode("utf-8")
        # Correct external key, wrong signed scope: neither is DSSE PAE.
        for message in (payload, event_bytes):
            env["signatures"] = [{
                "sig": base64.b64encode(self.dsse_key.sign(message)).decode("ascii"),
                "keyid": "test-key",
            }]
            with self.subTest(scope=message[:40]):
                with self.assertRaises(ValueError):
                    verify_envelope(env, self.verify_signature)
                with self.assertRaises(ValueError):
                    verify_envelope(env, public_keys=self.trusted_keys)
        # An actual observer event signature is not DSSE authentication and
        # its key is not implicitly trusted from bundle contents.
        event = self.bundle["events"][-1]
        env["signatures"] = [{"sig": event["signature"],
                               "keyid": event["observer_key_id"]}]
        with self.assertRaises(ValueError):
            verify_envelope(env, self.verify_signature)


if __name__ == "__main__":
    unittest.main()
