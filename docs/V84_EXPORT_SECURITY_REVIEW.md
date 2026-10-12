# V8.4 final exporter candidate — independent read-only review

## Verdict

**No blocking runtime/source issue identified in the scoped candidate diff.** The HTML context escaping and strict real-scanner result contract match the approved final-source intent without replacing libraries/engines or weakening previous test assertions.

**Commit-scope housekeeping is outstanding at this review snapshot:** parent strict execution generated three tracked benchmark report deltas in addition to the two intended candidate paths. Parent should preserve that evidence and explicitly restore/exclude those verified generated deltas before a two-file candidate commit. This reviewer does not restore or edit them.

No source fixes, tests, imports of product code, workloads, browser reruns, dependency changes or checkout writes performed by this review. Only this external report is written. The old 2/2 implementation lane remains closed; the parent owns the final 4→5 revision and integration/publication.

## Reviewed identity

- HEAD remains `9a6ce8ba706d853c6fb52d92c19146296cb05993`; reviewed uncommitted diff against this exact baseline.
- Intended paths: `kairo-sidecar/sidecar/exporters/kami_kpx.py` and `tests/test_kpx_export_contract.py`.
- Reviewed SHA-256 of source bytes: `539c979581fb4524ac9f084b8e1f351cbfe6cfccd9a51dd12ae023de0bd52d15`.
- Reviewed SHA-256 of contract-test bytes: `c357f6244769f992c67dcffeff232a8d7904526ba0503d74f1f2bc038104eae6`.
- First status inspection showed only those two paths. After parent strict completion, status also showed `bench/REPORT.json`, `bench/REPORT.md`, `bench/history/bench_52ceb0265dfff3ce.json`. Their read-only diffs change only Python-version recording from 3.14.6 to 3.13.14, not benchmark measurements or thresholds. They are not silently treated as exporter source changes.

## Source review

### Strict scanner decision

`_validated_scan_result` requires a dictionary, strict built-in bool safe value, list matched_patterns, string elements and no contradictory True/nonempty-pattern response. It raises a fixed descriptive RuntimeError for malformed schema; no untrusted response content is copied into an error. Short-circuit guards prevent missing keys/non-dictionaries from reaching the later indexing/iteration checks.

Real `PromptShield.scan_detailed` supplies precisely bool + list[str]. Benign/empty responses remain `(True, [])`; detected injection remains False with copied pattern strings. False with an empty pattern list still blocks, rather than inventing safety. Copying the list avoids mutable aliasing in the returned tuple. This is compatible with existing real-scanner callers; previously tolerated malformed or incomplete alternative scanner responses deliberately become unavailable/invalid failures.

`_scan_for_injections` now returns the validator applied to the actual scanner result, with no extra truthiness/default-success path. Existing ImportError refusal and unrelated propagated scanner errors are preserved. Existing direct-method scan-before-write boundaries and aggregate exception/status logic remain intact.

The validator is a schema boundary, not proof that an in-process compromised scanner is truthful. isinstance permits dictionary/list subclasses; arbitrary malicious Python objects or concurrent in-process mutation are not newly guaranteed safe by this contract. These are not externally serialized normal-scanner responses and are not scoped blockers.

### HTML title and seven converter sinks

- The metadata title in export_html is string-coerced then stdlib-escaped before the title text-context interpolation. It creates no metadata h1 and does not mutate metadata. Missing/default and ordinary string-coercible values retain their display semantics.
- All seven previously raw user-text sites are escaped: fenced code; h1/h2/h3; li; blockquote; paragraph source before inline transformations.
- Raw-prefix recognition and parser state remain unchanged. In particular `> ` is recognized before escaping, retaining quote structure.
- Fixed generated HTML delimiters remain trusted markup. html.escape's default quote=True is appropriate. Encoded user '<' cannot introduce a tag; ampersands/entity-looking input is not promoted to executable markup.
- Bold/em/code regex substitutions still insert only constant wrapper tags into already escaped paragraph content. Stars/backticks survive escaping, preserving existing supported Markdown structure rather than escaping completed output or replacing the converter.
- There is no URL/image/link rendering layer added, no new dependency or engine bypass. Standard-library function import is not shadowed by the local HTML output string.
- Non-targeted format result shapes, partial-output semantics, notifications and prior failure reporting are unchanged.

### EPUB explicitly included expression

The body-derived chapter h1 wrapper now escapes `ch_title`, in addition to shared helper body escaping. This closes the separately identified direct raw heading concatenation at that source sink. EbookLib's own metadata/navigation/serialization behavior is untouched. **This is source/structural evidence only**: no real EPUB-positive artifact/packaging/browser guarantee can be inferred without the actual allowed library/environment. The existing missing-EbookLib contract remains unmodified.

