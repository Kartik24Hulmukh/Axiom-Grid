# Axiom-Grid V8.5 — bounded functional/security fixes, production NO-GO

## Checkpoint and scope

Continuation recovered all99 checksummed V8.4 payloads from the original archive, then fast-forwarded local9a6ce8b to1176c902. Base complete tree20117aa4 equals publisheda144292b; latest observed mainaa386b49 remains unchanged. Source-tested integrated HEAD `11cf55ab57b7bcd24911d472166a15bfc9e17d31`, tree `45d2f6aa1c3a1e0aed1198a6fc1a586273baff9e`. Follow-up documentation only; complete remote tree equality must be verified after snapshot publication. Existing draft PR33 is the only target. No force/main push, merge, deployment, exposed-key use, provider call or 100x/traction/human guarantee.

Three parallel council reviews identified frozen load attribution needs, separate handler false success, and IPC task admission. Eligible handler/IPC candidates were implemented in isolated local clones; the systems reviewer then owned a separately eligible compiler lane. Parent integrated, reviewed and supplied final handler public-body security boundary. IPC author independently reviewed OTHER lanes only; parent reviewed IPC separately. Self-reviews are not independent certification or native-platform tests.

## Closed scoped defects

### IPC admitted task/byte accounting

Actual unchanged parent baseline fed64 tiny complete frames to real NamedPipeProtocol with controlled handler/transport unit fixtures:64 tasks allocated before scheduling,16 handlers started, receive bufferempty. The semaphore bounded handlers, not pending tasks. Candidate same64-frame oracle admits32 and closes/refuses excess before extra task creation; pre-start queued tasks cancel and budget drains. This is component evidence, not real Windows pipes/ACLs or a load/latency claim.

One server factory now shares32 active+queued framed requests and1MiB retained frame bytes across connections. Reservation precedes task allocation; completion owns release, including pre-start cancellation. Disconnect cancels only handlers not yet started; already-started mutations may finish with unknown outcome to a disconnected client.16-handler per-connection semaphore and both old tests remain unchanged; old21-frame test completes all21. Separate constructor defaults are component-local. Fragment/OS/response buffers, connection counts, fairness, deadlines, decoded expansion, native Windows and all-process memory remain OPEN.

### Separate Kami handler truthfulness and security entry

The production caller's separate KamiCommandHandler no longer reports all-success when some formats fail. Explicit Boolean success/nonempty path required; failures counted, genuine partial outputs retained, meaningful error summary propagates through existing structural IPC/Rust error parser. No client changes: Rust/API still loses partial result details.

Removed110-byte fake EPUB fallback. Direct compiler False produces honest generic failures, not successful notifications. Actual PDF success requires requested existing/nonempty PDF plus actual pdfplumber page readback; text/missing/wrong artifacts refused. HTML receives basic document-marker checks; EPUB basic ZIP/mimetype/container markers. These are not custody/race resistance, exhaustive EPUB/HTML conformance, semantic correctness, secure parsing or freshness guarantees. Engine partial/fallback files can remain; swallowed engine diagnostics remain unavailable.

Parent's final allowed handler revision protects PUBLIC handle body before invoking a format handler using actual PromptShield. Real detected injection refused; missing security import refuses before engine import/artifact dispatch; strict schema validation rejects missing/truthy/non-Boolean/inconsistent decisions.14 pure malformed-response fixtures are not real scanner emissions. Metadata, private methods, pre-guard directory creation/logs/arguments and detection completeness are NOT covered. Security abort response differs from normal partial batch failure. Frozen KPX security/HTML code was not wrapped/changed.

### Native compiler sinks and format boundaries

Encoded five native Reveal sinks after parser recognition: title, bullet, paragraph, fenced code and quoted language attribute. Actual before/after files rendered in isolated local Chromium with all networking blocked: five harmless markers executed before, none after; benign case has no marker in either phase. Three fixed script elements remain. Every page retained `Reveal is not defined` due blocked CDN globals; NO offline-navigation/presentation guarantee.

