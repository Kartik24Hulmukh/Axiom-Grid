# Assurance API migration

This change intentionally breaks permissive benchmark/DSSE behavior. Do not adapt
old clients by restoring no-trust verification, dummy signatures or fake scores.
It does not migrate or validate every downstream consumer in the monorepo.

## DSSE: parse versus authenticate

`parse_envelope(envelope)` validates supported structure and decodes the statement.
It returns **unauthenticated** data. Never route its success into an authentication,
execution, compliance or legal-effect success result.

`verify_envelope(envelope, public_keys={key_id: trusted_key})` authenticates the
exact DSSE pre-authentication encoding (PAE) before returning the statement. The
mapping must come from a separately trusted authorization policy, never from keys
claimed inside the envelope or bundle. Supported mapping values are Ed25519 public
key objects, raw 32-byte public keys or canonical base64 public keys. PEM loading
must happen explicitly before calling this API; a PEM string is not a raw key.

Alternatively supply `verify_signature_fn(pae_bytes, signature_b64, key_id)`. Only
literal `True` counts. The callback must authenticate PAE, enforce trust, and map
key IDs one-to-one to identities. Callback mode cannot automatically deduplicate
aliases. For multi-key thresholds prefer `public_keys`, which deduplicates actual
key material. Supplying no trust source, both trust sources, an unsigned envelope,
or insufficient distinct authenticated keys raises `ValueError`.

`create_envelope(bundle, signatures=[])` and
`wrap_bundle(bundle_path, signatures=[])` explicitly serialize unsigned envelopes;
they do not authenticate anything. Omitting signatures from `wrap_bundle` now
fails. To sign, serialize the exact payload first, sign
`pae(envelope["payloadType"], base64.b64decode(envelope["payload"]))` using an
independently managed signer, then attach its canonical base64 signature and key
ID. Do not modify payload bytes afterward. No signer/private-key provisioning is
added here. A RUN_CLOSED event signature or signature over raw payload bytes is
not a signature over DSSE PAE and must not be reused.

Finite JSON, unique object keys and canonical base64 are required. Authentication
still does not verify artifact digests, approved-intent completeness, event capture
completeness or legal acceptance. `verify_bundle` has separate known limitations.

## Benchmark v2: local ingestion/signing only

On a supported **POSIX** host with `O_NOFOLLOW` and `O_NONBLOCK`:

```bash
python bench/verifiable_benchmark.py --tasks 3 --document /path/input.txt \
  --signing-key /private/path/ed25519-private.pem --out /path/run.json
python bench/verifiable_benchmark.py --verify /path/run.json \
  --key /trusted/path/ed25519-public.pem
```

Paths above are placeholders, not credentials. Use existing independently managed
keys. Execution does not create a key; verification requires only the separately
trusted Ed25519 public PEM, never a private key or automatic adapter setup.
Windows is intentionally unsupported for this benchmark's safe file reader; the
CLI fails rather than dropping required file-open protections.

Keep the exact report bytes, its `.sig`, its `.receipts.json` and unchanged
original input bytes. The detached signature covers exact report bytes; the
signed report binds exact evidence bytes, and each receipt authenticates its own
canonical record. Old reports/adapter exports are not accepted as v2. Outputs
must not already exist. A failed write can leave partial artifacts; discard the
whole partial set, investigate and use a new output path instead of treating a
partial set as valid evidence. Only final-path no-follow is enforced, not an
immutable filesystem or malicious same-account protection.

The measured samples are repeated local ingestion plus receipt signing, not
independent agent tasks. Complete ingestion includes its own file I/O, hashing,
parsing and metadata work. Benchmark pre/post validation hashes, private snapshot
setup, key loading, report signing and export are outside the timed interval.
Median/min/max describe only this sample. Semantic correctness and citation
quality are explicitly `unmeasured`. A signature authenticates the producer's
assertion; it does not make the timing honest or establish output correctness.

## Validation

Run `python scripts/run_assurance_checks.py` with the pinned test dependencies
listed in README. Compatibility tests now exercise strict behavior, not the old
insecure contract. See IMPLEMENTATION_VERDICT.md for actual scope and open gates.
