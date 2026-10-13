# Independent scoped UX/product redteam review

**Outcome: eight reproduced frontend journey defects repaired; scoped local browser proof passes. Overall launch remains NO-GO.** This is an independent local review lane, not recruited-human research, a multi-person council, adoption evidence, or an assertion that all scenario permutations were tested.

## Frozen scope and provenance

- Worktree: `/data/axiom-fourth/ux`; branch `council/ux-hardening`; baseline `4f3a822`.
- Frozen frontend/tests commit: `55dfabe23f285a0f0bf1075b31cdafe091713ea6`.
- Exactly **one source-changing cycle** for both `overlay/templates/overlay.js` and `overlay/templates/index.html`. Later work added tests, screenshot capture and evidence/docs only. No module exceeded five cycles.
- Only those two static frontend files and dedicated new UX tests/docs changed. No server, admission, gateway, store or kernel source was edited. Existing tests, baseline commits, and failed results are preserved. Parent owns cross-scope fixes and full regression.
- Read starting report, `docs/RESEARCH_EXECUTION_LEDGER.md`, `docs/PR_HANDOFF.md`, relevant repository research/GenericPack behavior, and supplied catalog. Research claims were treated as hypotheses; no claims of public release or human validation were imported from them.
- Shared Python: `/data/axiom-third/venv`; existing Playwright **1.63.0** from `/data/axiom-third/repo/tests/browser/node_modules`; local Chrome for Testing **153.0.8010.12** at `/usr/local/bin/chromium`. This is a pinned Playwright client with an explicitly identified local browser, not an assertion of a downloaded matching Playwright browser revision.
- All application requests used loopback and a synthetic deployment-test key. No posted/exposed key, live provider, remote repository mutation, deployment, SaaS collector or subagent was used. The sole package fetch was the explicitly reviewed public development-only axe-core dependency.

## Findings and fixes

| Finding | Baseline evidence | Concrete frontend remedy | Focused proof |
| --- | --- | --- | --- |
| Forget during processing replaces cleared state with stale error | Delayed real 200 becomes “Connection changed” error on cleared document | Session and document-view ownership guards apply to success, failure and control reset | UX01; UX10 also proves old completion cannot unlock a newer request |
| Forget during owned upload displays stale failed-upload assurance | Delayed real 200 writes “Upload failed” after Forget | Epoch fence and upload-status reset; no stale owned option | UX02; owned upload duplicate/lock assertions UX09 |
| Closed editor remains keyboard-focusable | Hidden `modal-corrected` accepts focus | Actual `hidden` state, cleared drafts, inactive controls excluded from navigation | UX03 |
| Inspection tabs inaccessible to keyboard | Non-focusable divs, no tab roles/selection/navigation | Native buttons, tab/panel semantics and arrow/Home/End navigation | UX04 (ArrowRight explicitly tested; other keys implemented, matrix retains untested cases) |
| Correction editor lacks dialog semantics and focus containment | Missing role/labels, background remains reachable | Named modal dialog, explicit form-label associations, inert background, Tab trap and Escape focus return | UX05; axe-core UX19 |
| CAS conflict displays obsolete Original Value and stale errors on reopen | Reload changes card, not Original input; error persists | Reload stored baseline without replacing user draft; clear error on editor open/close | UX06; existing baseline explicit retry test passed before edit |
| Earlier save closes a different newer editor | Delayed real save closes second field’s editor | Capture editor identity; completion cannot close, disable or inject errors into another editor | UX07; token-owned busy map and session/view guards |
| Mobile correction dialog clips above viewport | 320×480 bounding box y=-51.875, height=583.75 | Viewport-bounded, internally scrollable dialog with corrected mobile width/padding | UX08 geometry plus trial scroll-to-Save reachability |

Additional scoped hardening: document controls lock together during upload/processing so upload/selection cannot silently replace the document midflight; readable HTTP-aware non-JSON error handling and uncertain-outcome timeout/network wording; explicit empty text, empty trace and halted-trace notices; visible focus CSS, reduced-motion CSS, and health-only wording that does not assert authentication. These supporting changes are not all independently reproduced baseline defects.

