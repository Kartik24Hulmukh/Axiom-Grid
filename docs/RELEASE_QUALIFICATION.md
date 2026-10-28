# Release qualification: evidence, not certification by script

**Current verdict: engineering preview; `production_qualified=false`.**
Passing focused CI does not authorize deployment on an unqualified device or
convert inherited monorepo components into a single production product.

## Why legacy tools changed

A scoped audit at base `47a0543cc50557e143e5d3b3f306a6329d870ac7` found reproducible
false approvals with synthetic temporary inputs:

| Legacy path | Counterexample | Current policy |
| --- | --- | --- |
| `generate_certification.py` | Missing or explicitly failed results still yielded hard-coded certification and invented test/memory results | Retired entrypoint refuses; import performs no report generation |
| `verify_production_gate.py` | Missing BMC/audit measurements defaulted to passing constants; impossible counts/non-finite values could pass | Explicit strict reported-evidence validation only; no automatic discovery or production approval |
| `release_check.py` | Planted passing metrics, missing measurements and invalid ranges could yield release clearance | Deterministic regression scope; no planted metric overrides, no release clearance |
| `verify_launch_checklist.py` | Constants, blank document length and an unavailable VLM yielded a launch recommendation | Retired entrypoint refuses; actual device evidence required |
| `ci/sbom_gate.py` | Missing signing capability returned success without a signature; ephemeral keys lacked approved verification identity | Legacy CLI/signing refuse; missing/erroring advisory tooling fails closed |

These legacy scripts were **not invoked by the active focused workflow** at that
base. This is a repair of misleading callable tools/documentation, not a claim
that an active CI bypass or an exploited production incident occurred. Removed
claims remain inspectable in Git history. The old release report is withdrawn as
qualification evidence, not silently reinterpreted as a real-device pass.

## Three distinct evidence layers

1. **Synthetic/deterministic regression**: validates the behavior of code and
   fixtures under the named harness. Useful, but not observed customer/model/UI
   performance. The release regression evaluator labels this scope explicitly.
2. **Reported measurements**: explicit evidence file, revision, profile, run and
   timestamp; strict shape, ranges, freshness and threshold checks. A successful
   report only means that supplied data met these scoped rules. JSON metadata is
   self-reported, not signed provenance or independent observation. A dishonest
   producer can lie about revision, time or whether data was synthetic.
3. **Target-device/distribution qualification**: independently observed native
   application/model behavior, approved artifacts, installation and operational
   controls. Neither layer above establishes this layer.

A checksum detects changes only against a trusted comparison value; it is not an
authenticated signature. Rejecting a cloud-tier API request is a policy test, not
an OS/process/network-egress measurement. No generic script can establish every
release property from user-supplied metrics.

## Reported-metric tool

Use `python scripts/verify_production_gate.py --help` for the exact required
arguments, and see `scripts/release_evidence.py` for the schema and fixed
thresholds. It requires an explicit evidence path plus expected revision/profile;
no HOME/CWD result discovery or default passing measurements are allowed. Its
successful exit is **scoped reported-data acceptance**, never production approval.
Do not fabricate an evidence file just to make a gate green.

`python scripts/release_check.py --help` describes the separate deterministic
benchmark evaluator. Report writing requires an explicit output path; it does not
replace the root release-status document automatically. Former planted-pass
shortcuts are rejected. The focused assurance runner includes negative contracts
for the new tools, not merely a happy-path report snapshot.

## Historical deterministic coverage failure and new semantic findings

A single local invocation of the final evaluator on the working tree based on
`47a0543cc50557e143e5d3b3f306a6329d870ac7` ran the actual held-out invoice fixtures
with an **explicit InvoicePack**. It **exited 1: insufficient coverage**:

| Measurement | Actual counts | Meaning |
| --- | --- | --- |
| Grounded answerable fields | 27/27 | Positive fixture coverage only |
| False refusals on answerable fields | 0/27 | Same answerable cohort |
| Refusals on unanswerable fields | **0/0** | **No negative coverage; not a measured 100% refusal rate** |
| Ungrounded renders | 0 | Fixture observation, not exhaustive proof |

The inherited benchmark reports a default 100% for a zero denominator; the new
evaluator **rejects it**, retains counts and marks the regression failed. Auxiliary
checks are not run after that blocking coverage failure. No fixtures or thresholds
were altered to manufacture success. Independent review also corrected the
intermediate wrapper's dirname-based fallback to GenericPack: that earlier
working-tree run's 50% refusal result is superseded and is not an InvoicePack result.

The current wrapper now validates both indexed corpora, snapshots their bytes, rejects missing/unindexed/symlinked sources and reconciles each document, field and aggregate count. This does not change the inherited harness everywhere else in the monorepo.

A subsequent single actual deterministic observation added four independently hand-authored negative documents without changing the three positives or thresholds. All seven documents were accounted for: grounded answers **39/39**, refusals **18/24 (75%, FAIL)**, false refusals **0/39**, ungrounded renders **0**. Exit was **1**, with regression/release/production flags false. Six lexically grounded but semantically wrong extractions exposed newline-spanning invoice labels, due-vs-issue date confusion, absent-tax defaults, arbitrary heading-as-vendor and provisional competing totals. The historical failure is retained; it is not erased by contract-test passes. Pack corrections and any later measurement must be identified separately.

No real-model quality or production qualification follows from these deterministic fixture measurements.

## Remaining blockers — not solved by these changes

- Select an exact target OS/build, CPU/RAM/GPU, backend version and model assets.
  No such customer device profile has yet been qualified here.
- The new [expected-identity policy](MODEL_IDENTITY_POLICY.md) adds required approved configuration, shared readiness/generation preflight and response-model consistency. Local Rust compilation/execution is unavailable; exact-head remote CI is required before accepting those contracts. Even passing report checks cannot attest a dishonest backend or eliminate substitution between checks; artifact/backend provenance remains separate.
- Run real compiled UI + real-model end-to-end tests on that profile, including
  disconnected cold start, missing assets, bounded resources, cancellation/quit,
  failure recovery and protected pairing. A dropped HTTP request does not prove
  backend compute stopped or sensitive context was erased.
- Enforce and observe appropriate network policy; loopback alone is not local-only
  inference proof. Qualify parser privileges/platforms separately; a child process
  is not a full filesystem/network sandbox.
- Review exact packaged dependencies, model licenses/notices, provenance and
  vulnerabilities; approve a verifiable signer. See [LICENSE_AUDIT.md](LICENSE_AUDIT.md).
- Qualify installers, update/uninstall/rollback, retention/crashes, external security
  review and operational support. Bundling stays disabled pending those gates.
- Validate usefulness and willingness to pay with consent-based permitted-task
  pilots. CI cannot establish demand, traction, a valuation or “100×” improvement.

The authoritative usage boundary is [AUTHORIZED_PREVIEW.md](AUTHORIZED_PREVIEW.md):
visible explicit input, review and manual copy on authorized devices/tasks. No
covert deployment, automatic application typing or assessment-policy bypass.
