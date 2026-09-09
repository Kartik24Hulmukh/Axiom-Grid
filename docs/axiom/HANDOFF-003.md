# Axiom-Grid implementation handoff 003

## Scope and status

Continued from main `cbe1cfd`. The user said “jittest”, but the supplied handoff and authorized repository identify **Axiom-Grid**. No separate jittest repository was supplied or modified; Kairo-Phantom was not modified.

**Working Linux native explicit-input preview, not production-ready ghost typing.** Workstreams (runtime/readiness, desktop extraction, real-model testing and security review) were executed concurrently where independent. No agent-spawning facility was available; no fictional multi-agent council was used.

## Implemented

- Authenticated `/readiness`: fixed-loopback Ollama inventory, exact configured tag, bounded response/count/name, three-second timeout, sanitized errors. Does not download/load/benchmark models.
- Model readiness/inventory UI with literal rendering, empty/unavailable states and single in-flight check.
- Extracted Tauri desktop into an independent Cargo workspace and lockfile, removed unused shell plugin, TLS/cloud-capable default reqwest features and Windows acrylic dependency. Generated platform schemas are regenerated, not source-controlled.
- Hardened native bridge: bounded JSON decoding, no proxy/redirects, actionable status messages, credentials never exposed to JS; removed misleading capture/suggestion broadcast events.
- Ephemeral paired-process Python launcher, random token per invocation, occupied-port refusal, authenticated startup, owned-child lifecycle cleanup and rapid restart support. **Not OS-keychain pairing**.
- Shortcut conflict no longer aborts app startup; shortcut only shows the window. Normal taskbar visibility restored. No automatic insertion.
- Reproducible real-model fixture smoke script; focused three-platform native build/test/Clippy CI added.

## Validation performed

| Gate | Result |
|---|---|
| Focused runtime tests | 23 passed (8 API, 6 readiness/config, 9 inherited regressions) |
| Frontend Node tests | 8 passed |
| Launcher stdlib tests | 4 passed |
| Native bridge Rust test | 1 passed |
| Runtime/native formatting, Clippy `-D warnings`, debug builds | Passed on Linux |
| Actual Tauri desktop on Linux | Readiness, real generation/display, review/discard, window-close/owned-runtime shutdown exercised |
| Real Ollama model | v0.6.8, qwen2.5:0.5b, Q4_K_M, Apache-2.0 license captured; CPU-only shared container |
| API fixture inference | 3 completed; observed 2.745s, 1.198s, 1.604s; NOT benchmark promises |
| Model quality | **FAIL:** emoji dropped/em dash changed; “today” changed to “immediately”; not an approved default |
| Rust dependency audit | Zero vulnerability-list entries, but runtime 1 unmaintained and desktop 6 unmaintained + 1 unsound warnings; unresolved |
| Windows/macOS native behavior | Not exercised; CI compilation is not behavioral certification |
| Copy across apps / accessibility / target insertion | Not certified; insertion remains disabled |
| Signed packaging / installer / updater / rollback | Not implemented |

Evidence is in `docs/axiom/evidence/`, including a screenshot of the real desktop result. Synthetic prompts only; no credentials included. Model explicitly installed by the engineer for validation; application never pulls it. Exact CPU/cgroup limits and model digest/license are recorded. Shared-container timings do not define minimum hardware. Tauri ran despite GTK/appindicator warnings, which need platform triage.

## Next engineering chunks (in order)

1. **Do not approve the tested 0.5B model.** Evaluate stronger license-compatible models with held-out editing cases: semantic preservation, names/numbers, Unicode, hallucinations and long context. Record cold/warm p50/p95, memory and hardware limits; target a release-quality default only from measured evidence.
2. Check the new CI run. Compile Windows/macOS; native QA on chosen first OS is mandatory (missing daemon/model, wrong credentials, Unicode manual copy, hotkey conflicts, crashes and restart). Add real-browser/WebDriver desktop testing rather than rely only on DOM stubs.
3. Resolve/own the dependency warnings in DEPENDENCY-REVIEW-003.md, including GLib unsoundness. Do not label the audit clean. Separate pure regression-only CRDT imports from production runtime when dependency analysis permits.
4. Replace environment-only pairing with OS-protected lifecycle-bound IPC capability provisioning. Consider embedding runtime transport in the desktop to remove a separately addressable HTTP service, after threat review.
5. Implement target-bound insertion as its own audited feature: approval binds session/content/target/expiry; revalidate focus/selection; abort changes; replay prevention; supported-control restrictions; native undo. Never force focus or blindly send Enter.
6. Prune inherited source only after dependency analysis. Focused runtime still path-imports five inherited modules. Preserve MIT provenance.
7. Signed/notarized packaging, SBOM/advisory gates, clean-machine install/update/rollback and OS-enforced network testing. Do not enable release publishing until launch gates are satisfied.
8. Validate traction honestly: recruit five design partners doing privacy-sensitive editing, measure accepted edits, time saved versus manual local-model use, meaning-change rate and weekly retention before broad launch. “100x” remains an aspiration, not demonstrated evidence.

## Launch judgement

**Production NO-GO.** A supervised manual-copy technical preview is reasonable; universal ghost typing and enterprise zero-egress claims are not. There is no credible way to guarantee product-market fit or production readiness merely by completing one engineering session.

## Credentials

Revoke/rotate the GitHub token exposed in the conversation. It was not committed. The launcher's random IPC token is separate and must never reuse a GitHub credential.
