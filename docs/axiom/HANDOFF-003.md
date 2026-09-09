# Handoff 003 — authenticated model readiness

**Status: incremental engineering-preview chunk; production remains NO-GO.**

## Completed

- Added authenticated `GET /readiness` to the focused runtime. It queries only fixed-loopback Ollama `/api/tags`, bypasses proxies, refuses redirects, and reports the configured exact model tag plus installed names, byte sizes and digests.
- Readiness uses exact tag matching; a similarly named tag does not pass. No model is downloaded and no cloud fallback exists. `/health` remains liveness only.
- Added a Tauri bridge command and startup/retry readiness card. Generation fails closed in the UI unless the configured model is present.
- Added Rust API coverage for exact-match inventory and authorization; added frontend coverage for ready and browser-only states.

## Verification in this environment

- `node --test phantom-overlay/tests/app.test.cjs`: **7 passed**.
- `git diff --check`: passed.
- Rust tests/format/clippy were **not runnable in this sandbox because no Rust toolchain is installed**. Focused GitHub CI must be green before merging/releasing; do not represent these Rust changes as locally compiled.
- Real Ollama inference and native Tauri execution remain unvalidated here.

## Next P0 chunk

1. Let focused CI compile/test this commit; fix any compiler or formatting findings.
2. On the chosen launch OS, run a real installed-model protocol (20+ representative prompts), recording model tag/digest/license, hardware/RAM, warm/cold first-token and total latency, failures and human-rated usefulness.
3. Build/run native Tauri and verify readiness, missing daemon/model, Unicode, discard, startup/shutdown and that secrets never appear in logs.
4. Replace environment-token provisioning with per-user OS-protected pairing.
5. Add cancellation propagated from UI through runtime to the in-flight Ollama request.
6. Keep automatic insertion disabled until target-bound approval, focus/selection revalidation, expiry and replay protection are implemented and native-tested.

## Honest launch gate

This improves first-run diagnostics but does not make Axiom-Grid production-ready. A design-partner preview remains conditional on CI, real-model and native-platform evidence.
