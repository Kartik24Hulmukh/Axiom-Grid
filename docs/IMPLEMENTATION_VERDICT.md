# Axiom-Grid implementation verdict

> Historical phase-1 snapshot. See [continuation verdict](CONTINUATION_VERDICT.md)
> for subsequent single-parse API and probe-evidence changes. Earlier open-gate
> wording below is retained as history, not the current status of every route.

**Verdict: scoped assurance improvements implemented; NOT production-qualified.**

This is an implementation handoff, not another claim that the complete product is
finished. No native app, model, installer, customer deployment, revenue, traction,
100× gain or billion-dollar outcome was established by this work.

## Source identity and delivery

- Baseline: `aa386b49f19e160491a8e7225cc01b391ae2e522`.
- Local review branch: `fix/authorized-preview-assurance`.
- Changes are local and uncommitted; no push or merge was performed.
- The delivery patch targets this baseline. Bundle `SHA256SUMS` binds the patch,
  changed-file copies, reports and logs. `CHANGED_FILES.json` records each supplied
  file's exact digest; a HEAD alone does not identify a modified tree.
- No exposed user GitHub credential was used, tested or written into the patch.
  Revoke/rotate exposed credentials independently; ignore rules do not revoke them
  or remove secrets already in history.

## Implemented changes

| Area | Concrete change | Remaining limit |
| --- | --- | --- |
| Benchmark | Replaces fake semantic/citation scores with honest local ingestion/signing metrics; actual input hash/counts; existing-key execution; exact-byte report signature; externally anchored public-key verification; digest-bound evidence and per-record signatures | Repeated local ingestion is not agent quality, production load or honest-measurement proof |
| Benchmark file handling | Bounded regular-file reads, no final-component symlink following, private captured-byte parsing snapshot, original-byte consistency checks, strict supplied receipt schema/canonical-byte comparison | POSIX only; not a parser sandbox, immutable filesystem, same-account compromise defense or secure erasure |
| DSSE | Structural parsing separated from authentication; exact PAE verification, mandatory independent trust, actual-key threshold deduplication, no event-signature reuse, explicit unsigned serialization only | Callback mode requires caller identity uniqueness; artifact/legal/approved-intent semantics remain separate |
| Malformed evidence | Rejects duplicate JSON members, non-finite DSSE values including exponent overflow, noncanonical base64, malformed/authenticated receipt bool/float substitutions | Not a full protocol implementation audit or resource-exhaustion certification |
| Visible preview | Taskbar-visible, focused, not topmost; explicit-input/manual-copy boundary; Clear session; stale-result suppression during cancellation | No native execution was observed; clear is not backend deletion and cancel acknowledgement is not guaranteed compute termination |
| Source/config guard | Allowlist checks, common bracket/alias IPC rejection, extra asset/capability/config tripwires, portable shared Cargo config | Lexical regression guard, NOT a JavaScript parser, runtime policy, transitive-code audit or complete mediation |
| Hygiene | Decodes previously ineffective base64 ignore template, protects common key/env/cache paths, preserves maintained frontend assets | No history cleanup, credential revocation or exhaustive secret audit |
| Validation/docs | Bounded runner, pinned Python test dependencies, CI artifact configuration, migrated compatibility tests, truthful release-profile claims and API migration | Remote CI, full repository suite, native toolchain and all historical docs/registry values remain unqualified |

No capture/injection functionality, shell permissions, clipboard automation, hidden
installation, institutional bypass, assessment assistance, fleet rollout or cloud
fallback was added. Legacy Phantom mutation remains outside this release boundary.
Authorization to administer a device is separate from permission to use AI in an
assessment. Demonstrate this profile with disclosed mock/permitted tasks.

## Observed validation

Final integrated run used a fresh Python 3.13 virtual environment with installed
`cryptography==50.0.2` and `python-docx==1.2.0`; Node 24 and Git were available on
the Linux host. This is not the entire project's dependency environment. CI is
configured for Python 3.13/Node 22, but remote execution was not observed.

```bash
python scripts/run_assurance_checks.py --output /path/to/results
```

| Scoped check | Observed result |
| --- | --- |
| Benchmark assurance | 23 passed |
| DSSE authentication/finite JSON | 18 passed |
| Preview source/config guard mutation regressions | 14 passed |
| Migrated DSSE compatibility | 14 passed |
| Migrated benchmark compatibility | 2 passed |
| Existing claim-guard logic | 13 passed |
| Frontend source/VM behavior | 24 passed |
| **Distinct test total** | **108 passed; zero reported failures/skips** |
| Actual-tree source/config guard | Passed |
| Diff whitespace; changed Python AST; workflow YAML parsing | Passed |

