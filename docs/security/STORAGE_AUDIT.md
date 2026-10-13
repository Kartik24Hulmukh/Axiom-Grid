# Independent scoped storage security audit

Date: 2026-10-02. Baseline: `e2b9d42` on isolated `council/security-v5` worktree.
Scope: `kernel/sidecar/evidence_store.py`, `overlay/document_store.py`, one shared
local-custody helper and new security tests/docs only. No server, admission,
policy, gateway, frontend, CI or load-producer edits. Read latest fourth-council
report, `docs/FOUNDER_PILOT_QUALIFICATION.md` and `repos.md` before source changes.

**Decision: narrow local security improvement; NO-GO for GA/paid sensitive intake.**
No encryption, identity IAM, production erasure, real-human evaluation or traction
claim is justified. This review is a local code audit and synthetic tests only.

## Findings and bounded design

| Severity / finding at baseline | Concrete evidence | Disposition |
|---|---|---|
| High: namespace symlink escapes owned uploads | Existing `local` symlink redirects save to outside directory; reopen's `is_dir()` follows it and deletes matching orphan-looking files outside root | Reject root/components/namespaces; owner/mode checks, no-follow regular files, all purge/recovery targets validated before deletion |
| High: database/sidecar symlink or hardlink adoption | Both stores open database before chmod; database and WAL/SHM victims can be followed/touched; root `resolve()` erases symlink evidence | Private roots, no-follow single-link owned regular files; DB/WAL/SHM/journal custody checked, DB created `0600` before SQLite |
| High: damaged schema passes readiness | `SELECT 1` succeeds after required table drop; wrong document-only primary key can be adopted despite intended composite tenant key | Exact required schema, PK/FK declarations, quick-check/foreign-key integrity; no silent table repair; startup/migration serialized with publisher writer lock |
| High: corrupt upload metadata enters path/quotas | Invalid suffix was accepted on resolve; negative, mismatched and non-numeric byte counts were accepted and could bypass/harm accounting | Validate ID/suffix/bytes/time and actual copy size before read/quota accounting; no arbitrary metadata-derived filesystem deletion |
| Medium/high: malformed evidence exposed as graph | Payload `{}` returned from direct graph read; only downstream consumers might fail | Validate size, graph shape, dataclass/enum reconstruction, requested doc ID and stored edges on graph/trace reads |
| Medium/high: TTL is not idle physical retention | Expired records hidden by reads but old inactive tenant rows/copies never removed by unrelated tenant writes | Explicit all-tenant `purge_expired`, startup/readiness and publication/save maintenance; scheduling/backup/erase gates remain explicit |
| Cross-worker review CAS | Existing `BEGIN IMMEDIATE` already serializes writers; thread-only test insufficient for independent processes | Preserve CAS; spawned independent processes prove one revision-1 winner/one conflict, unchanged source |
| Plaintext/IAM/erasure gap | Plain SQLite, source copies, WAL/journal/backups; credential hash namespace, no reviewer account roles | Unchanged operator gates; no superficial crypto wrapper or new dependency |

Design was reported to parent before further architectural expansion: protected
POSIX custody plus schema/read fail-closed checks and explicit purge, not a vault
rewrite. No substantial architecture expansion followed. Schema creation,
inspection and existing additive migration now share one `BEGIN IMMEDIATE` (not
an `executescript` implicit commit). Failed initialization closes its connection.
Mode is private at upload/DB creation without a threaded-server umask window.

## Preserved red/green history

All outputs are checked in under `docs/security/evidence/`; external mirror is
`/data/axiom-fifth/reviews/security-evidence/`. No failures were deleted.

- `baseline.txt`: **17 failed / 15 passed** before any runtime edits. Six DB/sidecar
  symlink attacks, two root-symlink attacks, namespace escape, suffix corruption,
  two false-readiness cases, wrong-PK schema, bad graph, two absent purge APIs,
  and evidence root mode failed. The 15 passes include legacy store tests and
  independent-process CAS; failures are not claims that every attack stole data.
- `cycle1.txt`: **32 passed**. `lint-cycle1.txt`: five import/unused-import errors.
- `cycle1-additional.txt`: **3 failed / 24 passed**; all three new invalid upload
  byte-count cases exposed remaining corruption/quota-accounting weakness.
