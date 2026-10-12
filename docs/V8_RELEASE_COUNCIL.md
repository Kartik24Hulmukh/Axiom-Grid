# Axiom V8 read-only release/security review

Reviewed: 2026-10-12. Candidate: `376c575af45290f034c3f933b2ee044d5f2b3d14` in `/data/axiom-integration`.

## Decision

**NO-GO for launch, conditional automatic merge, production deployment, sensitive paid intake, or provider enablement.** A narrowly described **code-hardening integration draft PR** is distinct from a release and can be prepared after safe publication and reconciliation with current main. Do not represent it as launch-ready. No tests, load runs, provider calls, outreach, repository writes, GitHub mutations, or exposed-credential use occurred in this review. The only filesystem write is this report. Existing logs were read, not generated or certified by this reviewer.

## 1. Critical: current main contains security work missing from this candidate

- GitHub MCP `list_branches` returned `main=aa386b49f19e160491a8e7225cc01b391ae2e522`, matching local `origin/main` at review time. The candidate V7 branch was not present in the returned remote branch list.
- Merge base: `8f381cf219098d03c0ae2d440681ed59beeaf99a`. Divergence: **7 main-only / 61 candidate-only commits**. This is not a fast-forward of current main.
- Candidate changes relative to merge base (`origin/main...HEAD`): **150 files, +11,743 / -1,687 lines**. Endpoint difference (`origin/main HEAD`): **162 files, +11,940 / -2,612 lines**. The endpoint diff is NOT the PR change set.
- Main-only `0a29acc` adds AES-256-GCM/scrypt sidecar memory export, enterprise authorization quarantine and identity custody work. `605f767` adds cross-platform memory-export custody fixes. These are absent at candidate HEAD. Main also has OpenBot adapter/benchmark additions and documentation absent from the candidate.
- An ordinary ancestry-aware merge would normally retain independent main-only changes. A wholesale snapshot/file replacement from candidate HEAD onto current main would instead overwrite identity/MCP/export security fixes and could omit/delete main-only files. Do not publish the entire endpoint difference as an integration patch.

