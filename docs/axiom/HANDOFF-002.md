# Handoff 002 — executable local preview and safety foundation

**Status: engineering preview. NOT a complete ghost-typing release.**

## Work completed

1. Added `axiom-runtime`, an independent Cargo workspace compiling the focused preview executable without the inherited GUI/swarm/cloud dependency graph. It shares the actual revised Ghost/session/CRDT/bootstrap/security modules rather than test-only copies.
2. Implemented explicit-context -> fixed-loopback Ollama -> structured preview response. No cloud fallback, ambient app capture, automatic model download, arbitrary URLs or automatic text insertion. HTTP redirects and environment proxies are disabled.
3. IPC authentication uses a separate 64-hex-character local secret. Missing/invalid configuration prevents startup. Privileged requests require the exact loopback Host, no browser Origin/fetch metadata, and the bearer secret. No auth bypass or token logging.
4. Bounded input, output, inference duration and concurrency; errors are generic and do not disclose model content. Process liveness is explicitly distinct from model readiness.
5. Replaced misleading overlay with Axiom explicit-input/review/discard UI. Literal text rendering prevents model-output HTML execution. Discard ignores late results, prevents overlapping requests and states that model execution may continue. Native bridge now authenticates, bypasses proxies, refuses redirects and checks HTTP status. CSP enabled; shell plugin initialization removed; screenshot protection disabled.
6. Removed privileged legacy `/inject`, `/ask`, ambient `/context`, mobile, image and export routes from the legacy API router. Legacy materialize is now preview-only and requires explicit context. **Other legacy execution paths remain unsafe/unverified and are not the Axiom launch binary.**
7. Fixed UTF-8 slicing, Unicode whitespace acceptance/undo, cancellation late tokens, async mutex blocking panic, review-only/low-confidence/empty acceptance, CRDT document offset replacement, model-prefix matching, silent model pulls and false-success downloads.
8. Archived inherited release automation; introduced focused CI; retained MIT attribution and source history.

## Evidence actually obtained

- Rust stable 1.98.1: focused debug build succeeded.
- `cargo test --manifest-path axiom-runtime/Cargo.toml --locked`: **17 passed, 0 failed, 0 ignored**.
- `cargo clippy --manifest-path axiom-runtime/Cargo.toml --locked --all-targets -- -D warnings`: passed.
- `cargo fmt --manifest-path axiom-runtime/Cargo.toml --check`: passed in final verification.
- `node --test phantom-overlay/tests/app.test.cjs`: **5 passed**.
- Real executable HTTP smoke against a **mock loopback Ollama server**: authorized request generated the expected Unicode response; unauthorized request returned 401; exactly one inference call. Deliberately broken proxy environment did not redirect local inference.
- Evidence logs in `docs/axiom/evidence/`. No real model inference, native Tauri execution, Windows/macOS app insertion or signed installer was validated.
- Inherited full-core `cargo check --lib --locked` was attempted and blocked by missing Linux `xi` development metadata. That is not a passing build. Do not infer full-core correctness from the focused crate's tests.

## Scope decisions / correction of attached audit

The attached document claims universal app support, exact latency/grounding metrics, “100x” traction, six deployed agents and cryptographic proof of zero egress without reproducible evidence. Those are not accepted as verified requirements or launch facts. Logs/signatures establish integrity of recorded events, not absence of unobserved networking. A preview-only, explicit-control wedge is safer and testable; it is not the finished differentiating ghost-typing product.

No independent agent-spawning facility was available in this run. Source inspection, build work and tests were parallelized where practical; this was not a fabricated multi-agent council.

## Next chunk: native preview + real inference (P0)

1. On one supported OS, install an appropriate real Ollama model; run `QUICKSTART.md`. Record exact model digest/license, hardware, RAM, first-token/total latency and quality across at least 20 realistic prompts. Do not use hardcoded invented benchmark claims.
2. Build and run Tauri with platform prerequisites. Verify token propagation, CSP/IPC, explicit-input focus, missing-model errors, discard, Unicode copy, startup/shutdown and no secret logs. The overlay is still nested in the inherited Cargo workspace; isolate it if that pulls unnecessary dependencies.
3. Add native-platform CI and real-model smoke as an explicit opt-in gate. Existing focused CI does not prove native integration.
4. Add per-user OS-protected credential pairing instead of manual environment provisioning; avoid cloud credential reuse.
5. Implement model inventory/readiness in the UI, with explicit model selection and user-approved download progress. Keep offline mode fail-closed and never silently fall back.

## Next chunk: safe insertion (P0, separate handoff required)

- Capture target process/window/element identity and selection revision while user explicitly initiates the operation.
- Bind approval to a session ID, content hash, target, and expiry. Revalidate immediately before any write; reject focus/selection changes and stale/replayed approvals.
- Keep preview separate from execution. Do not force focus, blindly replace lines, or simulate Enter in terminals/chats. Fail closed on unsupported controls/password inputs.
- Use a platform-supported write/paste adapter with transaction/undo semantics and clipboard restoration policy. Test races, cancellation, process exit, permissions, Unicode/graphemes, multiline input and user edits on real apps.
- Choose one OS and two ordinary text editors first. Office files, Figma/Canva canvas automation and DOM agents are out of first-release scope.

## Extraction and release backlog (P1)

- Delete unused legacy application segments only after import/dependency analysis; currently excluded from the independent executable, not broadly deleted.
- Refine GhostSession's public mutable state into encapsulated transition methods; the new safety methods guard their own paths but cannot prevent external mutation through public fields.
- Connect cancellation to server-side inference lifecycle; current discard is UI discard only.
- Add fuzz/property tests, content-length/chunk timeout tests, load tests and graceful shutdown with bounded draining.
- Threat-model local malicious processes/model-daemon compromise, prompt injection, persistent model logs, network observation, dependency audit and SBOM.
- Signed/notarized packaging, installer/update/rollback/uninstall, clean-machine tests and support docs. No automatic publish until gates pass.
- Retained startup/background functions are legacy only; remove old “100x” and readiness claims as those modules are retired.

## Launch judgement

Production NO-GO now. Target September 16/17, 2026 only for a gated design-partner preview if real-model + native UI tests pass. High impact/traction are hypotheses to validate with users, not something source changes can guarantee. See `LAUNCH-GATES.md`.

## Repository / credential discipline

Only `Kartik24Hulmukh/Axiom-Grid` is the write target. Source Kairo-Phantom is untouched. The GitHub token supplied in the task must be revoked/rotated because it was exposed in conversation. Never commit it, include it in handoffs, or reuse it for local IPC.
