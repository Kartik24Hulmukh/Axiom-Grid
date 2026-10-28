# Expected model identity: bounded report consistency

The focused preview requires `AXIOM_MODEL` and `AXIOM_MODEL_DIGEST` before creating pairing state or binding its listener. No inventory-derived trust-on-first-use, automatic model download, cloud fallback, or implicit alias selection is performed.

- Name: exactly 1–256 ASCII graphic bytes; whitespace, controls and non-ASCII are rejected rather than trimmed.
- Expected digest: 64 hexadecimal digits, optionally prefixed `sha256:` (case-insensitive); canonical representation is bare lowercase hex.
- Supply the expectation through an independently approved artifact/backend qualification process. Copying an untrusted backend's first report does not establish trust.

## Runtime contract

Readiness and each generation use the same bounded inventory policy: exactly one entry with the configured name, a positive size and a valid matching digest. Duplicate entries reject even when their digests agree. Schema-valid policy failures produce `200` with `ready=false`; inventory transport failure is `503`, malformed/status/size-limit failures `502`. Generation independently checks inventory before transmitting supplied context; a policy failure returns `503` without a generation POST.

The generation response must include a string `model` equal to the configured name. Missing, mistyped or conflicting identities return `502` without returning the suggestion. Readiness includes canonical `expected_digest` and `identity_check_scope: "reported-only"`. The desktop preview rejects legacy responses missing this protocol metadata. The Python evidence probe checks the same reported expectation.

The client disables proxies and redirects and targets loopback. These are useful transport constraints, not a complete security boundary. Cancellation drops the in-flight HTTP future; it does not prove that backend computation has stopped.

## What this does not prove

A malicious backend can lie consistently. Mutable model names can change between preflight and execution. Inventory digests are not verified weights, authenticated provenance, immutable execution references, offline attestation or proof of licensing. Digest-addressed generation is not assumed supported by the backend API. The configured digest and model assets require separate qualification.

Loopback mocks test policy and ordering, not real-model behavior. Native UI, actual model assets, resource limits, disconnection, installers, updates and target-platform security remain separate release gates. Production qualification remains false.