Evidence: local `git rev-list --left-right --count origin/main...HEAD`, `git diff --stat`, `git log HEAD..origin/main`, and read-only GitHub branch listing. Main security commits: [^https://github.com/Kartik24Hulmukh/Axiom-Grid/commit/0a29accaf735e3d21e841313b26b256d32e6c6f0] [^https://github.com/Kartik24Hulmukh/Axiom-Grid/commit/605f767c7768c30097ba8168336e4149855609c8]

## 2. Security and portability findings at 376c575

### Improved, but not independently executed here

- `phantom-core/src/lan_sync.rs:46,51,56,100`: discovery, pull, and server transport now return a disabled error; socket implementation was removed. Rust runtime regressions and Python source guards exist. This withdraws unsafe LAN transport, not implementation of secure pairing.
- `kernel/sidecar/storage_security.py:73-111`: cross-process initialization lock encloses WAL transition/schema initialization; live file checks use `lstat` rather than opening/closing duplicate descriptors that can disrupt POSIX SQLite locks.
- API key file custody and candidate deployment limits/grace ordering were hardened in preceding commits; local catalog decisions do not attest production custody.

### Still blocking release of this snapshot

1. **Enterprise authorization remains fail-open.** `phantom-core/src/identity.rs:162-169` permits special agent names and unknown principals; OIDC `verify_token` at approximately line 784 accepts an unverified JWT-looking prefix. `phantom-core/src/pro.rs:132-140` bypasses RBAC for the free tier. These are not person-level IAM. Current main quarantines several of these paths, so preserve those main-only fixes when integrating; do not claim they are implemented in this candidate.
2. **Legacy export confidentiality/custody remains unsafe.** `kairo-sidecar/sidecar/memory/memory_export_import.py` still uses SHA-256/repeating XOR and ordinary file writes. Current main's AES-GCM fix is missing here. Separately, `phantom-core/src/kpx_export.rs:50-106` exports full episode content into plaintext JSON via `std::fs::write`, without explicit atomic private-file/no-link controls. Do not imply the sidecar fix alone certifies the separate KPX path.
3. **License-policy contradiction remains executable.** `repos.md` and `THIRD_PARTY_NOTICES.md` ban PyMuPDF/AGPL, but `kairo-sidecar/requirements.txt:9` requires PyMuPDF and sidecar parser implementations import `fitz`. Catalog also includes LGPL EbookLib despite its permissive-only framing. Rust `deny.toml` is not a Python dependency/distribution audit. Remove/replace excluded dependencies or obtain explicit reviewed licensing/policy approval; do not label them permissive by assumption.
4. **Distribution is not release-attested.** Root installers advertise mutable remote scripts/clones, inconsistent repository brands/placeholders, and Windows rustup download execution without visible checksum/signature verification in that flow. No signed frozen artifact, clean-host upgrade, rollback, or trust-chain execution was performed here. These are audit findings, not an executed exploit.
5. **New storage portability/bounded-wait gaps.** Unconditional `import fcntl` makes the new storage module POSIX-only; no Windows implementation appears in this module. `flock(...LOCK_EX)` is blocking without an explicit acquisition deadline. Require a documented Linux-only envelope or supported-platform handling and startup-contention evidence. The new code alone does not prove the earlier broad-suite initialization timeout resolved on every platform/order.
6. **Operational and identity scope remains incomplete.** Candidate single-replica capacity restrictions do not certify horizontal scaling, reviewed IAM, full storage encryption/keystore custody, tenant lifecycle and erasure, TLS/OTLP backends, backup/restore, restart/kill chaos, rollback, 24-hour monitored soak, or independent receipt verification.

## 3. Historical credentials: confirmed without displaying values

Read-only local object inspection examined **3,305 historical blobs <=256 KiB** in selected source/config/document paths for Melious and GitHub token shapes. This is a bounded pattern audit, **not** a full Gitleaks replacement or proof that other secrets do not exist.

- Confirmed one matching Melious bearer occurrence in historical blob `fa09ceb3d0da`, path `scripts/session21_melious_torture.py`.
- Candidate HEAD torture script: no matching token. **Current origin/main torture script: token still matches.** Thus this is not only a historical-exposure issue upstream: main's tracked current script retains it.
- No GitHub token shape matched in the bounded inspected blobs. This does not resolve the separate GitHub token reportedly supplied in chat, nor prove revocation.
- Prior tracked release documentation reports 9 strict HEAD findings and 12 all-ref findings including the real token. These are historical reported counts, not a fresh complete scan at 376c575.
- `.gitleaks.toml` no longer contains blanket substring allowlists and includes a Melious bearer rule. A corrected scanner configuration does not revoke a credential.

Owner must revoke/reissue exposed provider and GitHub credentials, review audit logs/forks/copies, and approve coordinated history/cache remediation if required. Never test validity, authenticate with, print, or publish raw findings. A newly connected trusted GitHub MCP session is a publication mechanism, not evidence that every older credential has been revoked. No secret value or derived credential fingerprint was emitted or persisted by this review.

## 4. Workflow checks: producers exist; required enforcement is not proven

Static candidate workflow job identifiers:

| Workflow | Job identifiers |
|---|---|
| `.github/workflows/axiom.yml` | `focused-runtime`, `legacy-resource-lifecycle`, `focused-overlay`, `overlay-container` |
| `.github/workflows/launch-evidence.yml` | `receipt-browser-gate`, `requested-load-bounds`, `frozen-offline-semantic-e2e`, `local-format-oracles` |

These are job IDs, not observed final GitHub check-context names. Require all applicable check contexts on the reconciled PR/head and integration SHA; do not invent required-status names before observing actual check runs.

- GitHub branch listing reports **`main.protected=false`**. Protection/ruleset configuration and actual required-check enforcement were not exposed by the available inspected tools. Do not claim enforcement exists or infer all ruleset behavior from this single flag. Owner must verify appropriate rules, required review, restrictions against bypass/force-push, and exact SHA-bound required checks.
- Workflows trigger PRs targeting main; launch-evidence is also manually dispatchable but has no push trigger. Merely publishing a feature branch does not automatically run that workflow.
- `requested-load-bounds` intentionally fails until original strict bounds pass. Python and independent full native workload producers preserve failed gates rather than silently accepting shedding or transport failures. Do not mark it optional solely to manufacture “all validation passed.”
- No dedicated Gitleaks/head-plus-history job is wired into these workflow definitions. The configuration/source regression is not a history scan; add actual redacted secret auditing and reviewed dispositions as a gate.
- CI does not run the full broad Python suite, supported-OS matrix, long soak or provider acceptance. Rust CI builds `axiom-runtime` and Tauri overlay, not a dedicated `phantom-core` LAN-sync test/check job. `ci/pre-push.sh` also omits `tests/security/test_lan_sync_disabled.py`. Add active execution of the new security regressions before claiming LAN-disable validation on remote CI.
- Candidate Compose's constrained extraction envelope differs from the focused concurrency posture check's default `EXTRACTION_WORKERS>=4`; default development gates must not be described as deployment-equivalent capacity validation. Container smoke does not validate the mounted deployment-key secret topology or full sustained production load.

## 5. Evidence boundaries

Existing `/data/axiom-broad-v8.log` ends with **1,548 passed / 2 skipped / 1 warning**. Skips concern the owner-supplied training release asset and absent supported cross-platform workflow. Existing V8 browser/auth/UX logs show zero failures in their summaries. This reviewer neither ran those suites nor established their exact SHA/environment manifests; bind them explicitly before use. Do not sum overlapping suites.

Tracked V7 checkpoint retains broad-suite initialization failures, missing browser reruns at that checkpoint, load latency/transport blockers and unverified deployment/platform work. Later sibling evidence may supersede a specific old failure only with its exact measured code/environment and retained counter-evidence. The main-only V9 checkpoint reports improved transport/status results but still retains loaded HTTPX latency failure and explicitly says NO-GO; it is evidence about another code line, not 376c575. [^https://github.com/Kartik24Hulmukh/Axiom-Grid/blob/aa386b49f19e160491a8e7225cc01b391ae2e522/docs/V9_HARDENING_CHECKPOINT.md]

No evidence establishes recruited human testers, actual pilots, commercial traction, or a release. Scripted personas and a synthetic receipt demo must remain labeled synthetic. Commercial hypotheses and independent verification are separate from code validation.

## 6. repos.md applicability

Treat `repos.md` as a capability/license catalog and historical integration ledger, not an instruction to import frameworks or a current bill of materials. Existing FastAPI/Uvicorn/HTTPX/pytest/Hypothesis/psutil, Playwright/axe, OpenTelemetry and Gitleaks patterns are relevant to the observed hardening lanes. Catalog references to live routing or persona counts are historical assertions, not fresh credential-safe results, human usage or traction. Verify versions, transitive dependencies and actual distribution licenses; do not add a broad agent framework to solve queue, custody or latency issues. Catalog-wide “PyMuPDF absent” is not applicable to the wider desktop/legacy sidecar code.

## 7. Publication choices — advisory only; no mutation authorized here

### A. Preserve candidate commit ancestry/graph

A normal secure Git push of the **specific review branch ref** preserves candidate commit IDs, parents, file modes and tree structure. The local repository reports non-shallow and has 600 commits reachable across local refs, but this does not attest completeness of every original/reconstructed remote history. Verify the intended graph/bundle and exact base before publication. Do not `--mirror`, push every ref, force-push main, or reintroduce raw historical secret reports. Existing exposed ancestry requires explicit owner handling even where already present upstream.

Publish only after credential/custody authorization; reconcile against current main with ancestry-aware integration in a separately authorized writable phase; inspect conflict resolutions and preserve main's V9 security work. Then open a draft **code-hardening integration** PR, not a release PR. Fresh remote checks attach to the resulting integration SHA, not automatically to the earlier local evidence.

### B. GitHub MCP push_files

The inspected `push_files` schema is `owner/repo/branch/message/files[{path,content}]`: **one new text-file commit**. It has no parent-graph import, commit-SHA preservation, file-mode, binary-blob, deletion, or explicit base-SHA/CAS field. It cannot preserve the full reconstructed Git graph or exact candidate SHA. Separate tools can delete files, but that changes publication mechanics and is not an atomic full-tree/graph transfer.

For an approved patch-only path, use a dedicated branch from verified current main and apply a carefully reviewed merge-base delta, reconciled with main-only changes. Do not upload every HEAD file or blindly translate endpoint diffs: shared README/auth/export files can overwrite newer work. Executable additions (`ci/launch-evidence.sh`, mode 100755) require explicit mode/tree verification; content-only upload does not attest them. Immutable binary/model/tree requirements need a graph/blob-capable publication route. Scan staged published content without raw secret output. Record that commit identity/history changed and revalidate the new SHA.

### Required before any release/merge recommendation

Reconcile main security commits; obtain owner credential-revocation/audit confirmation; review licensing/installers and remaining security scope; bind clean-clone remote Python/Rust/Node/browser/container/platform checks to the resulting SHA; require original load/transport and explicitly approved SLO evidence; prove release artifacts, custody, backup/restore and rollback. Until then: **draft integration review only; no launch assertion and no automatic merge.**

## Addendum: parent integration and concrete publication feasibility

Parent subsequently integrated current main in its authorized writable phase. Read-only follow-up observed **merged HEAD `45415839f80474f35541efc30fdef77900b51a07`**, tree **`3b398c794ecfaea4dfd5a683a73d98d25fdf109d`**. The initial review above remains about 376c575; its missing-main security findings must not be misrepresented as findings against the reconciled merge. Follow-up comparison found no endpoint differences for main's identity/MCP auth, sidecar memory export and security tests, requirements, V9 checkpoint, OpenBot or benchmark paths. Existing unresolved product scope and release gates remain; broader revalidation belongs to the parent, not this read-only review.

Merged delta against main aa386b49: **150 UTF-8 paths, 109 additions / 41 modifications, no deletions, 1,394,538 content bytes**. This is compatible with text snapshot upload by logical slices, but **not exact mode/tree preservation through push_files**.

### Actual inspected upstream push_files mechanics

Official public implementation inspected on 2026-10-12:

- `repositories.go:1731-1735` sets **Mode=100644 for every submitted path**, including existing paths.
- `:1813` overlays entries onto the branch-tip base tree, preserving untouched main-only paths.
- `:1825-1829` creates a new single-parent commit, not the reconstructed commit/merge graph.
- `:1843-1847` updates the branch without force. The exposed tool has no explicit expected-tip/CAS argument; sequence uploads to a sole-writer branch and verify each returned tip.
- `:1867-1870` includes repository/workflow scope handling. Workflow publication can require authorization the current read-only calls do not establish.

This is inspected public upstream behavior, not an attestation of the deployed connector version. Its schema nevertheless offers no supported mode override. [^https://github.com/github/github-mcp-server/blob/main/pkg/github/repositories.go#L1731-L1736] [^https://github.com/github/github-mcp-server/blob/main/pkg/github/repositories.go#L1812-L1848]

**Confirmed mode hazards:** `ci/pre-push.sh` is currently 100755 and modified; `ci/launch-evidence.sh` is 100755 and newly added. Uploading their text through this implementation makes them 100644. `.github/workflows/launch-evidence.yml:30` invokes `./ci/pre-push.sh`, and `ci/launch-evidence.sh:5` does the same. Grouping files differently does not solve this; exact merged tree equality would fail.

### Option 1 — exact tested tree and reconstructed graph (preferred when required)

1. Freeze the parent's final validated merge SHA and tree; verify latest remote main and ancestry.
2. Owner approves credential revocation/audit and safe publication; use a newly authorized/rotated Git credential or SSH identity through a trusted credential manager, never any supplied exposed value. No secure authenticated Git transport was established here. Do not extract the MCP connector's credential for Git.
3. Owner imports a **secret-reviewed incremental bundle** into an authenticated trusted clone, or securely pushes the intended review branch from the local clone. Do not describe a rewritten “sanitized” history as preserving original commit identities: history rewriting changes IDs. Avoid exporting/pushing all refs or a full-history credential-bearing bundle.
4. Normal push only the new review ref, without force; confirm remote commit SHA and tree exactly equal the frozen candidate, including both executable modes and retained main features.
5. Open a truthful draft integration PR and require remote checks on that exact SHA. Keep merge/release blocked by outstanding validation and security gates.

This route preserves source, tree/modes and graph, but requires an owner-authorized Git transport outside the presently exposed MCP push_files interface. A local reviewed bundle plus instructions is a valid handoff, not completed publication.

### Option 2 — MCP-only draft snapshot, with explicit mode normalization (not exact-tree equivalent)

1. Obtain approval for **snapshot** rather than exact graph/tree publication and for workflow writes. Confirm current main still equals the integrated base; use a dedicated sole-writer draft branch based on it.
2. Parent deliberately adjusts the candidate to support non-executable scripts: use `bash ci/pre-push.sh` in the workflow and in `ci/launch-evidence.sh`, without changing any tests, warning policies, strict load verdicts or gate contents; document scripts as `bash ci/...`. Review any other direct invocation. Mark both scripts 100644 in this publication candidate to match tool behavior. These are parent mutations requiring authorized scope, not performed here.
3. Freeze/revalidate **that adjusted source/tree**. Older results attest the earlier merge, not the adjusted published workflow/mode tree.
4. Serialize the merged main-relative A/M delta into logical, dependency-aware `push_files` batches (for example runtime/storage; UI/browser; tests; docs; CI last). Keep each complete JSON arguments file well below the tool's **1 MiB file-backed payload limit** after escaping. No deletions or binary transfer is required by the observed delta. Intermediate commits are incomplete; do not treat them as validated candidates.
5. Verify branch tip after every upload, exact expected file blobs, unchanged main-only files and final **normalized tree**, not merely line counts. A failure stops publication; do not blindly replay against a changed tip. Workflow-scope denial is a real authorization blocker, not a reason to omit safety gates.
6. Include local commit/tree provenance and a securely reviewed bundle as a separate artifact if authorized. Say clearly: snapshot commit chain preserves content and normalized modes, **not original history/SHA or original tree**. Open only the final draft PR and run all remote checks there.

### Bottom line

**No exposed MCP tool currently demonstrated here can publish the exact 45415839 tree with its executable modes and reconstructed ancestry.** Normal authorized Git transport is the specific exact-preserving path. Grouped push_files is a feasible text-content draft snapshot route only if owner accepts explicit mode normalization, the parent changes bash invocations without weakening gates, and the adjusted snapshot is revalidated. Neither route authorizes launch, automatic merge or use of exposed credentials.

## Addendum: classification of parent's Gitleaks 8.24.3 directory report

Input: `/data/axiom-v8-secret-scan.json`, 15 redacted findings. Parent reports official checksum verification of the scanner binary; this reviewer did not download or execute it. Classified source contexts by reading locally and inspecting structure without printing source literals, `Match`, `Secret`, or key values. **12 findings map to tracked files; 3 map to untracked bytecode caches.** No source/tests/configuration was changed and no finding was suppressed.

| File + line | Classification |
|---|---|
| `docs/axiom/evidence/session8/SHA256SUMS.json:8` | Artifact SHA-256 checksum, not credential |
| `docs/security/evidence/manifest.json:10` | Evidence-file SHA-256 checksum, not credential |
| `kairo-sidecar/sidecar/safety/bmc_gate.py:188` | Identifier/call-argument false positive; no string literal at finding line |
| `kairo-sidecar/tests/test_ci_scan_gates.py:26` | Intentionally embedded deterministic negative secret-scanner fixture |
| `overlay/tests/test_server.py:328` | Explicit test API-key fixture |
| `phantom-core/tests/gauntlet_extended.rs:127` | PII/API-key redaction test input fixture |
| `scripts/ci/sbom_gate.py:22` | Mock cryptographic private-key constant, **not a checksum**; no identifier loads in this module. Must never be treated as a production signing trust anchor |
| `scripts/run_kairoreal_gauntlet.py:474` | Generated hostile-input/security test content, with deterministic fixture marker |
| `tests/test_keychain_storage.py:84` | Explicit keychain round-trip test key |
| `tests/test_keychain_storage.py:92` | Explicit test key for configuration non-disclosure assertion |
| `tests/test_production_ops_oracles.py:314` | Deliberately fake, deterministic GitHub-token scanner-detection fixture |
| `tests/test_production_ops_oracles.py:322` | Deliberately fake comment-ignore scanner fixture |
| `kairo-sidecar/tests/__pycache__/test_ci_scan_gates.cpython-313-pytest-9.1.1.pyc:28` | Untracked bytecode artifact associated with scanner test fixture |
| `tests/__pycache__/test_production_ops_oracles.cpython-313-pytest-9.1.1.pyc:744` | Untracked bytecode artifact associated with GitHub detection fixture |
| `tests/__pycache__/test_production_ops_oracles.cpython-313-pytest-9.1.1.pyc:749` | Untracked bytecode artifact associated with comment-ignore fixture |

**No true live credential identified among these 12 tracked findings from their inspected source contexts.** This is a context-based classification, not online credential validity checking or cryptographic proof of non-use. Retain the report and reviewed dispositions, avoid blanket exemptions, and exclude untracked caches from any publication payload. The separately confirmed Melious credential at historical/upstream main remains real exposure; chat-token revocation/audit also remains unresolved.

Parent later committed explicit bash gate invocation as `b7653ac5af2c613ee4eba24a61bea64bf9041bc9`. This removes the immediate execute-permission failure path, but does not itself prove that the local tree modes equal push_files output. Freeze the final publication candidate and expected mode-normalized tree; fetch/read back final remote tree/blobs and complete remote checks before saying the snapshot matches or is validated. Original reconstructed history/SHA remains a separate provenance artifact unless normal Git transport publishes it.
