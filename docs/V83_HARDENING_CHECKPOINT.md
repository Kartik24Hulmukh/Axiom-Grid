# Axiom-Grid V8.3 — verified defect fixes, launch NO-GO

## Decision and scope

Main remains `aa386b49f19e160491a8e7225cc01b391ae2e522`. Draft PR33/review branch is the only publication target. No exposed key, live provider, actual deployment, protected-main bypass, merge or startup traction/human claim. All failed and absent launch gates remain required.

Previous verified publication344c109/local31277e8 shared complete treefb0fff7e. Three parallel reviews isolated export contract, legacy PDF exhaustion and deployment capacity. Parent integrated exporter/PDF candidates and one proven capacity correction. Child reports refer to their31277e8 base and scope, not simultaneous parent changes or independent remote equality. Do not misread their historical parent-unchanged statements as final-head attestation.

Tested/measured source: `d0e1b44b28c6a7cf2b09cd05b3628e07c5140f16`. Final follow-up adds these report/council documents only. Complete remote/local tree equality must be verified after authorized snapshot publication, which preserves content/modes/tree, not reconstructed local ancestry.

## Closed defects

### Explicit resource limits actually take effect

Docker/Compose requested two extraction workers/four queue slots, but runtime `max(4,...)` yielded four workers, four metadata workers and eight extraction permits. Pre-edit actual-import oracle and new tests froze the counterexample:5 failures/4 passes.

Single final server-cycle correction respects explicit1..32 workers; unset/empty retains historical automatic4..32 sizing. Zero/negative/above32/noninteger explicit values fail startup; no documented zero-as-auto use was found. Actual two-worker configuration now creates2 CPU workers,2 metadata workers and6 permits; pipeline/evidence remain2.29 narrow configuration/deployment/admission/cancellation checks passed; lint passed. This fixes operator/config correctness, not wire latency. Lower configured capacity can change waiting, throughput and shedding.

Admission before metadata, completion-owned release, CPU revalidation, tenant/upload custody, parser isolation, original status/threshold oracles and both original producers are unchanged. No speculative stat shortcut, retry or keepalive adjustment.

### KPX partial export and security-component failure

Requested-format failure now returns aggregate `ok:false`, preserves genuine successful outputs and all failure reasons, and reports incomplete counts instead of “all formats exported”. Pure return-contract validation rejects explicit unsuccessful/malformed method responses without mocking primary engines.

Missing PromptShield now raises a security-unavailable RuntimeError before unscanned export/index insertion/round-trip content return. Actual import-denial negative tests exercise real owned components. Real benign four-format files and injection-denial controls pass. No model/provider call or substitute scanner/parser.

The V8.2 test that observed erroneous `ok:true` is deliberately strengthened to assertFalse; exact missing-EbookLib failure/no-fake-EPUB/four-real-output assertions remain. Historical baseline evidence is retained, not rewritten. Real EPUB success remains unverified/unavailable in the default profile. The separate KamiCommandHandler aggregate and malformed scanner-result default remain outside this candidate; no UI-wide/full security claim.

### Exhausted legacy PDF extraction cannot return empty success

The genuine optional-engine-absent profile previously returned empty low-confidence fallback as completed extraction for born-digital and scanned fixtures. Baseline3 tests:2 failures/1 real pdfplumber positive.

One final engine revision rejects empty/whitespace final fallback with descriptive RuntimeError. Same unchanged real-profile harness:3 passed, no skips, no import interception/availability flags/mocked parser. Supported real pdfplumber route still extracted768 characters/104 measured word boxes. The harness hard-fails if fitz/OpenDataLoader/olmOCR/Surya are discoverable/installed; missing required pdfplumber also fails, never skips. Whitespace guard was structurally verified; no whitespace engine output was fabricated.

Named-pipe propagation is source inspection only: existing extract/table/summarize exception boundary returnsfalse. Actual named-pipe E2E, capability advertising, PDFMaster catch/default behavior, missing-file metadata, incorrect tier labels, figure absence and installed-fitz policy remain open. Do not claim all legacy PDF routes fixed or legal approval.

