# Continuation draft — NO-GO, not opened or merged

# Axiom-Grid continuation — verified hardening checkpoint

**Decision: NO-GO for general availability or automatic merge.** Actual code and test evidence are delivered; neither production readiness nor traction has been demonstrated.

- Branch: `harden/axiom-grid-v1-launch`; current code: `b8d445b11392af798994db8fb0058a4f867886c8`.
- Control checkpoint: `f7ba9b93d088e3e5186975f167e52c24c0bdfd29`; repeated full load code: `82f920a20cfd90c36bf5a6e6d33106a673c7e4d9`.
- Later changes tighten secret scanning and public copy/CI only. SHA-256 equality of every measured runtime source file against the delivered version is asserted in `analysis/evidence.json`. The final documentation commit is separate.
- No supplied credential was used. No GitHub push, PR creation, merge, live-provider call, deployment, customer outreach, grant submission or recruited-human session occurred.

## Completed in this continuation

1. Sampled the actual server with py-spy. Fuzzy edit-distance windows dominated the initial sampled pipeline; this is measured profiling, not guessed root cause.
2. Added mathematical character/length upper-bound pruning, prepared token normalization and per-source bounded embedding reuse. Differential/property tests preserve historical accepted scores/anchors and original window caps; this does not certify legacy long-field truncation semantics.
3. Replaced six BaseHTTPMiddleware task/stream layers with one pure-ASGI policy boundary. Preserved quota/auth/origin precedence, body caps, context propagation, security headers, request IDs and structured metrics; policy rejections now receive headers/correlation too.
4. Replaced immediate-FD and daemon-log shutdown verdicts with actual bounded TCP-drain checks and an atomic lifecycle marker written only after worker join and durable-state close. The unchanged control also drains FDs: the old snapshot was not proof of a leak.
5. Fixed isolated binary parsing: drain the child result before joining, close/reap process resources, retain chunks/document/pages, and never parse that input again in the parent. A real >64KiB child result and a deliberately isolated parent-handoff oracle pass.
6. Added a tab-memory-only deployment-key connection flow (not a provider key), HTTPS outside loopback, rejection/forget/reload checks and a generation fence for delayed authentication responses. No app localStorage/sessionStorage persistence. This is not OS memory zeroization.
7. Removed Docker production test mode, defaulted untrusted parsing to spawned isolation, switched the container probe to readiness and documented single-worker/single-replica preview provenance. Multi-worker/horizontal scale is not implemented or certified.
8. Removed scanner-wide substring exemptions and added the Melious bearer pattern. A generated, deleted synthetic canary is detected. Current strict findings and historical exposure remain visible instead of being suppressed.
9. Replaced obsolete ghost-writing, trained-model and universal Merkle-receipt marketing with an explicit-export demo using the actual synthetic signed sample, honest scope and GTM hypotheses. Fixed mobile overflow, removed animated verification implications, checked actual advertised code paths.
10. Added an independent native Node HTTP ingress diagnostic and telemetry/browser-auth CI coverage. These producers are not GA badges and do not excuse failing full workload gates.

## Fresh validation

| Population | Result | Scope |
|---|---:|---|
| Focused pre-push | 430 passed | Strict resource/unraisable warnings; one dependency deprecation |
| Broad Python `tests/` | 1184 passed, 4 skipped | Skips are not 100% completion |
| Kernel + packs | 222 passed | Overlaps focused; do not sum populations |
| Chromium overlay/browser | 6 local + 8 authenticated passed | Includes one explicitly fabricated XSS response oracle and one paused real-auth response |
| Desktop JavaScript | 17 passed | Not native desktop execution |
| Receipt CLI / dependencies | Verified sample / pip check clean | Pinned public key + checkpoint; signed observations only |
| Website Chromium QA | 320px and 1280px, no page exceptions or document overflow | Static local preview; not a deployed site |
| Rust / Docker / supported OSes | Not rerun/built in this environment | Previous Rust results are historical; native/toolchain/platform validation remains open |

Broad skips: release-asset training dataset, unavailable LibreOffice, missing PDF form fixture and absent cross-platform workflow.

