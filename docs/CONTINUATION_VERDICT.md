# Axiom-Grid continuation implementation verdict

**Status: further defensive code implemented; NOT production-qualified.**

This continuation closes the known parent-reparse gap in one document extraction
route and improves the validity of future smoke-test evidence. It does not make
all Axiom-Grid surfaces end-to-end qualified, prove an actual local model, or
establish demand, retention, 100× improvement or a billion-dollar outcome.

## Source and delivery

- Original baseline: `aa386b49f19e160491a8e7225cc01b391ae2e522`.
- Local branch: `fix/authorized-preview-assurance`; local changes remain uncommitted.
- No push/merge, deployment or authenticated GitHub access was performed. The exposed
  GitHub credential was not used/tested; revoke/rotate it independently.
- The bundle includes a cumulative patch from the original baseline and an
  incremental patch from the exact previous 24-file delivery. **Choose one**, not
  both. Verify your starting tree and run `git apply --check`; do not discard local
  work or force conflicts. APPLY.md gives the exact starting-state instructions.
- CHANGED_FILES.json and SHA256SUMS bind source copies, patches, logs and review
  notes. Digests are byte-integrity evidence, not independently signed authorship.

## What changed in this continuation

### 1. Single captured-byte parse and full graph reuse

The extraction endpoint previously classified child-produced text, then parsed the
original file again in the parent orchestrator. Now one admitted bounded source
capture goes to a private snapshot and one parser invocation. Validated chunks,
actual Document, pages, hash, IDs, source types, geometry, embeddings and timestamp
are reused for both classification and orchestration through a copying in-memory
adapter. Returned document identity now matches request-store/provenance identity.

Final-component source replacement by FIFO/symlink is rejected using POSIX
no-follow/nonblocking opening plus regular-file/size checks. This is not full
filesystem confinement. Original replacement/deletion after capture cannot change
the captured bytes subsequently parsed; underlying filesystem reads are not claimed
atomic against a hostile local account.

### 2. Safe result transport and fail-closed resource profile

Child-controlled pickle/Queue result transport and its join-before-drain deadlock
were replaced by a capped atomic JSON result file. Strict parent validation checks
schema/types, duplicate keys, nonfinite/overflow numbers, normalized finite geometry,
route-safe unique IDs, references, page counts, dimensions, hashes and aware timestamp,
plus input/output/text/count/embedding budgets. A genuine 1 MiB parser result and
a genuinely hung child are tested.

Default is POSIX process mode with resource setup before parser work, remaining
monotonic budget, group cleanup and direct-child reap. Unsupported prerequisites,
invalid configuration and malformed output fail closed without parent parsing.
Explicit thread mode remains trusted-development-only, validated but not killable.
See PARSER_BOUNDARY.md for hard ceilings and exact threat-boundary limitations.

### 3. Worker lifecycle regression coverage

The existing worker-owned capacity rule is preserved: a cancelled/timed-out waiter
does not free capacity while work still runs. New persisted regressions cover queued
cancellation (no source I/O, one release) and executor-submit failure (one release).
Existing context/native guard tests were migrated to an explicit valid thread-mode
fixture instead of invalid missing provenance. No security fallback was restored.

### 4. More trustworthy smoke evidence

The opt-in loopback probe now labels locality/offline/native/production as unverified;
checks reported inventory, version/show/loaded metadata consistency; rejects
conflicting model-name/digest aliases; validates exact boolean cancellation and
integer response counts; caps response bytes; privately/boundedly reads POSIX pairing
files; validates environment token format; refuses report overwrite; persists only
sanitized error types and recursively redacts exact-token echoes, including numeric
values/keys. Simulated complete-probe tests cover valid and invalid HTTP contracts.

These are tests OF THE PROBE using socket-free fixtures, not a real-model test.
Self-reported digests do not authenticate weights; cancellation HTTP 499 does not
prove backend compute termination; exact-token redaction is not universal DLP,
encoded-secret detection or secure erasure. The poll's nominal short window can
include a longer bounded HTTP request; no hard cancellation-latency SLA is claimed.

### 5. Reproducible selected service profile

`scripts/run_assurance_checks.py --document-service` includes the prior assurance
checks plus selected service/admission/context/lifecycle/compatibility regressions.
`requirements-assurance.lock` pins the disposable Linux/Python3.13 environment,
including transitive versions. It is not the full project's runtime lock, artifact-
hash supply-chain proof, vulnerability review or license clearance. CI is configured
for Python3.13/Node22 but was not remotely executed; local tests used Node24.

## Executed verification

Final integrated run: **191 selected tests passed**, zero reported test failures
or skips, plus actual-tree source/config and whitespace checks passed.

| Selected suite | Passed |
| --- | ---: |
| Combined assurance: 23 benchmark +18 DSSE +14 source guard +18 isolated ingestion +11 probe | 84 |
| Migrated DSSE compatibility | 14 |
| Migrated benchmark compatibility | 2 |
| Existing claim-guard logic | 13 |
| Frontend source/VM tests | 24 |
| Selected service/admission/context/lifecycle and legacy isolation tests | 54 |
| **Total in this profile** | **191** |