## Verification

- Strict pre-push: **668 pytest passes,44 subtests**, plus **3 real absent-engine/PDF-positive unittest checks**, lint/compile gates passed. New runtime-capacity and export contracts plus profile harness are enforced, not merely run ad hoc.
- Expanded offline Python scope: **1,889 passed,2 unchanged skips,44 subtests** under fatal ResourceWarning/unraisable warnings. Missing training asset and cross-platform workflow remain skipped; Starlette warning retained. These overlap strict/lane totals.
- Exporter cycle1 fixture schema error retained (1failed/5passed), corrected test-only in cycle2(6passed), runtime unchanged. PDF baseline2fail/1pass retained; one candidate cycle3pass. No dependencies installed/downloaded or old PDF tests/skips weakened.
- Generated benchmark/release outputs preserved then verified generated paths restored. No benchmark report churn was committed as improvement.
- Full-workload metadata preflight failed before running either producer because recorder used systemPython lackingHTTPX metadata; corrected to actual already installed venv, retained failure. One serial execution of each unchanged full producer followed, not retry-until-green.

## Current full-workload acceptance — FAIL, not a transport cure

Both one-shot full producers on clean tested source used100 clients,120 scripted identities and4,500 timed requests each; no runtime, threshold, logging, timeout, client, retry or provider override. Not container-equivalent deployment, not recruited humans.

- Python/HTTPX: expected statuses matched; no timed transport losses observed in THIS sample; worst hostile error860.675ms and worst persona error **4,098.083ms**, versus unchanged<200ms. All other listed strict gates passed, including no observed5xx/unhandled markers, FD idle return and bounded shutdown. RSS floor74,485,760/ceiling101,294,080bytes; FD17..117; threads max15. Sampled resources are not soak/leak certification.
- Independent Node: expected statuses matched; no timed transport losses in THIS sample; hostile max350.946ms and persona max **354.499ms**; unchanged<200ms gatefailed. Other producer diagnostic gates passed, workers/state joined/closed.
- Both producer exits1 and `passed_requested_bounds:false` are retained. Original earlier two pooled header-read failures remain causally unresolved; their absence in this sample is not a root-cause fix. No matched performance improvement delta is claimed.
- Exact error P50/P95/P99/max and throughput byphase are preserved in `full-workload-summary.json` and original producerJSON. Current persona error quantiles: HTTPX18.092/1357.422/2883.316/4098.083ms; Node8.917/142.418/314.300/354.499ms. Different clients/phases must not be presented as a causal speedup comparison.

Existing V8.2 log inspection additionally identifies the355.25ms response-start maximum as a404 on `/api/extract-document`, before successful heavy extraction.2109 heterogeneous logrecords include1602 unique completion IDs/600 hostile completions; repeated validation warnings were retained. Status-code rate/date decline hints were refuted as inapplicable; log timing is rounded and occurs before wire delivery. It narrows the failing route, not metadata/stat/GIL/logging/transport cause. No new instrumentation or load was used for that analysis.

## Budgets and unresolved gates

Server **5/5 frozen** after the justified capacity correction; helper1 unchanged. PDFengine conservative5/5 frozen. Diagnostic5/5 and install.sh5/5 unchanged/frozen. Export source4/5, lane2/2 frozen; one future source revision requires separately bounded ownership, not lane reset. Strict gate conservative fifth history revision now includes completed contracts; no further silent gate edit. Baseline narrow failures/test-only corrections remain in the handoff.

Load latency and historical transport attribution remain failed/unresolved. Live gateway endpoint/model/quotas with rotated access, incident-response audit, training assets, legal distribution/EPUB profile, signed clean-host platform artifacts, broader IAM/key custody/retention/backup/rollback, deployment/soak and consented human/customer evidence remain required. No background retries, protection bypass or auto-merge.

The next transport/server implementation cannot silently exceed exhausted limits. Owner must explicitly choose a bounded exception/new attribution plan, or keep the limits and supply external launch inputs. No fabricated GO follows from local green tests.