## Matched full workload

Each full run has 4,500 timed calls plus 120 deliberately abandoned TCP sessions: 1,000 health, 600 malformed/hostile inputs, 300 extraction bursts, 2,400 interactions from 120 scripted identities and 200 recovery probes. The identities are not people or tenant-isolation tests. No verified 1-client reference establishes 100x throughput/scale. All runs are sequential on the same environment; the earlier profiled diagnostic baseline is retained but not used for the chart.

P95 covers all phase responses, including shed requests. Changes in admission affect the population mix: faster percentiles are not proof of higher successful extraction capacity.

| Phase | Control P95 ms | Final 1 P95 ms | Final 2 P95 ms |
|---|---:|---:|---:|
| health | 2448.6 | 338.8 | 320.4 |
| hostile | 2424.0 | 354.4 | 326.6 |
| extraction_burst | 8023.7 | 844.5 | 1332.1 |
| 120_synthetic_personas | 11928.0 | 1399.9 | 1850.0 |
| post_abandon_recovery | 2301.7 | 2048.4 | 604.4 |

Complete P50/P95/P99, throughput and response counts are preserved in `analysis/benchmarks.csv` and raw JSON. Do not average or pool these percentiles.

| Operational evidence | Final 1 | Final 2 |
|---|---:|---:|
| Timed 5xx | 703.00 | 596.00 |
| All server-recorded 5xx, including untimed work | 792.00 | 691.00 |
| Worst timed error, ms | 4639.57 | 3924.47 |
| Shutdown, ms | 214.04 | 214.10 |
| RSS ceiling, MiB | 99.76 | 98.37 |
| FDs after real TCP drain | 11 → 10 | 11 → 10 |

**Passing short-run evidence:** server remains alive, no unhandled ASGI/task/fatal markers, actual TCP quiescence, joined workers and closed state. **Failing:** valid-request expectations, zero-5xx and maximum loaded-error <200ms. No 24-hour soak, universal memory/coroutine/socket guarantee or crash-proof assertion.

The native Node diagnostic covers only health and invalid-input phases. Its final hostile-input maximum is 146.79ms, versus slower full HTTPX measurements. This confirms client/clock sensitivity, not a clean full workload or a reason to discard failed wire latency. Server-Timing excludes transport and pre-dispatch scheduling; it is not end-to-end latency.

## Secret scan: false-green audit closed, credential safety still open

The original configuration globally allowed hexadecimal substrings and words such as test/mock. Its zero-finding result was invalid assurance. Strict scanning produces nine HEAD findings (public checksum, formal identifier and synthetic test vectors), matched to prior review with unchanged-file hashes. These findings are retained; no blanket suppression or automatic green secret-scan claim is made.
Strict all-ref/full-history scan reports 12 findings, including a real historical Melious token in `scripts/session21_melious_torture.py`. Deletion from HEAD does not revoke it. Revoke/reissue all exposed credentials, review account audit logs, forks/copies and history remediation. Never publish a raw secret report.

## Catalog / research reconciliation

Retained pinned Playwright (real Chromium flows), OpenTelemetry (declared runtime SDK/CI installs) and checksum-verified Gitleaks v8.30.1 from the supplied catalog. Profiling, ASGI, multiprocessing and native Node HTTP use local developer tools/standard primitives; no extra application framework, unreviewed connector, installer or autonomous-exploitation dependency was introduced.
Research prioritizes portable signed observations and credible distribution. The prior offline OpenBot/Opik/Helicone exporters remain export-only, not live SDK hooks or upstream-merged integrations. The signed demo is synthetic; external witness, independent implementation, key-rotation protocol and real captured-trace verification remain open. Funding, model-era and regulatory assertions in research are not silently treated as current verified facts.

## Premortem and convergence ledger