The first three rows are the runner's combined 55-test `python-assurance` check.
Repeated runs are not extra distinct tests. Logs/results are in the review bundle;
`results.json` records exact commands, durations, exit codes and log hashes.
Test keys are disposable fixtures, not user/deployment credentials. Crypto-vector
and file tests are local evidence, not independent external certification.

**Not run:** Rust build/test/clippy (Cargo/rustc unavailable), compiled Tauri UI,
real Ollama model generation, Windows/macOS hardware, clean-host installer lifecycle,
disconnected/network qualification, full repository suite, external security review,
production load or real customer/workflow validation. Frontend VM tests are not a
native end-to-end demonstration. Configured workflows are not observed CI passes.

## Parallel review and correction loop

Two implementation agents worked on disjoint benchmark/DSSE files while a separate
read-only reviewer challenged the changes. The lead integrated preview/config/docs,
source guard and reproducibility. These are cooperating AI reviews, not independent
human auditors, real buyers or hundreds of externally validated experiments.

Review identified and corrected a pending-cancellation Clear race, unsupported-OS
failure handling, misleading timing exclusions, mutable-original reparse exposure,
legacy tests expecting permissive APIs, ignored maintained assets, env ignore gaps,
receipt bool/int/float equality confusion, DSSE exponent overflow, and common lexical
IPC blind spots. Malformed receipt tests legitimately re-sign their outer fixture
report; they do not claim an unauthenticated signature forgery. The final read-only reviewer pass reported scoped closure: 71 selected Python and
24 frontend tests passed, with no new actionable defect in the inspected changes.
That pass excludes the lead's additional 13 claim-guard tests. Remaining lexical,
native, semantic and trust-custody limits are deliberately explicit.

## Open release gates — do these next, in order

1. **Qualify one supported native profile.** Choose one authorized OS/hardware/model
   combination, reconcile Rust root/CI version drift, install its actual SDK/linker,
   build/test/clippy and run the compiled Tauri → runtime → backend flow. Record
   exact source/build/model identities and all failures. Do not enable bundling or
   sell a working installer until clean-host install/update/rollback/uninstall pass.
2. **Prove the offline boundary rather than inferring it from localhost.** Audit
   exact model/backend settings/assets/licenses and cloud modes. Measure disconnected
   cold start, generation, missing model, timeout/cancel/quit, concurrency/resource
   release and networking under an approved controlled boundary. No simulated model
   result or local endpoint substitutes for actual model provenance/E2E evidence.
3. **Close unsafe document-service surfaces before sensitive intake.** Eliminate
   the second in-process parse after child classification; implement bounded isolated
   parsing with a single validated result and fail-closed error/resource limits.
   This patch does not fix that pipeline or qualify untrusted document ingestion.
4. **Separate legal evidence authenticity from execution truth.** Independent key
   policy/custody, externally bound approved intents, independently derived expected
   effects and trustworthy observation are still needed. Writer-reported expected
   edits, embedded trust, retrospective events and integrity-to-execution-pass
   inference remain blockers; improved DSSE does not repair them automatically.
5. **Operational review.** Threat model the chosen profile, inspect transitive/native
   code and dependency/model licenses, define retention/access/key rotation/incidents,
   commission an external security review and test recovery. Replacing one parser
   does not resolve every licensing obligation.
6. **Validate value before scope expansion.** Recruit a small authorized pilot for
   one workflow, compare against its current tool using predeclared task success,
   completion time, correction burden and repeat-use/payment evidence. Measure
   retention/support economics. Do not substitute synthetic councils, features,
   repository popularity or marketing adjectives for demand.

## Historical handoff caveats

The attached stress/deployment report describes an unpushed `1ee9f9a` change and
Windows linker failures; those local changes were not present in this baseline
and were not silently assumed applied. Rust targets are additive: a Linux target
entry is not by itself proof every Windows build is blocked. Native SDK/linker
requirements remain even after removing author-specific shared paths. No historic
“green” counts, token-validity assertion, license clearance, revenue or customer
claims from that handoff were independently established here. Registry-domain
labels/numbers in STATUS remain declarations, not revalidated release evidence.

## Apply and reproduce safely

Follow bundle APPLY.md. Inspect the patch and run `git apply --check` on your actual
clean branch before applying. If your local work includes unpushed changes, review
conflicts manually; do not reset, force apply or overwrite them. Keep keys/models/
logs outside version control. See ASSURANCE_API_MIGRATION.md for intentionally
breaking APIs and AUTHORIZED_PREVIEW.md for the permitted visible profile.
