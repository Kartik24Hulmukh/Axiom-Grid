# Axiom V8.3 KPX exporter — isolated candidate handoff

## Identity / integration

- Verified base commit: `31277e8b1a4ae0ef529101e67ea63e52340d17c2`.
- Verified base tree: `fb0fff7ef9e540e3cc75e89003f69faa29a88a9b`.
- Worktree: `/data/axiom-v83-export`; branch `harden/axiom-v83-export`.
- Atomic candidate: **`8cfa25bb5d2c30c49d338cd892abe0d8c48d8a76`** (`fix(export): report partial KPX failures and refuse unscanned content`).
- Candidate tree: `63082d09f3541a42d79e91bdf76bbe00985ff0dd`.
- Worktree clean after commit. Parent checkout remains clean at exact original commit/tree above. No parent checkout writes or cherry-pick performed.
- Published review344c109 object remains unavailable locally. Base/current local trees were verified independently; this lane does not claim new remote publication or attest remote equality.

## Exact committed scope

1. `kairo-sidecar/sidecar/exporters/kami_kpx.py`: missing-PromptShield fail-closed ImportError handling; pure per-format response validation; truthful all-requested aggregate status/notification.
2. `tests/test_legacy_epub_dependency_boundary.py`: explicitly stronger False aggregate oracle and partial-notification assertions; all prior direct missing-dependency, exact EPUB failure, no-fake-EPUB and four-real-file assertions retained.
3. `tests/test_kpx_export_contract.py`: new narrow isolated real-export/security-import-denial tests and pure malformed/unsuccessful response-contract checks.

No other tracked file changed. No handler/engine implementation, semantic-search behavior, actual PromptShield module, installer, server/helper, diagnostics, producer, release gate, dependency manifest or license policy changed. Index/round-trip callers inherit the unavailable-scanner refusal from their existing shared scan call; their implementations are untouched.

## Runtime contract

- `export_all` still attempts all five original real formats, preserving its signature and `ok`, `format`, `results`, `notification` response keys.
- All result keys remain. Successful values remain output paths; failures remain `FAILED: <reason>`. Partial real artifacts are not deleted or replaced.
- `ok` now means every requested format succeeded. Any thrown error, non-dictionary result, missing/non-True success status or malformed output-path response makes that format fail. Explicit unsuccessful error text is preserved. Malformed responses yield explanatory failure information rather than accidental success or silent omission.
- Successful notification remains unchanged. Partial and total failure report the actual success count and failed formats, never blanket “All formats exported”. An output path beginning with FAILED is not itself used to calculate success: explicit method outcomes determine status.
- The private static `_export_output_path` validates actual method return dictionaries. Tests exercise it directly with contract values, not by replacing exporters or primary engines. It does not attest arbitrary external file existence; existing real format methods retain their existing write/assert behavior.
- Missing PromptShield import now raises `RuntimeError("PromptShield unavailable; refusing unscanned content")` chained from the ImportError. Direct export fails before writing content or importing EbookLib. Directory creation is still possible at construction/round-trip setup; this is not a zero-filesystem-activity claim.
- Aggregate scan unavailability gives False, five FAILED reasons, 0/5 notification and no output content artifacts. KAMI insertion fails before embedding/index insertion; round-trip export/import refuses unscanned content.
- Real present-scanner safe and detected-injection behavior is unchanged. Other existing scanner exceptions already propagated.

## Caller compatibility and intentional behavior changes

Initial scoped searches found KPXExporter/export_all calls in Domain11 tests and the V8.2 boundary test, not a production importer. Static search cannot establish absence of external or dynamically resolved callers.

Consumers treating aggregate ok as “batch finished” now see False for partial success, by design; successful outputs remain available in results. Direct callers now get an explicit RuntimeError on unavailable security rather than unchecked content acceptance. No new public required response fields introduced.

Separate `KamiCommandHandler._export_all` is NOT a KPX caller and remains unchanged, including its own false-success behavior and legacy fallback concerns. This candidate does not claim end-to-end // kami all UI remediation.

The V8.2 True assertion was an observation of a defective baseline, not a requirement to preserve the defect. Parent explicitly authorized changing it to False; the test name now describes the corrected behavior. Exact EPUB failure and all real-artifact checks remain. Historical V8.2 checkout reports/council/checkpoint files and `/data/axiom-v82-license-review.md` were not rewritten. Baseline still records True and is not silently relabeled as corrected behavior.

