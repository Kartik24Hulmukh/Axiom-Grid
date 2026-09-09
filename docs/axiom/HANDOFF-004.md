# Axiom-Grid — Handoff 004

Repository: https://github.com/Kartik24Hulmukh/Axiom-Grid
Commits pushed to `main` this session:
- `4938e9f` — `fix(ci): apply rustfmt formatting to readiness API tests`
- `12dfdcb` — `feat(overlay): propagate user cancellation to the in-flight local request`

**Status: focused CI gate is GREEN on main for the first time; production remains NO-GO pending real-model and native-platform evidence.**

## Completed this session

### 1. CI unblocked (P0 #1 from Handoff 003 — DONE)
- Run #2 on `a1c4fad` failed at `cargo fmt --check` with two rustfmt diffs in `axiom-runtime/tests/api.rs`. Applied the exact expected formatting (`4938e9f`).
- CI on `4938e9f` completed **success**: fmt, `cargo test --locked`, `clippy -D warnings`, `node --test`, `cargo build --release` all green on rust 1.98.1 / node 22.

### 2. Cancellation propagation (P0 #5 — implemented)
- Frontend: Cancel while pending invokes the new `cancel_materialize` command; cancel with no pending work stays local and never calls the backend.
- Tauri: new `cancel_materialize` command emits `phantom:status = cancelled` when an in-flight request was aborted.
- Bridge: `materialize` races the request against a oneshot cancel channel via `tokio::select!`; a `OnceLock<Mutex<Option<oneshot::Sender<()>>>>` slot holds the active handle. Abort drops the reqwest future, closing the loopback connection; axum drops the `/materialize` handler, which drops the runtime’s in-flight Ollama request. No new endpoint or replay surface.
- Tests: 2 new frontend tests; **9/9 pass**, `node --check` clean.

## Verification

- `node --test phantom-overlay/tests/app.test.cjs`: 9/9 pass; `node --check` pass.
- CI on `4938e9f`: green. CI on `12dfdcb`: running at handoff; `axiom-runtime` untouched, node tests pass locally.
- Caveat: `src-tauri` is NOT compiled by CI and this sandbox has no Rust toolchain, so the bridge/command Rust in `12dfdcb` is conservative but compiler-unverified.

## Next P0 work

1. Add `cargo check` of `phantom-overlay/src-tauri` to CI (needs `libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev` on ubuntu-latest); fix findings.
2. Real installed-model protocol on the launch OS (20+ prompts; record tag/digest/license, hardware/RAM, warm/cold latency, failures, human-rated usefulness).
3. Native Tauri run: readiness, cancel-mid-generation against a real slow model, missing daemon/model, Unicode, startup/shutdown, no secrets in logs.
4. Replace `AXIOM_API_TOKEN` env provisioning with per-user OS-protected pairing.
5. Keep automatic insertion disabled until target-bound approval, focus revalidation, expiry and replay protection are native-tested.

## Honest launch gate

Green CI is a real milestone and cancellation closes a genuine UX/safety gap, but Axiom-Grid is still not production-ready: no real Ollama inference, no native Tauri run, bridge crate compiler-unverified. Design-partner preview remains conditional on items 1–3.

**Security: rotate the GitHub PAT exposed in the task conversation immediately.**
