"""Authentication regression tests; run with stdlib unittest discovery."""
import base64
import copy
import json
from pathlib import Path
import tempfile
import unittest

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)
from kairo.legal_v3.dsse_envelope import (
    PAYLOAD_TYPE, create_envelope, pae, parse_envelope, verify_envelope,
    wrap_bundle,
)

# RFC 8032 section 7.1, TEST 1 (public test-only key, empty message).
SEED = bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60')
PUBLIC = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
RFC_SIGNATURE = bytes.fromhex(
    'e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155'
    '5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b')
# Fixed locally generated DSSE vector, independently framed literal PAE.
PAYLOAD = (b'{"_type":"https://in-toto.io/Statement/v1","predicate":{},'
           b'"predicateType":"https://kairo.phantom/legal-v3/v1","subject":[]}')
MESSAGE = (b'DSSEv1 42 application/vnd.kairo.legal-v3.bundle+json 123 ' + PAYLOAD)
DSSE_SIGNATURE = bytes.fromhex(
    '6c1f8199b071d8edb5d36ad04bd347af118f9fea0808fcd9c37d1f5fc4701be42'
    '39ff3111cba36ec421ed6c0204e235f8e5fdf3f1dd4d17816a1a08d2492a708')


def b64(value):
    return base64.b64encode(value).decode('ascii')


class DSSEAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.sk = Ed25519PrivateKey.from_private_bytes(SEED)
        self.pk = Ed25519PublicKey.from_public_bytes(PUBLIC)
        self.env = {'payloadType': PAYLOAD_TYPE, 'payload': b64(PAYLOAD),
                    'signatures': [{'keyid': 'trusted', 'sig': b64(DSSE_SIGNATURE)}]}
        self.keys = {'trusted': self.pk}

    def verify(self, env=None, **kwargs):
        return verify_envelope(self.env if env is None else env,
                               public_keys=self.keys, **kwargs)

    def callback(self, message, signature, keyid):
        if keyid != 'trusted':
            return False
        try:
            self.pk.verify(base64.b64decode(signature, validate=True), message)
        except InvalidSignature:
            return False
        return True

    def test_rfc8032_positive_and_negative(self):
        self.assertEqual(self.sk.sign(b''), RFC_SIGNATURE)
        self.pk.verify(RFC_SIGNATURE, b'')
        with self.assertRaises(InvalidSignature):
            self.pk.verify(RFC_SIGNATURE, b'changed')

    def test_fixed_dsse_vector(self):
        self.assertEqual(pae(PAYLOAD_TYPE, PAYLOAD), MESSAGE)
        self.assertEqual(self.sk.sign(MESSAGE), DSSE_SIGNATURE)
        self.assertEqual(self.verify(), json.loads(PAYLOAD))
        for key in (PUBLIC, b64(PUBLIC)):
            self.assertEqual(verify_envelope(self.env, public_keys={'trusted': key}),
                             json.loads(PAYLOAD))

    def test_unicode_pae_byte_lengths(self):
        self.assertEqual(pae('é/🔒', '雪'.encode()),
                         b'DSSEv1 7 \xc3\xa9/\xf0\x9f\x94\x92 3 \xe9\x9b\xaa')
        env = create_envelope({'label': '雪🔒'}, [])
        payload = base64.b64decode(env['payload'])
        # Frame independently, without the implementation's pae helper.
        message = b'DSSEv1 42 ' + PAYLOAD_TYPE.encode() + b' ' + str(len(payload)).encode() + b' ' + payload
        env['signatures'] = [{'keyid': 'trusted', 'sig': b64(self.sk.sign(message))}]
        self.assertEqual(self.verify(env)['predicate']['label'], '雪🔒')

    def test_real_callback_receives_pae(self):
        seen = []
        def callback(message, signature, keyid):
            seen.append(message)
            return self.callback(message, signature, keyid)
        self.assertEqual(verify_envelope(self.env, callback), json.loads(PAYLOAD))
        self.assertEqual(seen, [MESSAGE])

    def test_missing_trust_and_empty_signatures(self):
        with self.assertRaises(ValueError):
            verify_envelope(self.env)
        self.env['signatures'] = []
        self.assertEqual(parse_envelope(self.env), json.loads(PAYLOAD))
        with self.assertRaises(ValueError):
            self.verify()
        with self.assertRaises(ValueError):
            verify_envelope(self.env, self.callback)

    def test_wrong_key_and_untrusted_keyid(self):
        with self.assertRaises(ValueError):
            verify_envelope(self.env, public_keys={'trusted': Ed25519PrivateKey.generate().public_key()})
        self.env['signatures'][0]['keyid'] = 'untrusted'
        with self.assertRaises(ValueError):
            self.verify()

    def test_payload_and_type_tamper(self):
        for field, value in [('payloadType', 'application/json'),
                             ('payloadType', None),
                             ('payload', b64(PAYLOAD.replace(b'{}', b'{"changed":true}')))]:
            with self.subTest(field=field, value=value):
                env = copy.deepcopy(self.env)
                env[field] = value
                with self.assertRaises(ValueError):
                    self.verify(env)
                with self.assertRaises(ValueError):
                    verify_envelope(env, self.callback)

    def test_known_signature_corruption_and_unrelated_vector(self):
        for signature in (bytes([DSSE_SIGNATURE[0] ^ 1]) + DSSE_SIGNATURE[1:],
                          RFC_SIGNATURE, b'short'):
            self.env['signatures'][0]['sig'] = b64(signature)
            with self.subTest(signature=signature), self.assertRaises(ValueError):
                self.verify()
            with self.assertRaises(ValueError):
                verify_envelope(self.env, self.callback)

    def test_event_and_raw_payload_signatures_rejected(self):
        for message in (PAYLOAD, b'{"event_type":"RUN_CLOSED"}'):
            self.env['signatures'][0]['sig'] = b64(self.sk.sign(message))
            with self.assertRaises(ValueError):
                self.verify()
            with self.assertRaises(ValueError):
                verify_envelope(self.env, self.callback)

    def test_invalid_encoding(self):
        for field in ('payload', 'sig'):
            for value in (None, 123, [], b'AAAA', '', '!!!!', 'Zg', 'Zh==', 'Zg===', 'Zg==\n', '雪'):
                with self.subTest(field=field, value=value):
                    env = copy.deepcopy(self.env)
                    target = env if field == 'payload' else env['signatures'][0]
                    target[field] = value
                    with self.assertRaises(ValueError):
                        self.verify(env)

    def test_malformed_structure(self):
        for signatures in (None, {}, 'sig', [None], [{}], [{'keyid': [], 'sig': b64(DSSE_SIGNATURE)}]):
            env = copy.deepcopy(self.env)
            env['signatures'] = signatures
            with self.subTest(signatures=signatures), self.assertRaises(ValueError):
                self.verify(env)
        for payload in (b'[]', b'null', b'\xff', b'{',
                        PAYLOAD.replace(b'"subject":[]', b'"subject":{}'),
                        PAYLOAD.replace(b'"predicate":{}', b'"predicate":[]'),
                        PAYLOAD.replace(b'"predicate":{}', b'"predicate":{},"predicate":{}'),
                        PAYLOAD.replace(b'"predicate":{}', b'"predicate":{"x":NaN}')):
            env = copy.deepcopy(self.env)
            env['payload'] = b64(payload)
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_envelope(env)

    def test_nonfinite_json_literals_and_exponent_overflow_rejected(self):
        for token in (b'NaN', b'Infinity', b'-Infinity', b'1e999', b'-1e999'):
            with self.subTest(token=token):
                payload = PAYLOAD.replace(b'"predicate":{}',
                                          b'"predicate":{"nested":[{"x":' + token + b'}]}')
                env = copy.deepcopy(self.env)
                env['payload'] = b64(payload)
                # A genuine trusted PAE signature must not mask invalid JSON.
                env['signatures'][0]['sig'] = b64(self.sk.sign(pae(PAYLOAD_TYPE, payload)))
                with self.assertRaises(ValueError):
                    parse_envelope(env)
                with self.assertRaises(ValueError):
                    self.verify(env)
                with self.assertRaises(ValueError):
                    verify_envelope(env, self.callback)

    def test_serializer_rejects_nonfinite_and_overflow_values(self):
        for value in (float('nan'), float('inf'), float('-inf'),
                      float('1e999'), float('-1e999')):
            with self.subTest(value=value):
                bundle = {'nested': [{'x': value}]}
                with self.assertRaises(ValueError):
                    create_envelope(bundle, [])
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp)
                    # Model externally supplied nonfinite/overflow bundle JSON.
                    (path / 'bundle.json').write_text(json.dumps(bundle))
                    with self.assertRaises(ValueError):
                        wrap_bundle(tmp, signatures=[])
                    self.assertFalse((path / 'bundle.dsse.json').exists())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / 'bundle.json').write_text('{"nested":[{"x":1e999}]}')
            with self.assertRaises(ValueError):
                wrap_bundle(tmp, signatures=[])
            self.assertFalse((path / 'bundle.dsse.json').exists())

    def test_finite_numbers_remain_supported(self):
        values = [0.0, -1.25, 1e308, -1e308, 1e-308]
        env = create_envelope({'numbers': values}, [])
        self.assertEqual(parse_envelope(env)['predicate']['numbers'], values)
        payload = base64.b64decode(env['payload'], validate=True)
        env['signatures'] = [{'keyid': 'trusted',
                              'sig': b64(self.sk.sign(pae(PAYLOAD_TYPE, payload)))}]
        self.assertEqual(self.verify(env)['predicate']['numbers'], values)

    def test_duplicate_keys_cannot_satisfy_threshold(self):
        self.env['signatures'] *= 2
        with self.assertRaises(ValueError):
            self.verify(threshold=2)
        with self.assertRaises(ValueError):
            verify_envelope(self.env, self.callback, threshold=2)
        self.env['signatures'][1] = dict(self.env['signatures'][1], keyid='alias')
        with self.assertRaises(ValueError):
            verify_envelope(self.env, public_keys={'trusted': PUBLIC, 'alias': b64(PUBLIC)}, threshold=2)

    def test_two_distinct_keys_meet_threshold(self):
        second = Ed25519PrivateKey.generate()
        self.env['signatures'].append({'keyid': 'second', 'sig': b64(second.sign(MESSAGE))})
        keys = dict(self.keys, second=second.public_key())
        self.assertEqual(verify_envelope(self.env, public_keys=keys, threshold=2), json.loads(PAYLOAD))
        with self.assertRaises(ValueError):
            verify_envelope(self.env, public_keys=keys, threshold=3)

    def test_invalid_trust_policy(self):
        for threshold in (0, -1, True, 1.0, '1', None):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                self.verify(threshold=threshold)
        for callback in (lambda *args: False, lambda *args: 1, lambda *args: 'yes', 1):
            with self.subTest(callback=callback), self.assertRaises(ValueError):
                verify_envelope(self.env, callback)
        def raises(*args):
            raise RuntimeError('verifier unavailable')
        with self.assertRaises(ValueError):
            verify_envelope(self.env, raises)
        with self.assertRaises(ValueError):
            verify_envelope(self.env, self.callback, public_keys=self.keys)
        with self.assertRaises(ValueError):
            verify_envelope(self.env, public_keys={})

    def test_unsigned_wrapper_is_explicit_never_event_signed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            bundle = {'events': [{'event_type': 'RUN_CLOSED', 'signature': b64(DSSE_SIGNATURE),
                                   'observer_key_id': 'trusted'}]}
            (path / 'bundle.json').write_text(json.dumps(bundle))
            with self.assertRaises(ValueError):
                wrap_bundle(tmp)
            self.assertFalse((path / 'bundle.dsse.json').exists())
            output = wrap_bundle(tmp, signatures=[])
            env = json.loads(Path(output).read_text())
            self.assertEqual(env['signatures'], [])
            self.assertEqual(parse_envelope(env)['predicate'], bundle)
            with self.assertRaises(ValueError):
                self.verify(env)


if __name__ == '__main__':
    unittest.main()