Unchanged Domain11 all-five-positive tests expect true success with real EbookLib. Local `/data/axiom-minvenv` has no EbookLib. This lane did NOT run that all-five positive scope, install a dependency, substitute an engine, or add a skip. Four native real-format positives and the actual missing-EbookLib path were validated. Real EPUB positive artifact/structure validation remains parent-owned in an authorized real-library environment.

## Narrow validation and retained failure

Command in each implementation/narrow cycle:

`/data/axiom-minvenv/bin/python -m pytest tests/test_kpx_export_contract.py tests/test_legacy_epub_dependency_boundary.py -q`

- **Cycle 1: 1 failed, 5 passed** (0.42s). New JSON-positive fixture mistakenly looked for title under metadata. Actual unchanged exporter places title at the top level. Failure was KeyError: title, not an engine failure. Retained full failure log: `/data/axiom-v83-export-cycle1.log`.
- Diagnostic rerun of the same failing tiny probe exposed that KeyError; it did not revise source or expand workload scope.
- **Cycle 2: 6 passed** (0.37s), no skips. Corrected only the new test fixture to the real JSON schema and improved subprocess assertion reporting; runtime candidate unchanged. Final log: `/data/axiom-v83-export-cycle2.log`.
- AST syntax parse of all three changed files passed without importing engine modules.
- Working and staged `git diff --check` passed. Exact tracked/untracked changed-path-set assertion matched only the three authorized paths.
- Commit executed with hooks disabled to avoid unapproved hook/workload execution; no hook/strict-gate/fullsuite success is claimed. Parent owns the real integrated gates and publication.

Test coverage includes:

- Five actual direct exporter methods under actual blocked `sidecar.safety.prompt_shield` import; exact chained security-unavailable exception and no content artifacts.
- Actual aggregate under blocked security import: every format fails, False, 0/5 honest notification, empty artifact directory. Blocker hit count asserted; model/EbookLib imports forbidden on this negative path to verify security precedes those engines.
- Actual KAMI add_document: refusal before embedder load and size remains zero. Actual MarkdownRoundTrip export and import refuse unavailable scanner; an import source fixture is preserved.
- Four actual native format files with real present PromptShield: HTML, Markdown, LaTeX, JSON; output content/title and nontrivial file sizes checked.
- Real injection scan blocks all five direct exports before engine use; aggregate False, zero outputs.
- Pure result validator rejects nine explicit unsuccessful/malformed cases, preserves supplied error text and accepts a valid path named with a FAILED prefix without parsing its filename as status.
- Existing actual EbookLib import-denial probe: direct ModuleNotFoundError, exact aggregate EPUB FAILED string, aggregate False and honest 4/5 partial notification; all four native files exist; zero fake EPUB.

All generated export content uses tiny temporary directories removed automatically. No server/model startup, provider/live/network call, dependency install/download or broad workload performed. Import denial is a missing-component test, not a replacement scanner/engine.

## Budget / freeze

- Runtime exporter source history before candidate: `37fe3ef`, `40e3dd1`, `e7d5ecc` = conservative 3/5.
- This one atomic runtime source revision reaches **4/5**, leaving at most one future parent-authorized source-path revision. No runtime source revision occurred in cycle 2.
- Existing V8.2 boundary test path had one history commit (`9dd8541`); this stronger oracle is its second committed source revision.
- New contract test had no history; two editing/narrow cycles (initial fixture and corrected fixture), one final commit. **2/2 authorized implementation/narrow cycles used; no further lane retries or implementation authorized.** No path/lane rename or budget reset.
- Installer 5/5 and diagnostics 5/5 frozen; server4/helper1 reserved and untouched.

## Residual limitations / parent actions

- This closes missing-security-component ImportError handling only. Existing malformed PromptShield response default `result.get('safe', True)` remains outside the expressly scoped candidate; malformed scanner-response hardening is not claimed.
- Response validation does not replace engine-specific completeness/integrity checks, fix optional licensing availability, offer rollback, or add a verified EPUB distribution profile.
- Historical all-five-positive test scope, full integrated suites, lint/strict gates, public/UI callers, publication and release/legal decisions remain parent-owned.
- Candidate is frozen for parent review/cherry-pick. No remote branch/PR/publication/deployment action performed.