- `cycle2.txt`: **1 failed / 39 passed** under fatal ResourceWarning/unraisable
  gates. Test fixture had used SQLite connection context-manager as if it closed
  the connection. Explicit fixture close corrected this, no assertion relaxation
  or third runtime-source cycle. Deferred collection surfaced it at the CAS test.
- `final-strict.txt`: **42 passed**, ResourceWarning/unraisable fatal, with allocation
  tracing enabled. Covers original 13 store tests and 29 new security cases.
- `api-focused.txt`: **10 passed**, fatal resource/unraisable gates: scoped evidence
  API, source evidence and evidence lane. Existing APIs/tests were not edited.
- `process-repeat.txt`: **3 passed**, repeated independent-process CAS, four-process
  cold initialization and eight-thread simultaneous cold migration.
- `lint-final.txt`: all checks passed for the three scoped source files/new tests.
- Existing FastAPI/Starlette test-client deprecation remains visible in combined
  tests. No dependency install/update performed merely to suppress it.

Commands use `/data/axiom-third/venv/bin/python`; tests are local synthetic
fixtures only. Focused core run: `-m pytest -q -W error::ResourceWarning
-W error::pytest.PytestUnraisableExceptionWarning tests/security/test_storage_boundaries.py
kernel/tests/test_evidence_store.py overlay/tests/test_document_store.py`.
API slice: same flags with `overlay/tests/test_scoped_evidence_api.py
 overlay/tests/test_source_evidence.py overlay/tests/test_evidence_lane.py`.

## Cumulative-cycle ledger and scope freeze

Prior history was available from Git, not guessed:

- Evidence store: `3c713a3` initial scoped store, `b86d081` serialized migration,
  `c2791a1` closed-refusal fix = **3 previous + 2 current = 5**. Runtime frozen.
- Upload store: `3c713a3` initial scoped store, `93ed641` collision protection
  = **2 previous + 2 current = 4**. Runtime frozen after two current cycles.
- New custody helper: **2 current** (implementation, then import-lint cleanup).
- New security test module: **4 changes** (initial red oracles; additional attacks;
  import lint; explicit fixture close plus cold-process/maintenance tests).

`manifest.json` retains baseline/branch, exact SHA-256s of final source/tests,
operator doc and raw results. This is no broader cycle budget for existing
admission/gateway modules. Subsequent edits require a new authorized checkpoint,
not silently counting them as validation. No bulk installs/catalog integration,
real secrets, network/provider calls, cryptographic spend, push or deploy.

## Residual operator gates and nonclaims

See `LOCAL_STORAGE_CUSTODY.md` for deployment obligations. Major limits:

- A same-UID/privileged attacker, ACL/mount bypass, hostile filesystem and
  returned-path TOCTOU are not defeated by POSIX path checks. Dedicated protected
  host/UID is mandatory. Linux/POSIX scope only, not a portable desktop guarantee.
- No app encryption/KMS/key management; DB/source/WAL/backup/export are plaintext.
  Full-disk encryption is an independently verified operator control, not shipped
  end-to-end app encryption. No individual reviewer IAM or account migration.
- TTL denial is immediate relative to API clock; scheduled idle maintenance is
  **not shipped**. All-tenant purge must be scheduled/monitored before retention
  promises. SQLite delete/file unlink do not erase WAL/free pages/backups/media.
- No file-content authentication for equal-size host edits. Graph checks are
  structural, not a MAC/signature/anti-rollback journal. Source and evidence
  retention are separate inventories, not a unified erasure transaction.
- Schema health checks scan storage; all-tenant purge can contend with writers.
  No load/SLO/global-storage budget/24h soak/multi-node HA proof in this scope.
  A damaged live upload fails closed; operator repair must stop intake and work
  on a protected consistent copy, never reset evidence to make health green.
- Existing one-local-volume SQLite writer CAS is verified, not distributed CAS.
  Upload unlink/metadata are not atomically crash-erased together. Expired missing
  copies reconcile next purge; unexpected schema/purge failures remain visible.

Parent must integrate the exact verified atomic commit, run final integrated
release gates separately, and retain the fourth-council failed latency verdict.
This security slice does not supersede that NO-GO or prove humans/customers.