## Test review and evidence boundaries

All three original contract tests and their existing probes remain unchanged; the diff adds two new tests. `tests/test_legacy_epub_dependency_boundary.py` and the frozen pre-push gate have no candidate diff. Missing-EPUB False oracle, exact failure, four real outputs and no fake EPUB assertions remain intact.

New real HTML test:

- Uses actual KPX export_html and real present PromptShield; no engine/scanner substitute/import denial.
- Ten hostile cases cover metadata title breakout, paragraph, all three heading levels, list, quote, fenced-code breakout, inline code and raw img/onerror markup.
- Parser checks reject injected script/img elements, require one title and literal text retention; a benign fixture checks all existing heading/list/quote/pre/code/strong/em structures and text content.
- HTMLParser checks are artifact-structure evidence, not actual script-execution evidence.

New strict-decision test:

- Pure validator fixtures reject 17 malformed/inconsistent responses; valid True/False and non-aliased copied pattern list are checked.
- AST wiring checks verify the real scan adapter returns a validator call; actual real scanner calls cover empty, benign and detected-injection content without monkeypatching.
- No dynamically injected malformed scanner response is executed through export_all in this test. The combination of direct validator tests, visible adapter wiring and existing error/aggregate contracts supports the contract; do not describe pure fixtures as real scanner emissions or end-to-end malformed-scanner runtime evidence.
- AST func.id assertion is implementation-specific/brittle to future refactoring, not a current production/security defect. Avoid cosmetic source churn to accommodate speculative future refactors.

### Existing parent evidence inspected, not rerun

Evidence directory: `/data/axiom-v84-delivery/evidence`.

- `regression-before.log`: **2 failed, 3 passed**. One failure is actual HTML exposure. The scanner test fails because the new validator does not exist at baseline; it is **not a reproduction of a malformed decision being accepted by a real scanner**.
- `narrow-after.log`: **8 passed**, 0.60s, including unchanged missing-EbookLib boundary tests.
- Chromium before/after JSON: eight cases each (seven hostile + benign). Before: all seven hostile cases execute the harmless local script marker and create one script element each. After: no marker execution and zero script elements in every case. Benign browser title/headings/quote/code/bold observations match before/after.
- The recorded harness consumes actual exported HTML via local Chromium page.setContent and aborts all context network routes. It creates no remote/provider workload. This is scripting-enabled DOM rendering of the real artifact, not a claim about every actual file-opening/origin environment.
- Export manifests record real PromptShield safe=True for these inputs, and the generator source asserts actual scan_detailed before actual export. No replacement engines/scanners visible in the inspected harness.
- `browser-precondition-failed.txt`: initial Playwright location failure is retained, followed by correction to existing local pinned browser resources, not installation or scanner/engine substitution.
- At review time `strict-after.log` had completed: ruff stages passed; **670 passed, 44 subtests passed, one retained Starlette deprecation warning**, followed by **3 real PDF profile tests passed** and `PRE-PUSH GATE: PASS`. This reviewer read those parent-generated results; did not execute the strict gate. Gate/profile numbers are separate overlapping scopes, not additive full-product certification.

## Formatting and residuals

The new test's embedded probe strings use dense compact style, and the EPUB concatenation is long. These are readability/possible stricter-style concerns, not demonstrated syntax failures or blockers under the inspected current E9,F gate. Parent's recorded applicable lint passed. Do not spend another forbidden source revision on cosmetic reformatting.

The converter remains a limited Markdown formatter, not a full Markdown parser. Escaping intentionally removes raw-HTML rendering support; this behavior change should be documented honestly. Existing simplistic nested inline semantics and parser tag-balancing behavior remain unchanged; no complete CommonMark guarantee is made.

This closes the specific raw-text HTML emission/safety-schema contracts reviewed. It does not establish comprehensive EPUB/XML validation, legal dependency availability, all handler/UI coverage, all metadata/template safety in other engines, model-security effectiveness, platform deployment readiness or a universal production security guarantee.

## Parent handoff / budget

- Accept this final candidate for parent integration review on its stated scope; no scoped blocking source defect found.
- Preserve/exclude the three generated benchmark-report deltas deliberately before claiming an exact two-file candidate. No reviewer action taken on those files.
- Commit/publish with explicit identity and current evidence; do not label the absent-validator baseline failure as actual malformed-scanner execution.
- Parent source revision4→5 reaches the exporter ceiling and freezes it. No more source correction, new lane reset, wrapper rename or reopening the completed child 2/2 implementation lane authorized by this review.
- Server/diagnostic/pre-push/PDF/installer ceilings remain frozen; no edits or proposed bypasses to them.
