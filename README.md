# Axiom-Grid

**Local writing. Explicit control.** A focused writing copilot derived from Kairo-Phantom.

> **Engineering preview, not production-ready.** The working slice generates a reviewable suggestion from text you explicitly provide. It does not automatically type into other applications. That feature is gated until target-bound approval and native-platform tests pass.

## What is implemented

- Independent Rust preview runtime (`axiom-runtime`), with no inherited swarm, cloud adapters, plugins, ambient screen capture or injection in its launch path.
- Direct loopback Ollama inference: no proxy use, no redirects, no automatic downloads, no configured cloud fallback.
- Native IPC bearer authorization; browser-origin and invalid Host requests denied; bounded input/output and one active generation.
- Axiom desktop preview UI with explicit context, literal text rendering and late-result discard.
- Regression coverage for Unicode, session acceptance/cancellation, model identity, CRDT replacement, API security and UI behavior.

## Start here

[Quickstart](QUICKSTART.md) · [Current handoff](docs/axiom/HANDOFF-002.md) · [Fork handoff](docs/axiom/HANDOFF-001.md) · [Launch gates](docs/axiom/LAUNCH-GATES.md)

```sh
cd axiom-runtime
cargo test --locked
cargo clippy --locked --all-targets -- -D warnings
```

An already-installed Ollama model is required for real inference. Local tests use a mock model server, not benchmark evidence.

## Scope and provenance

Imported from `Kartik24Hulmukh/Kairo-Phantom` at `8975743`. **No upstream changes.** MIT license and source history retained; inherited Rust crate names remain compatible during extraction.

Inherited release workflows and launch documents are archived in `docs/inherited/`. Broad inherited source remains outside the focused executable until dependency-safe pruning is complete. Do not treat inherited reports as Axiom launch evidence. Do not launch the legacy `kairo-phantom` binary as the Axiom product.

No claim of universal app support, certified zero egress, enterprise compliance, specified model speed, product-market fit or “100x” traction has been verified. Signed event logs cannot by themselves prove absence of network egress.