- Product trust: broken protected-browser access and misleading launch claims were repaired; genuine activation, user consent, price validation and revenue remain unmeasured.
- Worker starvation: pruning/caching and ASGI cost reductions help, but the four-worker/16-queue default still sheds legitimate work. Do not relabel 503 as 429 or relax gates to manufacture a pass.
- Async/resource safety: native parse handoff, child pipe draining, lifetime ownership and evidence barriers are repaired; long soak, restart and OS tests are still required.
- Gateway risk: the prior secure-destination/redirect/circuit/budget tests remain green locally; the requested four live model IDs, routing quality, costs and quotas require owner-provisioned rotated credentials and bounded live validation.
- Evidence/traction: a signature authenticates a statement, not execution truth or compliance. No recruited human cohort, paid pilot or funding outcome exists in this session.

No failing module exceeded five remediation cycles. Grounding used two substantive rounds, isolation two, auth two, secret scanning one and launch-copy/layout three. Final repeats are validation, not additional remediation. Open architectural/deployment tasks are checkpointed rather than hidden.

## Remaining release gates

1. Resolve admission/fairness and measured wire latency using a realistic documented overload SLO and provisioned infrastructure; preserve these failed runs. Extend the independent client to the full workload before interpreting clock differences.
2. Add tenant-scoped shared provenance/expiry and restart consistency before multi-worker/multi-replica claims. The single-worker candidate is a restriction, not a scalable architecture solution.
3. Run long soak, kill/restart/queue chaos, Docker/collector and signed clean-host installation checks on supported platforms.
4. Revoke/reissue exposed credentials; review strict findings and history. Validate provider model catalog, failover, token/spend boundaries and model-quality cases under a capped live-test budget.
5. Recruit consenting humans and obtain real traces; independently verify receipts; validate pricing and activation. Publish only scope-accurate preview material after review.
6. Push a review branch / open a truthful draft PR only with appropriate credentials. Merge/release only after required remote checks, owner review and rollback readiness. There is no production release PR or merge in this delivery.

## Reproduce

```bash
PYTHON=/path/to/venv/bin/python bash ci/pre-push.sh
PYTHON=/path/to/venv/bin/python npm --prefix tests/browser test
AXIOM_BROWSER_AUTH_TEST=1 PYTHON=/path/to/venv/bin/python npm --prefix tests/browser test
/path/to/venv/bin/python scripts/launch_torture.py --output launch-evidence/tcp.json
PYTHON=/path/to/venv/bin/python node scripts/benchmark_ingress.mjs --output launch-evidence/native.json
```

Install the declared runtime/telemetry dependencies and pinned browser runner first. The strict torture exits 1 on the documented current failures; that is intentional evidence, not an installation success badge.


---

## Earlier handoff (historical; superseded)

# Hardening + signed receipt export checkpoint (NO-GO for GA)

## Tested code

`2d90ff35f5f26e3f6f09d96600386a59abecd040`; remote base `8f381cf`; branch `harden/axiom-grid-v1-launch`.

## Why this remains draft

418 focused tests pass, but the strict TCP bounds fail: 728 overload 503s in 4,500 measured calls, worst error 5994.479 ms, unverified FD quiescence and shutdown marker. Four broad skips, rotated credentials, real human testing, live gateway quality, collector receipt, platform/signed-install/soak/replica gates remain open. No push/PR/merge was performed in this execution.

## Included changes and premortem resolutions

Broken browser parser and XSS surfaces fixed; false desktop post-state success removed; worker cancellation/admission and graph retention bounded; actual document identity/source evidence repaired; bearer redirects refused; offline pinned-key receipt format and export adapters implemented. Five-point product/systems/resource/gateway/trust premortem and catalog choices are in `docs/RESEARCH_EXECUTION_LEDGER.md` and `LAUNCH_VERIFICATION-2026-10-01.md`.

## repos.md integration log

Real Playwright tests/lock; actual checksum-verified Gitleaks developer scan; OpenBot MIT AuditEvent export contract inspected; generic Opik/Helicone export adapters; existing OTel/Prometheus retained. No large framework or unreviewed plugin was vendored. Live upstream hooks and deployment are not claimed.

## Benchmark deltas

