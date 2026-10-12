# Axiom-Grid V8.2 — verified hardening checkpoint, launch NO-GO

## Decision and source identity

Draft PR33 remains an integration review, not merge/GA certification. Main was `aa386b49f19e160491a8e7225cc01b391ae2e522`; review base `922abacbf5a67b7b5608f9a7699eacab37c9c679` has the same complete tree as local `27e9f8e`. Newer main security fixes remain preserved. No exposed credential, live provider call, deployment or main merge was used/performed.

Tested and measured source: `2b793394dc0046f949fdce8620d06c53a25c068c`, tree `1ad42f71d8a5a5cd810a10fa5095705f06b8bbcc`. The following final commit adds this report and council documents only. Publication via authorized GitHub MCP produces a new snapshot commit; it is not the local atomic commit graph. Verify complete remote/local tree equality before claiming publication fidelity. All changed paths use mode100644; no executable-mode downgrade or deletion is needed in this increment.

## Completed changes

Three parallel lanes: installer trust boundaries, declared dependency/license policy, and read-only load-cause review. Parent integrated four isolated commits and strengthened the actual strict gate.

- Root installers no longer execute mutable remote bootstrap scripts, clone arbitrary latest source, pull Ollama models, probe endpoints, modify machine/PATH/home/MCP configuration, or promise unsupported desktop launch. Windows/macOS automated paths fail closed.
- Linux remains explicitly reviewed, unprivileged local developer provisioning: private fresh destination, source/wheel symlink/ownership/write checks, reviewed offline binary wheels with `--no-index --no-deps`, fatal `pip check` plus actual import/corpus smoke commands; or existing Cargo `--offline --locked --bin kairo-phantom`. Unit tests replace command boundaries; real installation was NOT executed or attested.
- Direct default requirements no longer declare banned PyMuPDF or LGPL EbookLib. EbookLib is a separate legal-review-only opt-in, not approval. MPL dependencies are not called permissive. The guard checks19 manifest roots and local requirement/constraint closure, not resolved/transitive artifacts or installed packages.
- Corrected historical license-audit claims: shipped KPX code does import EbookLib; it is LGPL, not AGPL. Clean-default KPX EPUB is **unavailable**. Real missing-import test observes direct `ModuleNotFoundError`, aggregate EPUB failure despite `ok:true`, real other-format files and no fake EPUB. Wider fitz implementations remain open/unsupported, not replaced or declared legally safe.
- Strict pre-push now includes LAN/enterprise fail-closed source guards, real owned PDF/DOCX socket tests, installer/source boundary tests and dependency/missing-EPUB regressions. Assertions were not weakened; three baseline unused imports were removed after retaining their exact lint failures.
- `repos.md` was reviewed/corrected as a catalog, not execution instructions. Existing tools suffice; no gratuitous application framework or parser substitute added. Pinned Gitleaks8.24.3 was downloaded to an isolated workspace and matched its published same-channel archive checksum, not independent signature attestation.

Local atomic commits: `10e18fd`, `b9e5f4a`, `f411352`, `9dd8541`, `2b79339`. Council documents record original isolated commit IDs and scopes.

## Verification — overlapping scopes, not humans

- Final strict gate: **656 passed,44 subtests passed**, mandatory broad/changed-file and new boundary lint, Bash syntax and compile gates passed.
- Expanded offline Python scope: **1,877 passed,2 skipped,44 subtests passed** under fatal ResourceWarning/unraisable warnings. Two skips remain: absent training dataset asset and cross-platform workflow. Starlette deprecation warning retained.
- Installer lane54 tests are mocked command-boundary/source tests, not actual pip/Cargo, platform installation or native desktop execution. Dependency lane12 tests/44 subtests include real tiny exporter calls with only EbookLib import denied. These are contained within parent totals.
- Earlier V8.1 container and8/9 CI results, and earlier43 browser checks, belong to their prior heads. New final-head remote CI must be reported separately; no current-head browser/platform/soak claim is inferred from them.
- Expanded tests generated tracked benchmark/release reports. They were preserved as evidence then only the verified generated paths restored; no synthetic report deltas entered this source increment. Initial clean-tree assertion stopped BEFORE any ingress workload; retained as a precondition failure, not silently erased.