Results/logs include exact commands, durations, return codes and SHA-256 values.
New tests include real spawned TXT/MD/PDF/DOCX parsing through the HTTP endpoint,
real orchestrator/store/grounding/provenance and forbidden parent-parser assertions.
Gateway fixtures reject inference; no real model or external inference is involved.
The 1 MiB child-result and actual hung-child kill/reap tests use real subprocesses.
Remaining dependency deprecation warnings are not runtime qualification.

The exported patches are also replayed and the same selected profile rerun before
packaging; replay results are included separately. Repeated runs do not increase
the distinct test denominator. Source AST and workflow YAML parsing passed.


Expanded overlay execution is deliberately reported separately because it overlaps
the selected profile: **211 passed, 2 failed**, not a clean full-overlay result.
The two failures were:

1. A chmod-000 unreadability expectation on this privileged host. A separately
   created synthetic chmod-000 file was demonstrably still readable here, so the
   test returned 200 rather than expected 422. This is an environment-sensitive
   expectation, not evidence of complete permission/tenant-policy qualification.
2. A 600-request malformed-surrogate burst missed its P50 <200ms threshold:
   **203.932ms**, with P95 714.240ms/P99 739.716ms. It had zero 5xx and healthy
   recovery, but the threshold failure remains real. This test does not reach the
   parser. No threshold or assertion was loosened to obtain a green report.

Raw expanded output is included. Do not add overlapping test runs/reviewer subtests
as extra distinct production tests. Earlier failed exploratory runs and their causes
remain in agent handoffs. Configured CI is not an observed remote pass.

## Parallel implementation, adversarial review and fixes

Two disjoint implementation agents worked on the parser boundary and service
integration; a separate read-only agent reviewed both plus the lead's probe changes.
These are cooperating AI reviews, not independent human audits or simulated buyer
evidence. The final review reported no further actionable defect identified within
its inspected scope after these demonstrated P2 counterexamples were corrected:

- Child IDs with query/fragment/control characters corrupted source links → strict
  ASCII route-compatible ID grammar and actual malicious-result regressions.
- Duplicate loaded model names with conflicting digests could pass → uniqueness over
  all same-name entries plus digest/alias validation.
- Truthiness and bool/int equality admitted malformed cancellation/counts → exact
  types and complete simulated success/failure probe regressions.
- An all-decimal token echoed as an integer survived redaction → numeric scalar/key
  representation checking and a regression with a public synthetic token.

The lead subsequently persisted the reviewer's queued-cancel/submit-failure checks
and reran the integrated profile. Review notes include exact inspected hashes and
commands. Final delivery manifests identify later test/docs changes separately.

## Remaining blockers — no blanket production claim

1. **Native product E2E:** Rust/Cargo, compiled Tauri UI, real approved Ollama model,
   named OS/hardware performance, disconnected cold starts/failure/cancel behavior,
   network observations, backend termination/resource release, signed installer,
   upgrade/rollback/uninstall and independent reproduction are still untested here.
2. **Hostile-code and whole-service boundary:** the child retains the service user's
   filesystem/network/environment privileges. It is not a restricted container/VM/
   OS sandbox. Descendants can escape a process group; filesystem/process operations
   and uninterruptible kernel I/O have no universal Python deadline. Post-parse
   pipeline work and thread dev mode can outlive the HTTP waiter. Other ingestion
   routes, ancestor path races, storage quotas, auth/tenant policy and private-data
   intake require separate review before the whole Python service is exposed.
3. **Durable click-to-source:** per-request store/provenance is not persistent and
   existing source routes are not demonstrated artifact/evidence retrieval. Correct
   IDs/geometry alone do not make that user workflow end-to-end complete.
4. **Legal/evidence semantics:** embedded trust, independently complete approved-
   intent/effect checking, retrospective observation and private-key custody remain
   unresolved. Strict DSSE is byte authentication, not legal or execution truth.
5. **Operations:** resolve/reproduce the broad test failures on the intended non-
   privileged deployment profile; benchmark realistic load; validate retention,
   incident/recovery and key rotation; audit dependency/model licenses/security;
   obtain an external scope-specific security review.
6. **Product value:** recruit real authorized users for one workflow, compare actual
   success/time/correction burden with the incumbent, measure repeat use/payment,
   retention and support economics. More agents/frameworks or a polished demo do
   not prove demand. No traction evidence was gathered in this code continuation.

## Practical next decision

Use this as a reviewable POSIX extraction-boundary candidate, not a launch build.
First reproduce the two broad failures and selected tests on a non-privileged target
host. Then choose ONE release workflow and supported OS/model combination. For the
writing preview, qualify the actual native/model path with disclosed mock/permitted
tasks. For document extraction, finish OS/route isolation plus durable source retrieval
and validate customer usefulness. Do not merge those profiles into a single universal
readiness claim or turn on covert/automatic-typing deployment.

No hidden installation, capture/injection, assessment assistance, fleet deployment,
security-policy bypass or new automatic desktop mutation was added. Authorization
to administer a device is separate from permission to use AI in an assessment.
