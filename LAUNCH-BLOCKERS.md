# Axiom-Grid launch blockers — 2026-09-29

**Latest continuation:** [verified hardening and failed release bounds](LAUNCH_VERIFICATION-2026-10-02.md). TCP quiescence and explicit lifecycle proof now pass in short local runs; legitimate shedding, loaded-error latency, credential revocation, platform/deployment and human verification still block release.

**Decision: engineering preview, not general availability.** Historical focused-suite and synthetic-load passes are useful evidence, not a production certification. Do not claim 100 recruited human testers or universal sub-200 ms recovery based on one scripted run.

| Gate | Current evidence | Required to close |
|---|---|---|
| Credential safety | Melious key was committed in a tracked torture script, and a GitHub token was supplied in chat; deletion from HEAD cannot revoke history or chat exposure. | Repository owner revokes and reissues both credentials, checks audit logs and all forks/copies, stores replacements in a secret manager. Never reuse supplied values. |
| Full regression | Fresh local `tests/`: 1,178 pass / 0 fail / 9 skip; focused gate: 366 pass. This is not proof of all platforms, Rust, browser E2E, or a clean release SHA. | Fresh clean-clone Python/Rust/Node, integration and browser E2E on supported OSes, zero unexplained failures/skips, checks attached to release SHA. |
| Load and resilience | 100 synthetic personas and bursts were tested historically; no recruited humans, 24-hour soak, multi-replica test, or formal extraction-shedding SLO. | Define accepted admission and latency SLOs; run repeated burst/soak/chaos tests with P50/P95/P99, RSS and fd trends, then recruit user testers and record consented findings. |
| Trust and distribution | Local receipts and verifier exist; provenance, installer, website and third-party proof claims need independent checks. | External receipt-verifier reproduction, security review, signed installers and clean-host installs; deploy correct branded site and verify links and demos. |
| Release controls | A green focused CI badge is not a GA gate. | Enforce required checks and review on protected main; merge only after independent verification, then publish a release with evidence and rollback plan. |

`repos.md` integration choice: retain existing OTel, gitleaks and load-harness patterns; avoid vendoring large agent frameworks merely because they appear in the catalog. Verify licenses and versions before any new dependency. Five failure vectors to revisit in each test cycle: queue starvation, uncaught async errors, memory/fd growth, provider 429/5xx cascade exhaustion, and credential exposure. These are hypotheses and test gates, not a claim of a real council or real human cohort.

## Fresh checkpoint — 2026-10-01

See [current validation and operational failures](LAUNCH_VERIFICATION-2026-10-01.md). Focused tests pass, but zero-5xx, loaded error latency, FD-quiescence and shutdown-marker proof gates do not pass. No automatic merge or GA claim is authorised by local focused-suite success.