## Fresh bounded ingress reproduction — still FAIL

One unchanged existing Node ingress-only producer on clean tested source,100 clients,1,000 health calls and600 hostile calls. No successful extraction/personas/abandon phase, no logging/worker/timeout/client/threshold overrides, no retries, no provider egress.

- Expected health/hostile statuses matched; hostile worst client error **406.559ms**; worst server policy interval **355.247ms**; recorded admission wait maximum **0ms**.
- The unchanged error target is **<200ms**, so this sample fails. Ingress-only producer exit0 does NOT construct/certify the full requested-load gate. Its child joined workers and closed state on SIGTERM; this is a bounded shutdown observation, not soak/leak proof.
- This reproduces an independent hostile server-policy tail before heavy successful document work. It does not identify which metadata/stat/logging/scheduling component dominates; maxima cannot be subtracted for per-request decomposition.
- Original full trace's two pooled response-header losses and4,831.152ms error maximum remain retained, not replaced by this smaller sample. Keepalive race, GIL/metadata/logging contention remain hypotheses, not root-cause findings.
- Original P50/P95/P99/RAM/throughput evidence remains in V8 reports. Fresh phase quantiles/throughput are in `native-ingress-only-100.json`. No matched performance improvement delta is claimed: this is a different bounded mode/environment, not a causal A/B benchmark.

## Security scan and incident status

Tracked candidate scanner exits1 with13 redacted findings, same rules/paths/lines as the reviewed V8 source contexts; all finding source blobs are unchanged from27e9f8e. Those prior checksum/identifier/test/mock dispositions can be reused only for identical source. No auto-allowlist/suppression. **Not a clean scan, exhaustive secret audit or revocation proof.** Historical/main/chat credential exposure remains an owner incident-response blocker. Final docs/history scan findings and remote GitGuardian status are reported in publication evidence, not presumed here.

## Five-point premortem and residual gates

1. Bootstrap/supply-chain execution: mutable bootstrap removed; reviewed wheels/toolchain/cache authenticity, signed artifacts and hash-pinned resolved release lock remain required.
2. False platform support: Windows/macOS automation blocks; actual clean Linux/macOS/Windows install/launch/read-back evidence and native prerequisites remain missing.
3. License/feature masking: direct default exclusion and negative guards prevent declaration regression; optional/resolved/transitive distribution decisions, legacy fitz and unavailable EPUB remain open. Preinstalled-library broad passes are not clean-default evidence.
4. Tail latency/starvation/transport: independent ingress tail reproduced; original timed losses unresolved. Final server cycle reserved; no denied-path shortcut bypasses admission, no retry or larger timeout manufactures a pass.
5. False release confidence: strengthened gate includes completed boundary work; failed load, skipped assets/platforms, live-provider verification, IAM/key custody/retention/backup/restore, deployment/soak and consented human/customer demand evidence remain required.

## Convergence budget

Installer lane stopped2/2; root install.sh reaches5/5 history revisions and is frozen. Parent packaging change removes unused imports only (third source revision); installer assertions unchanged. License lane stopped2/2. Diagnostic implementation stays5/5 frozen; runtime inherited server4/helper1 unchanged. No new server/helper cycle or scope-renamed diagnostic used. Small denied-path stat order candidate is documented but unimplemented: no evidence it closes transport or latency, so do not consume server5 speculatively.

## Next authorized inputs, not an automatic merge instruction

- Owner must revoke/audit exposed keys and provide rotated provider access securely, authoritative endpoint/model IDs, quotas and a bounded live test budget. No exposed key is reused.
- Agree a bounded socket-lifecycle attribution plan and explicit convergence authorization if additional frozen instrumentation is necessary; do not rename/reset budgets or retry until green.
- Supply training assets, reviewed distribution profile/signing authority, platform/deployment targets, IAM/key custody/retention/rollback evidence and consented human/customer evaluation.
- Keep PR draft, leave main unchanged, and merge only after unchanged release requirements and owner gates actually pass. No protection bypass, force push or GA claim is justified.
