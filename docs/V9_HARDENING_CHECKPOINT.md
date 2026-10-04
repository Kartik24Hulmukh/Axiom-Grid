# V9 security checkpoint — release remains NO-GO

Date: 2026-10-03  
Branch: `harden/axiom-grid-v1-launch-v8`  
Base: `d3f25422685052cccd3e5c6b232dc74304027b0b`

V9 closes two critical confidentiality/authorization defects and makes the
retained transport failure diagnosable. It does not convert incomplete
deployment, licensing, platform, human, or commercial evidence into a launch
claim.

## Delivered

### Authenticated memory exports

- Replaced deterministic SHA-256/repeating-XOR obfuscation with a versioned
  AES-256-GCM envelope.
- Added per-export random 16-byte salt and 12-byte nonce.
- Added scrypt key derivation and authenticated format metadata.
- Removed the deterministic default passphrase.
- Plaintext and legacy XOR imports now fail closed.
- Added 64 MiB/100,000-record bounds.
- Added atomic `0600` writes plus symlink and hardlink rejection.
- Added wrong-key, tamper, randomness, plaintext, legacy, mode, symlink, and
  hardlink regressions.

### Enterprise authorization quarantine

- RBAC now denies unknown principals by default.
- Only the generated local agent identity receives an explicit default rule.
- JIT token validity now checks Ed25519 signature and time bounds.
- Placeholder OIDC verification denies every token.
- Placeholder MCP OAuth authorization denies every tool.
- Placeholder cloud sync returns an explicit disabled error.
- Disabled directory mapping no longer grants administrator privileges.

These changes intentionally quarantine incomplete enterprise features instead
of pretending that prefix checks or comments constitute authorization.

### Transport correlation

- Every httpx torture request now receives a deterministic bounded
  `X-Request-ID`.
- Status-zero results retain request ID and transport exception class.
- A new correlated run completed with zero transport errors and zero status
  mismatches.

## Validation

### Passed

- Expanded strict gate: **596 passed**.
- Authenticated export security suite: **5 passed**.
- Ruff, Python compilation, workflow YAML, shell syntax, and diff checks pass.
- Correlated loopback torture:
  - **4,500 requests** across health, hostile, extraction, and synthetic-client
    phases plus **200** post-abandon recovery calls.
  - Zero status mismatches.
  - Zero transport errors.
  - Zero 5xx.
  - No unhandled exception markers.
  - Clean shutdown and FD return to idle.

### Retained failure

The httpx producer still fails its requested loaded error-latency bound:

- Hostile phase error P95: **399.072 ms**, max **831.279 ms**.
- Mixed synthetic-client error P95: **1,335.428 ms**, max **4,517.005 ms**.
- Server policy duration for the pure hostile phase remained bounded:
  P95 **3.892 ms**, max **15.221 ms**.

The independent native TCP harness previously passed the same candidate with
fuzz max **76.888 ms** and zero transports/5xx/FD growth. The discrepancy is
now isolated from transport loss but is not waived. It requires repeated
candidate-container runs and a formally approved end-to-end SLO definition.

## Unverified locally

- Rust/Cargo tooling is unavailable in this execution environment. Rust source
  regressions and `cargo check` are wired into active CI but are not locally
  attested.
- Remote CI has not run on this branch.
- No live provider calls, production deployment, signed installers, backup
  restore, rollback, or 24-hour soak were performed.
- Synthetic clients are not recruited humans.

## Remaining launch blockers

1. Revoke and audit every credential exposed in chat or repository history.
2. Run and pass remote Rust/Python/Node/browser/container CI on a frozen SHA.
3. Resolve the PyMuPDF/EbookLib distribution-policy contradiction.
4. Replace or withdraw mutable and unauthenticated one-line installers.
5. Implement reviewed OIDC/JWKS and MCP authorization before re-enabling
   enterprise authentication; the current safe state is disabled/deny.
6. Move identity private keys to an OS keystore and harden first-run custody.
7. Resolve the httpx loaded latency gate on the deployment-equivalent
   container; preserve all failed evidence.
8. Complete cross-platform signed artifacts, clean-host upgrades, telemetry,
   TLS, retention/erasure, backup/restore, rollback, and a monitored soak.
9. Correct public-site claims/accessibility drift and run consented human
   evaluation and commercial validation.

## Release decision

**NO-GO for merge to `main`, GA, live-provider enablement, sensitive paid
intake, or production deployment.** The code is materially safer, but a product
cannot be made production-ready by relabeling unresolved operational,
licensing, platform, and human-evidence gates.