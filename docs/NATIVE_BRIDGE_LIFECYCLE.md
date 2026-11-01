# Native bridge request ownership

The foreground preview uses explicit text and manual review/copy. This document
covers the Rust HTTP bridge's local request ownership, not native UI or real-model
qualification.

## Failure addressed

The former bridge stored one optional cancellation sender. A second native
`materialize` invocation replaced it, dropping the first sender. Receiver closure
could be interpreted as user cancellation, and either caller's unconditional
cleanup could remove the other caller's handle. UI button disabling did not make
this shared native state atomic.

## Local ownership contract

- Reserve one native materialization lease atomically before client/token setup.
  Reject overlapping calls without replacing ownership or sending their context.
- Keep admission while sending the request and while awaiting best-effort runtime
  cancellation acknowledgement. Consuming the one-shot sender does not free it.
- Return true from `cancel_active` only when the current signal was delivered;
  repeated or idle cancellation returns false.
- Release the identity-owned lease on normal return, setup/HTTP/decode failure or
  task drop. An old lease must not clear an unrelated owner's state.
- Fail closed on a poisoned admission lock. Do not recover and claim readiness.
- Readiness probes do not acquire or replace generation ownership.

Dropping a future releases local admission; it does not itself send asynchronous
cancellation from `Drop`, prove server slot release, stop backend computation or
erase context. External clients sharing the runtime/token are outside this
bridge-local single-flight invariant. Runtime admission remains a separate gate.
A cancellation acknowledgement is not backend termination evidence.

## Contract tests and evidence strength

`axiom-runtime/tests/native_bridge_lifecycle.rs` includes the exact production
bridge module with its shared pairing implementation, without Tauri dependencies.
Eight async tests use token-bearing, header-checked loopback Axum mocks, captured contexts and
Notify barriers for ownership, overlap, cancellation acknowledgement, task drop,
setup/HTTP/decode errors, negative cancellation responses, recovery and readiness
independence. Environment changes
are serialized inside that test binary and restored; only a public synthetic
credential is used.

Run in the focused Rust profile:

```sh
cargo test --manifest-path axiom-runtime/Cargo.toml --locked --test native_bridge_lifecycle
```

These tests have no real model and do not observe a compiled desktop window,
platform shortcut or disconnected device. Local Rust execution was unavailable
when the change was prepared; exact-head remote formatting, compilation, test and
Clippy results must be checked separately before merge. The existing focused
runtime workflow runs this integration file as part of `cargo test --locked`.

## Integration decision

Cancellable job ownership is a useful design/test pattern from the prior repository
review, not a reason to import a provider registry, suite launcher or plugin
runtime. The defect is repaired with Axiom-owned state and existing dependencies.
No new filesystem, clipboard, shell, model-download, automatic insertion or
installation authority is introduced.

[Target-device qualification](DEVICE_QUALIFICATION.md) and
[release qualification](RELEASE_QUALIFICATION.md) remain required. Pairing/readiness recovery diagnostics identified by the independent audit remain
separate follow-ups, not repaired by this ownership change. Production,
offline operation, backend authenticity and customer value remain unqualified.