Unknown formats refuse; direct JVM only accepts explicit pdf/revealjs before temporary/subprocess work; known HTML/book/EPUB route to real native builders instead of catch-all PDF mapping. Native missing-JVM PDF refuses instead of writing HTML at a.pdf path. Supported Java output remains unexecuted/unverified; bundled-JAR profile tests hard-fail, not skip or fake JVM positivity. Native tiny HTML/book/EPUB actual structural readback is not legal clearance or universal interoperability.

### Honest release/catalog claims and additive CI

Catalog now accurately describes frozen KPX partial aggregateFalse. Historical acceptance page no longer certifies current production or contradicts its unverified Excel/PDF/legal rows. Signed JSON/public-key assets unchanged; no re-signing/fresh audit claimed. Added enforced textual guards and two new least-privilege, pinned-tool component workflows. Old workflows, strict gate, load producers/thresholds and frozen runtime files remain byte-identical. New IPC job explicitly excludes native Windows; compiler job excludes JVM/offline-slide proof. Old missing training/cross-platform skips remain, not cured by dummy assets/workflows.

## Verification / retained failures

- Unchanged integrated strict gate: **686 passed,44 subtests**, plus3 actual absent-engine/PDF-positive profile checks; lint/compile passed. Retained Starlette warning.
- Expanded same offline scope plus new root regressions: **1,941 passed,2 unchanged skips,44 subtests**, fatal resource/unraisable warnings. Counts overlap; not full legacy/all-platform release certification.
- IPC component12 passed; parent actual64-task baseline failure retained, after32 bound passed. Child baseline was only2 original positives; parent separately froze actual counterexample BEFORE integration. Test-location/gitagainststageddeletedpath error corrected only in placement/command, no source rewrite.
- Handler baseline8fail9pass retained; first genuine minimal profile2fail15pass corrected NEW optional-dependency test assumptions only, runtime unchanged. Final child narrow17pass in each real full/minimal profile. Parent final security baseline3fail17pass (real injection accepted, missing-component ignored, new helper absence distinct); after20pass in both profiles; combined handler/compiler44pass. Pure result/schema fixtures are not actual engine/scanner emissions.
- Legacy provider-free Domain7 subset: actual full profile11pass; genuine missing-ReportLab profile3fail8pass retained, old tests unchanged. This remains a broader clean-profile issue, not erased by conditional new-test passes. Other legacy commands/platforms not run.
- Compiler baseline20fail4pass; candidate1fail23pass due NEW attribute-vs-text oracle error retained, test-only correction final24pass; runtime unchanged. Parent scripting replay separately measured five marker executions→zero. Fixed CDN errors retained.
- Claim baseline2fail9pass retained; qualified candidate25pass1 unchanged platformskip; final guard file13pass44subtests.
- Generated benchmark/release outputs preserved then only explicitly verified generated paths restored/removed. No benchmark improvement committed. Initial recovery/stale loose-ref read/path lookup/gitagainstdeletedpath/bot-identity failures retained and qualified, not product successes.

## Budgets and unclosed release gates

Handler source **5/5 FROZEN** after separately parent-owned final security revision; child2/2 stays closed. IPC4/5, its lane1 implementation used; compiler3/5, lane2/2 closed (one source revision, second test-only). KPX/server/diagnostics/strict gate/PDFengine/install ceilings unchanged/frozen. No reset, renamed runtime route, monkeypatch fix or cap exception inferred from repeated broad delegation.

NO new local full-load run or latency fix. Historical V8.3 HTTPX persona max4098.083ms/Node354.499ms each violate unchanged<200ms; original two pooled header-read losses remain causally unresolved. V8.4 final remote8success1failure/both load steps failed is historical, not V8.5 timing evidence. Final-head remote results must be recorded separately. Systems review proposes one request-correlated observation experiment, NOT authorized: needs explicit bounded exception against server and diagnostic ceilings; no instrumentation/run occurred.

Required owner evidence remains missing: historical/chat/main credential revocation/audit; rotated live-provider endpoint/catalog/quotas and bounded authorization; training release asset; legal/transitive distribution; signed supported-platform clean-host installs; native Windows pipe/ACL/lifecycle; broader IAM/key custody/retention/backup/rollback; deployment/soak; consented humans/customer/budget evidence. Scripted fixtures are not recruited humans or traction. More code tests cannot manufacture those facts. Keep draft/main unchanged until unchanged release gates actually pass.
