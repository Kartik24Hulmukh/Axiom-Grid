# Axiom-Grid launch-critical follow-up — 15 September 2026

## Decision: NO-GO for production; PR #19 intentionally not merged

[PR #19](https://github.com/Kartik24Hulmukh/Axiom-Grid/pull/19) delivers real hardening
on `harden/axiom-grid-prod`. The user's 100%-verified enterprise release definition
is NOT met. Keep the September 16–17 announcement to a gated, single-tenant
design-partner preview only after the remaining preview gates close.

### Forensic baseline and conflicting attachments

Both attached reports were read. Remote `main` was `645595a`, not the docs-only
`5ac0d26`: corrective PR #18 had already merged and its focused CI passed. The first
attachment's production-ready assertion remains unsupported; the corrective
handoff correctly identified the missing release gates. No open PR existed at
start. The remote hardening branch was `3a63320`. This session branched from main,
fast-forward pushed the required branch without force, and opened draft PR #19.
Other remote branches include native-preview-validation, session-012/013 fixes,
v1-prod variants and hardening waves 6–11; none was silently merged or deleted.

Baseline focused Python suite: **185 passed**. Final: **194 passed**, ResourceWarning
and unraisable warnings treated as errors. Node UI tests: **17 passed**. Ruff E9/F:
passed. `pip check`: no broken installed requirements. These are scoped results,
not an all-repo green declaration. Python here is 3.14.6; visible CPUs 48; actual
cgroup CPU quota is recorded verbatim in the environment artefact.

## Root-cause changes

| Component | Root cause and change | Evidence |
|---|---|---|
| Gateway recovery | Reasoning-only `finish_reason=length` during HALF_OPEN left `probing=True` forever. Reset breaker on valid budget-exhausted response; no spend-amplifying fallback. | Failing reproduction, four budget regressions, focused suite |
| Extraction admission | File reading and classification preceded capacity acquisition, filling the default executor before rejection. Admit first; run I/O/classification/request SQLite on bounded workers; release on actual completion, not cancelled waiter. Bound the initial file read. | Admission red/green; saturation, oversize, missing file and cancellation tests |
| Grounding CPU | Profile: 4,958 edit-distance calls, ~23.6 million Python `min` calls; quadratic DP dominated extraction. Replace DP inner loop with exact Myers integer bit vectors. | Exhaustive small alphabet + 200 Unicode property examples + long-string differential tests |
| Trace continuity | Server spans ignored incoming W3C traceparent. Extract parent context without baggage or header capture. | Real SDK parent-ID and safe-attribute assertions |
| Logging | Bounded JSON sink defaulted to stderr, contrary to stdout requirement. Emit stdout and test both undrained pipes. | Queue-join stdout test; 2,000-request blocked-output chaos |
| Evidence/tests | Old saturation test patched the demo orchestrator and slept, rather than blocking the actual request worker. Synchronize real worker; retain failed benchmark output and distinguish SIGTERM from forced kill. | Final 194-pass suite; raw failed runs preserved |

No production sleep workaround or fake model replacement was added. Differential
reference implementations and controlled fault transports exist only in tests.
The previous long-field truncation/subsampling semantics remain and need a
separate grounding-integrity review; faster equivalence is not correctness
certification for those heuristics. Initial read bounding does not resolve parser
expansion, file mutation/TOCTOU or every document endpoint.

## Measured benchmark deltas (single runs; not causal capacity claims)

### Probe-only: 2,000 requests, 100 clients, one Uvicorn worker

| Metric | Baseline main | Final candidate | Delta |
|---|---:|---:|---:|
| P50 ms | 114.34 | 111.93 | -2.41 |
| P95 ms | 174.77 | 174.85 | +0.08 |
| P99 ms | 181.32 | 181.76 | +0.44 |
| Requests/sec | 816.5 | 825.5 | +9.0 |
| RSS start / peak MiB | 79.4 / 103.2 | 79.3 / 102.9 | similar |
| HTTP/transport errors | 0 / 0 | 0 / 0 | none observed |

Both **FAIL the existing P95 <=120 ms gate**; both pass P99 <=250 ms.
These endpoints are not extraction or upstream-model capacity. Earlier paired
runs, including worse rows, are preserved rather than replaced.

### Real extraction: 1,000 requests, 100 clients, 80% valid memo requests

| Metric | Baseline main | Final candidate |
|---|---:|---:|
| Successful extractions | 4 | 48 |
| Explicit capacity 503 | 760 | 850 |
| Transport failures | 36 | 0 |
| 422 / 404 | 100 / 100 | 100 / 2 |
| Total throughput req/s | 14.79 | 61.71 |
| Successful extraction req/s | 0.06 | 2.96 |
| Successful P50 / P95 / P99 ms | 10821 / 13644 / 13644 | 6841 / 8614 / 8669 |
| All-response P50 / P95 / P99 ms | 5534 / 8436 / 15016 | 939 / 1376 / 7627 |
| Sampled RAM floor / peak MiB | 79.96 / 119.72 | 79.73 / 116.43 |
| Shutdown | forced kill after 10.012 s | SIGTERM completion, 0.164 s |

**This is a severe capacity failure, not launch readiness.** 850/1000 responses
were deliberate 503; healthy backpressure is not successful work. Moving admission
before path resolution intentionally lets saturation supersede some 404s. The
candidate had zero unexpected responses/transport failures and remained healthy,
but successful P99 is ~8.67 seconds. The global pipeline lock and CPU-bound work
remain constraints. Baseline also timed out in earlier runs whose harness lost
JSON on shutdown exception; stderr evidence is retained. Harness corrected to
retain failure measurements. A preliminary optimized run's zero RAM floor was a
post-exit sample; preserved unchanged and superseded by the filtered final run.
Some exploratory runs overlapped other local verification; the final candidate
benchmark ran in isolation. Separate-host, repeated offered-rate tests remain mandatory.

An exact-distance 1,000-iteration microbenchmark improved **2.9373 s -> 0.1563 s
(18.79x)** with equal output. This is a narrow algorithm benchmark, NOT 18.79x
product speed, 100x load, or a traction guarantee.

## Gateway and telemetry verification

Live catalog returned 200. One sequential synthetic call per requested default
route, `max_tokens=512`, no retry, bounded 15 s deadline, produced nonempty text
on all four: GLM-5.3 517.81 ms; GLM-5.3 Flash 1961.99 ms; Kimi K3 2134.52 ms;
Qwen 3.8 27B 1201.75 ms. Raw model IDs and token accounting are in the artefact.
No paid provider hammering was attempted. 429/5xx/timeouts, fallback, budget and
concurrency behavior are exercised by local controlled tests, not claims of a
real provider outage experiment.

Blocked stdout/stderr chaos: 2,000/2,000 health responses, no shutdown timeout,
0.214 s shutdown, 1,715 deliberately dropped logs. Queue shedding prevents serving
deadlock but is not durable audit logging. OTel parent propagation verified with
the real SDK; deployed collector/alerts unverified. Existing `/readyz` caches a
one-time synthetic check: it does not continuously validate DB, volume or gateway.
Overlay extraction itself forces gateway test mode and disables cloud inference;
separate live-router smoke is NOT proof of a model-backed product E2E path.

## Full-suite blockers: explained, not hidden

Default collection: **2,620 collected, 41 errors**. Installing lightweight CPU
requirements and using importlib mode reduced collection errors to **4** with
3,264 collected at that revision: three files import `fitz` (prohibited by the
repository's stated PDF dependency policy), one imports obsolete `packs.wedge`.
Default mode also has duplicate `latency_test`/`memory_leak_test` basenames.

A bounded execution after tree-sitter install reached **231 passed, 6 failed,
1 skipped, 4 collection errors**, then stopped at `--maxfail=10`. Failures include
missing parquet/model2vec dependencies, an attachment fixture hash mismatch and
PowerPoint shape-readback mismatches. This is not a full pass and was not fixed
by weakening expectations. Native Rust/Tauri and full E2E were not run locally
(no cargo/Docker). Latest inspected code-head CI had container and GitGuardian
success, with runtime/overlay still running; no full-green claim is made.

## Five-point premortem and accountable launch gates

1. **Capacity collapse / cancellation** — improved CPU/admission; 85% shedding and
   seconds-long successful latency remain. Architect: redesign worker isolation,
   remove global lock only after proving ownership, bound all document paths,
   repeat offered-rate soak including multi-worker and post-drain memory.
2. **Tenant/document exposure** — auth keys are not ownership. Security lead:
   one tenant per isolated deployment now; opaque tenant-bound document IDs and
   cross-tenant adversarial E2E before multi-tenant production.
3. **Provider spend / recovery** — half-open latch fixed; quotas and breakers
   remain process-local, no distributed spend ceiling. Architect/provider owner:
   shared quota design, approved load budget and real product integration gate.
4. **Deployment/telemetry false confidence** — readiness stale, native/image
   certification incomplete. SRE: exact-image SBOM/disposition, TLS and collector
   proof, alert drill, 60-minute canary, timed rollback and backup restoration.
5. **Evidence and secret compromise** — conflicting historical GO report;
   credentials exposed in prompt. Owner must rotate/revoke both keys. Raw evidence
   now appended in a new directory with SHA256 manifest, not rewritten history.

Convergence checkpoints stayed below five fix loops per component: gateway one,
admission one, telemetry one each, grounding two (second fixed an invalid timing
test); benchmark instrumentation three. Capacity, full-suite and infrastructure
blockers are escalated rather than papered over.

## Delivery and next action

Code commits start at `a53b0f3`; final harness code `3f6f9f4`; all changes isolated
to the required branch. PR #19 remains **draft, unmerged** because merge was
conditional on complete verification. No production deployment or release tag.

- [Deployment and rollback runbook](HARDENING_2026_09_15_RUNBOOK.md)
- [Raw evidence + SHA256 manifest](evidence/session-20260915-followup/)
- [PR #19](https://github.com/Kartik24Hulmukh/Axiom-Grid/pull/19)

Founder plan: five reviewers × ten redacted memos; measure >=30% median review-time
reduction, critical correction/refusal rate, and week-one repeat use. Preview only
after privacy/auth, actual user flow, scoped latency and rollback gates close.
