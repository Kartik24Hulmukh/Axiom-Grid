# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.3.x   | ✅ Active security updates |
| < 0.3   | ⚠️ End of life |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report security issues privately:

1. Go to the [GitHub Security Advisories](https://github.com/Kartik24Hulmukh/Kairo-Phantom/security/advisories/new) page for this repository.
2. Click **"Report a vulnerability"**.
3. Fill in the details: affected version, reproduction steps, and potential impact.

We will acknowledge your report within **48 hours** and provide a resolution timeline within **7 days**.

## Security Architecture

Kairo-Phantom is designed with security as a core constraint:

- **Zero telemetry by default.** No data leaves your machine. In sealed mode (`KAIRO_SEALED=1`), zero outbound connections are established — verified by the air-gap oracle (`pytest tests/test_airgap_zero_egress.py`).
- **Reference monitor.** The primary load-bearing security layer gates every action. PromptShield blocks 106 injection patterns; 25/25 red-team payloads blocked, 0/15 false positives.
- **Signed audit trail.** Every action is Ed25519-signed and hash-chained. Tamper any byte → verification fails. Independently verifiable via `tools/verify_receipts_external.py`.
- **Sealed build profile.** Static scan + runtime oracle confirm no network symbols in the sealed build.
- **No vendored secrets.** Kairo-Phantom contains zero hardcoded API keys, tokens, or credentials.

## API Authentication & Quotas (SEC-005 / SEC-006)

The overlay API ships in two postures, selected by environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `AXIOM_API_KEYS` | unset | Comma-separated accepted keys (>=16 chars). When set, every route except `/`, `/healthz`, `/readyz`, `/dashboard`, `/docs`, `/openapi.json`, `/static/*` requires `Authorization: Bearer <key>` or `X-API-Key: <key>`. |
| `AXIOM_REQUIRE_AUTH` | unset (`1` in the Docker image) | Production posture. If set and no keys are configured, protected routes return **503** (fail closed) instead of running open. |
| `AXIOM_RATE_LIMIT_PER_MIN` | `300` | Anonymous per-IP sliding-window budget; excess gets **429 + Retry-After**. |
| `AXIOM_RATE_LIMIT_PER_MIN_AUTH` | `3000` | Per-tenant budget for authenticated keys (bucketed by key digest, not IP). |

Design notes:

- Keys are never stored or logged in plaintext; only SHA-256 digests are held in memory and compared with `hmac.compare_digest` (constant-time). The first 12 hex chars of the digest serve as the tenant id for quotas and `request.state.tenant`.
- Invalid keys are counted against the **anonymous** per-IP bucket, so key brute-forcing is throttled by SEC-005 (verified live: `scripts/stress_sec006_gauntlet.py`).
- `/healthz` reports `auth_enabled` so operators and CI can assert the posture of a running instance.
- Rotate keys by restarting with a new `AXIOM_API_KEYS` list; supply old+new during the overlap window.
- The in-memory limiter is per-process. Run one worker per container (as the Dockerfile does) and scale horizontally behind a load balancer; move buckets to Redis before multi-replica metering.

Verification: `python scripts/stress_sec006_gauntlet.py 2000 100` boots a real uvicorn socket with auth on and asserts every auth/rate/origin/traversal invariant under 100 concurrent clients.

## Disclosure Policy

We follow responsible disclosure. Once a fix is ready, we will:

1. Release a patched version.
2. Publish a GitHub Security Advisory with full details.
3. Credit the reporter (unless they prefer anonymity).
