# Axiom-Grid

**Engineering preview — explicit input, visible review, manual copy.**

Axiom-Grid contains several experimental systems, not one uniformly qualified
product. The focused desktop lets a user supply text explicitly and review a
model suggestion. It does not automatically capture or type into other apps.
There is no production-readiness, universal-app, accuracy, compliance or
whole-machine zero-egress certification for this release profile.

See [review publication scope](docs/PUBLISHING_REVIEW.md) for the distinction
between archived local-validation verdicts and current GitHub publication/CI state.

## Release profiles and boundaries

| Profile | What exists | What is not established |
| --- | --- | --- |
| Focused desktop + `axiom-runtime` | Explicit-text preview, readiness check, authenticated runtime requests, discard/cancel signal, manual copy | Qualified native installers, real-model performance, cross-platform E2E, confirmed model termination, certified offline operation |
| Python document API (`make serve`) | Python Uvicorn API and extraction/grounding code | A Rust-enforced kernel boundary; complete parser isolation; production approval |
| Legal-v3 research | Source/intent/output bindings, local approvals, signed events and OOXML checks | External identity trust, independently complete approved-intent checking, independent real-time observation, legal correctness |
| Legacy Phantom | Experimental capture/injection/document-writing code | A supported automatic-typing release; excluded from the focused preview's capability promise |
| OpenBot adapter | Manually called signed-log SDK | Automatic interception of every real OpenBot action or a production integration |

**Only use on devices and tasks you are authorized to use.** Device-administration
permission does not grant permission for AI in an assessment. No covert deployment,
concealed assessment aid or bypass of institutional security policy is supported.

See [release qualification and retired certification tools](docs/RELEASE_QUALIFICATION.md)
for evidence requirements and the remaining native/model/distribution blockers.

## Review and validation commands

These commands test deliberately narrow behavior; passing them does not qualify a
native application or establish business traction. Run from the repository root.
Use Python 3.13, Node and Git on a POSIX development host. Install the selected
profile's pinned test dependencies (`requirements-assurance.lock`) into a disposable
virtual environment, not an existing production environment. This is not the full
project runtime or a supply-chain certification. JavaScript uses Node's built-in runner.

```bash
python -m pip install -r requirements-assurance.lock
python scripts/run_assurance_checks.py --document-service
# Or run the narrow suites directly:
python -m unittest discover -s tests/assurance -p 'test_*.py' -v
node --test phantom-overlay/tests/*.test.cjs
python scripts/check_authorized_preview.py
```

For native runtime validation on a properly equipped development host:

```bash
cargo test --manifest-path axiom-runtime/Cargo.toml --locked
cargo clippy --manifest-path axiom-runtime/Cargo.toml --locked --all-targets -- -D warnings
```

Those Rust commands were not run in the implementation sandbox: Rust/Cargo and
native SDKs are unavailable there. A configured CI job is not a verified CI result.
See [latest continuation verdict](docs/CONTINUATION_VERDICT.md) for actual commands,
results and unresolved gates for this branch.

## Focused preview requirements

The intended route is Tauri → authenticated loopback `axiom-runtime` → Ollama.
Install/approve the backend and model separately. The visible UI accepts only the
text the user chooses to provide and does not insert results into another app.
`Clear session` clears the input/output shown in this window; it is not secure
memory erasure or proof that backend/OS logs retain nothing.

Ollama can support cloud models behind a localhost endpoint. Thus localhost alone
is not proof of local inference. Backend configuration, exact model/assets,
licenses, disconnected cold starts, external networking and cancellation resource
release still require qualification. No cloud fallback is authorized by an offline
promise. See [authorized preview](docs/AUTHORIZED_PREVIEW.md).

Windows currently requires an explicitly configured shared IPC token; automatic
protected file pairing is Unix-specific. Tokens must be provisioned privately; do
not paste them into chat, commit them, log them or reuse exposed credentials.

## Document API is a separate experimental surface

`make serve` starts `overlay.server:app` directly through Python/Uvicorn. It does
not automatically put parsing behind the Rust kernel. `/api/extract-document`
(and `/api/ask-document` when it delegates to it) now uses one captured-byte parse
with a validated full graph, reused for classification and the orchestrator. The
default is a killable POSIX child with bounded JSON results; explicit `thread`
mode is trusted-development-only and not killable. Unsupported process prerequisites
fail closed. See [parser boundary](docs/PARSER_BOUNDARY.md).

This is not an OS sandbox: the child retains user filesystem/network privileges.
Other routes, including legacy demo/figure/source behavior, are not qualified by
this change. Do not expose the whole service to untrusted/sensitive intake or infer
the desktop preview's narrower capability boundary applies to it. Returned identity
consistency is not a durable/resolvable click-to-source guarantee.

The opt-in `scripts/axiom-live-e2e.py` probes loopback HTTP contracts using synthetic
prompts. Its success is not backend-locality, native-UI, offline, usefulness or
production proof. Metadata reports must be consistent; inspect its explicit limits.

## Evidence and benchmark semantics

- Signatures authenticate particular bytes under a trusted key; they do not prove
  semantic correctness, legal adequacy, capture completeness or absence of traffic.
- The benchmark is an **ingestion/signing microbenchmark**, not an agent-task,
  citation-quality or production-load evaluation. Unmeasured quality is not 100%.
- Benchmark report verification must use a separately trusted public key and
  authenticate report content plus referenced evidence. A key embedded by the
  producer does not establish authorization.
- DSSE structural parsing is not authentication. Use a trusted signature verifier
  over DSSE pre-authentication encoding. Explicit unsigned wrapping (`signatures=[]`) is serialization,
  not a signed attestation. See [assurance API migration](docs/ASSURANCE_API_MIGRATION.md).
- The adapter's historical export is a JSON object despite its `.jsonl` filename;
  that legacy format is not a standardized receipt protocol or complete mediation.

See [claims register](CLAIMS.md). Registry labels/historical pass counts in
`STATUS.md` and archived documents are not current release qualification.

## What must happen before production claims

A named OS/hardware/model/workflow matrix, native build/install/uninstall evidence,
real-model E2E and failure tests, scope-specific security review, privacy/retention
and incident procedures, dependency/model license review, and independent
reproduction are still required. Commercial value additionally requires real
users, comparative outcomes, repeat purchases and viable support economics.

## License

Root source is MIT; consult `LICENSE`. Dependency, model, asset and service terms
are separate. No blanket distribution/license clearance is implied.