| Phase | Before P50/P95/P99 ms | After P50/P95/P99 ms | Before/after req/s | After status counts |
|---|---|---|---|---|
| health | 238.46/2143.75/3471.34 | 477.85/2284.38/3332.19 | 166.61 / 125.12 | {"200": 1000} |
| hostile | 274.31/1142.56/1932.49 | 642.87/2309.44/2701.80 | 231.37 / 107.48 | {"404": 100, "422": 500} |
| extraction_burst | 1877.30/7447.01/8409.35 | 2618.64/8326.46/9451.31 | 24.76 / 19.80 | {"200": 42, "503": 258} |
| 120_synthetic_personas | 4440.70/13352.35/14597.95 | 4212.66/12582.10/13452.73 | 17.83 / 18.88 | {"200": 1130, "404": 400, "422": 400, "503": 470} |
| post_abandon_recovery | 1710.59/2761.08/2777.82 | 1908.79/2344.10/2354.05 | 45.08 / 50.68 | {"200": 200} |

RSS before 69.89–130.15 MiB; after 69.84–120.82 MiB. 503 before/after: 726/728. Per-phase P50/P95/P99 and throughput above are one local serial pair, not replicated production capacity. Retain the failed run and all caveats.

## Validation and release conditions

Focused 418; broad 1,183 + four explained skips; kernel/packs 215 (overlapping); Rust runtime 28, fmt/Clippy clean; desktop JS 17; browser 6 including one isolated response-fuzz oracle. Confirm exact final PR SHA in independent CI. Require owner rotation/audit, stricter repeated SLOs, drain/quiescence, full platform/clean-host/signing, production collector, live model quality, external receipt verification, soak, replica chaos and recruited humans before any GA merge/release.


## Scoped hardening continuation — still NO-GO

Runtime verified at `c2791a110253fbe997ab9a11e79b8bf692076b02`. Implemented credential-scoped durable source/trace/review state, owned uploads, CAS/confidence feedback and BLOCK refusal, bounded fair/disconnect-aware admission, cold-store/lifecycle safety and portable restart/CAS/browser/frozen-model gates. Local strict gate: 450; broad: 1,415 + four skips; Chromium: 20 (two isolated rendering-fuzz oracles). Actual known-ID 100-way CAS yields one winner and 99 conflicts across two workers and process replacement. Full-load SLO remains red: two Python transport failures, two all-server capacity 503s, and loaded errors well beyond 200 ms; native timed zero-5xx is not a GA pass. See SCOPED_HARDENING_CHECKPOINT.md and SCOPED_EVIDENCE.md for exact source/benchmark scope, catalog integration and blockers. No remote mutation, live-provider test, independent council, real-human recruitment or production release was performed.

## Current council checkpoint — overrides earlier launch claims

Tested runtime b28d58a; local branch harden/axiom-grid-v1-launch. Four AI roles, three isolated coding lanes, native evidence bulkhead/disconnect/OTLP/gateway/UX/axe changes integrated. Exact final results and all retained failures: COUNCIL_HARDENING_CHECKPOINT.md. 507 strict; 1,466 broad +four skips; 39 browser checks; 100 real credential-partition script workflows. Final short Python/native 100-client 5xx/transports zero, error maxima 3,656.30/702.48ms >200ms. No GA/merge, real humans, live provider or remote mutation. Catalog/benchmarks/premortem/product gates and convergence counts are in that report and FOUNDER_PILOT_QUALIFICATION.md. New CI producers are authored, not run remotely.


## V5 continuation — still NO-GO

Current verified integrated runtime c612662fac87d624ecc5cd7ec84aaf571ea0cb1c: private POSIX storage custody/schema/quota/purge guards, exact grounding allocation reduction, real local spreadsheet/PDF coverage, four usability regressions, offline no-dispatch provider gate. Strict576; broad1,543/two external skips; browser43. Fresh full100-client HTTP errors4.756s Python/523.52ms native still miss200ms. Clean100-credential primary failed after600calls with two transports; separate800call diagnostic functionally passed but did not fix/reproduce cause. Earlier successful dirty-generated-report run retained, not selected as certification. No push/PR/merge/provider/deploy/realhumans/traction. See V5_HARDENING_CHECKPOINT.md for all phase percentiles/throughput/RAM, rejected preflight rollback, catalogue/license/scanner review, cumulative cycles and owner gates.