**Forget is a client ownership fence, not server rollback or file deletion.** A sent upload/save can complete on the server even after the UI discards its result. Requests retain their existing 30-second timeout; no server-cancellation or memory-zeroization claim is made. Source observations remain unchanged by human review; review is not re-grounding or native execution proof.

## Actual verification, not additive totals

| Run | Persisted result | Interpretation |
| --- | --- | --- |
| Original local browser suite before edits | 9 passed | Preserved control suite; includes one fabricated XSS-rendering oracle |
| Frozen new eight regressions before edits | 0 passed / 8 failed | Actual Chromium reproductions, including paused real backend responses |
| Same eight after source cycle 1 | 8 passed | Before/after defect proof |
| Extended first attempt | 17 passed / 1 failed, plus asynchronous test-route error | Retained failed assumption and test-harness issue; not a clean pass |
| Corrected focused UX suite | 19 passed / 0 failed / 0 skipped | Persisted full focused run; no asynchronous activity warning |
| Post-freeze screenshot-helper/Save-reachability enhancement | 1 passed (UX08) | Production source unchanged; changed test enhancement separately verified |
| Focused script/public-asset safety | 4 passed | One existing Starlette deprecation warning; not full server regression |
| Reconstructed baseline assets: UX08 + axe-core UX19 | 2 failed | Baseline geometry and critical label/select-name defects preserved |
| Candidate UX08 + axe-core UX19 | 2 passed | Three actual UI audit states; not WCAG certification |

These runs overlap and must not be summed as unique cases or people. The focused 19 cases include real backend journeys, browser-only focus assertions, and three **explicitly isolated oracles**: UX14 fabricated empty/halted rendering, UX17 fabricated HTML proxy response, UX18 stalled transport/accelerated timeout clock. UX15 uses an actual backend unknown-ID source response, not actual expiration. UX10 reconnects with the same test key and is not tenant-isolation proof.

### Failed no-suggestion assumption, resolved by source semantics

The first UX13 assertion wrongly assumed a document without memo headings could not yield any suggestion. Its 51-character note returned one grounded summary. `packs/generic/pack.py` explicitly extracts a first substantial paragraph (>50 chars), so this was an unsupported test assumption, **not a demonstrated backend refusal defect**. The original failed log remains. The corrected real-backend test uses the distinct 11-character low-information input `brief note.` and obtains zero suggestions. UX14 separately exercises empty/halted rendering as a clearly fabricated response oracle. No actual BLOCK/model-quality claim is inferred from either case.

The asynchronous “Route is already handled” failure came from replacing a transport interception while its earlier request was still held. The dedicated test now uses one handler with two explicit transport gates and waits for fulfillment. No production behavior or assertion was relaxed to suppress that test harness defect.

### Screenshot timing and interpretation

The original eight regression assertions, including mobile geometry, were frozen and run **before source edits**. Screenshots were **not** captured then. Baseline screenshots were generated **after remediation** by reconstructing only static HTML/JS from `4f3a822` while using the unchanged real backend. They are labelled `ux-baseline-assets`, not falsely described as before-edit captures. Candidate screenshots are `ux-current-assets`. Screenshot capture disables finite CSS transitions to avoid mistaking an in-flight fade for the final dialog. This last test-only capture change was verified by repeating UX08: reconstructed baseline still fails geometry; candidate passes. The modal evidence uses viewport screenshots at 320×480, including a candidate view after scrolling the Save button into reach; full-page screenshots of other states are separate. Geometry assertions, not the full-page image, establish viewport clipping.

## axe-core catalog integration and license decision

The catalog has 247 GitHub URL entries. Relevant accepted choices:

1. **microsoft/playwright:** retain existing 1.63.0 client; package license Apache-2.0 was inspected. No alternate browser-agent framework or second test runner was installed.
2. **dequelabs/axe-core:** integrate **4.11.0**, development-only, under `tests/browser/ux-a11y/`. Npm metadata, installed LICENSE and lockfile agree on **MPL-2.0**. Exact tarball integrity is committed; lifecycle scripts were disabled. Only tests inject its unmodified source into a local page. It is not a production asset, runtime dependency or collector.
3. **Other catalog entries:** browser-use/Skyvern/Stagehand, testing-library/Storybook/MSW, Lighthouse/cloud visual QA, agent frameworks and security scanners were not installed in this lane. Existing native DOM and pinned Playwright suffice; cross-scope profiling/security/load tools belong to the parent. Their licenses were not approved by implication or blind bulk review.

MPL decision: retain upstream package license/notices and satisfy source availability for covered files if distributing axe-core; no upstream source modifications were made. A later modified or production-bundled integration needs a fresh license/distribution review. This does not claim the application as a whole must become MPL or offer legal certification.

### Audit results and honest residual gaps

UX19 runs default axe-core rules against **actual initial, processed and open-correction states** at 320×900 and asserts zero serious/critical **violations** (not zero incomplete checks).

- Reconstructed baseline: critical `label` (three controls) and `select-name` (one selector) in each audited state. Moderate `region` remains, and initial/processed also have `page-has-heading-one`.
- Candidate: **zero serious/critical violations** in each state. Initial and processed still have moderate `page-has-heading-one` and `region` (two nodes); correction has no violations.
- Candidate serious `color-contrast` **incomplete** checks: initial 17 nodes, processed 38, correction 3. These require manual contrast review on translucent UI surfaces. They are not treated as passes, nor as confirmed contrast violations.
- No screen-reader perception, real touch-device keyboard, 200% zoom, low-vision evaluation or recruited-human task-completion study was performed. Automated semantics/geometry tests cannot replace those.

## 120 distinct scenario designs and bounded coverage

`docs/ux/SCENARIO_MATRIX.md` contains **120** distinct journeys spanning connection, processing, upload, abandonment, review, conflict, sources, empty/refused, keyboard, accessibility, mobile and recovery/trust. It explicitly labels **54 rows with cited observations or constrained partial/oracle/pre-edit references**, and **66 planned/unverified** rows. **54 is not a whole-journey pass count**; some refer only to a tested subcase. **19 is the focused test count**, not 120 executions. No Cartesian-permutation claim, synthetic-person-as-human claim or “all UX tested” badge is warranted.

Remaining high-value follow-ups: delayed failed processing/upload after Forget; multi-credential actual UI journeys; a second CAS conflict and failed reload; review quota errors; all source expiry boundaries; actual empty binary files; end-to-end actual BLOCK refusal (parent/server scope); assistive tech, contrast, small-device keyboard and zoom; uncertain save reconciliation after navigation/reload. Admission/backend stress, full regression, credential rotation, load SLO and actual human/adoption gates remain with parent/owners.

## Reproduce and evidence

Install the new development-only audit:

```bash
npm ci --prefix tests/browser/ux-a11y --ignore-scripts --no-audit --no-fund
```

Focused suite (installed paths in this environment):

```bash
NODE_PATH=/data/axiom-third/repo/tests/browser/node_modules \
PYTHON=/data/axiom-third/venv/bin/python \
AXIOM_BROWSER_EXECUTABLE_PATH=/usr/local/bin/chromium \
node --test tests/browser/ux-hardening.e2e.cjs
```

Add `AXIOM_UX_EVIDENCE_DIR=/path/to/local/evidence` to save axe JSON and screenshots. Set `AXIOM_UX_BASELINE_ASSETS=1` and `--test-name-pattern='UX08|UX19'` for the intentionally failing reconstructed-baseline proof; **do not** use that mode to claim baseline/current extraction differences. No production source checkout or editing is needed.

Preserved logs and compact audit summary are committed in `docs/ux/evidence/`. Larger raw axe reports/screenshots remain in `/data/axiom-fourth/evidence/{ux-baseline-assets,ux-current-assets}` with SHA-256 manifest in `docs/ux/evidence/artifact-manifest.json`. The two early runner setup failures (wrong `/usr/bin/chromium`, missing Playwright-managed browser) remain separately in the shared evidence folder; neither counted as application failures or passing test runs. Parent full regression is still required on the integrated final SHA.
