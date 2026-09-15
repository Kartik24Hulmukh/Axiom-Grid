# Session 11 — launch hardening checkpoint

**15 September 2026 · Release decision: NO-GO · PR #20 remains draft.**

Session 9's launch-ready assertion is superseded by independently reproduced full-suite failures. Session 10's checkpoint was the correct starting point. No deployment or release merge is certified.

## Delivered root-cause fixes

- **Unbounded compression telemetry:** `_global_stats` retained every request's mutable statistics, made reads O(lifetime traffic), and returned inconsistent totals during concurrent writes. Three new tests failed on the baseline (1,000 retained objects, aliasing, torn counts). Replaced the history with locked lifetime counters and a copied last-run snapshot. No per-request history, no change to endpoint totals, no arbitrary sleeps. A synchronized 100-worker/10,000-update test passes.
- **Lost worker tracing:** `ThreadPoolExecutor.submit` did not carry request ContextVars/OpenTelemetry context. A real SDK regression failed before explicit `copy_context().run` propagation and now passes, including no leakage to the next request. Existing admission, cancellation and shutdown ownership remain intact.
- **Rejected optimization:** request-local text pipelines could overlap with separate stores and provenance, but measured useful throughput fell from 3.10 to 2.68 req/s and P99 worsened from 6,760 to 8,305 ms under 100 clients. Reverted lock removal. CPU-bound work does not become useful capacity merely by adding threads. Native parser serialization remains protected by a regression.
- Added benchmark output arguments so historical evidence is not overwritten. Extended the focused lint gate to cover the compressor.

All own changes were made on `harden/axiom-grid-prod`. A concurrent remote commit `202f75f` arrived during the run; the non-fast-forward push was rejected, its diff was reviewed, then own commits were rebased on it and pushed without force. Its sealed-environment test changes and workbook close are attributed to that external commit, not this run.

## Validation

| Gate | Independently observed result |
|---|---|
| Baseline focused Python | 214 passed |
| Final focused Python plus existing compressor suite | 230 passed, 13.95s, strict ResourceWarning/unraisable warnings, exit 0 |
| New retained regressions | 5; focused directories alone contain 219 tests |
| Node UI | 17 passed |
| Wedge / adversarial F1 | 0.996 / 0.977 |
| Lint E9/F, diff whitespace, installed dependency consistency | Passed |
| 100-client hostile/auth loopback | 1,000 requests, zero transport errors or observed auth leaks; 363.9 req/s |
| Undrained log sink | 2,000 health responses, 1,715 counted log drops; shutdown 0.214s; post-warmup RSS growth 6.58 MiB |
| Latest bounded broad suite | **831 passed, 15 failed, 17 skipped**, stopped at 15 failures; not a complete run |
| Isolated legacy tracing strict process | **exit 1 despite 23 passed assertions**: unclosed SQLite and ZipFile finalization errors |

Fresh environment collection initially had 37 errors; installing real document, code, analytics and embedding dependencies recovered execution. Four environment remediation rounds, then checkpointed below the five-cycle limit. Latest blockers include podcast/TTS provider configuration, faster-whisper, cross-suite Opik trace suppression and resource lifecycle errors. External commit `202f75f` does not eliminate the observed broad failures. Sealed-mode state is intentionally irreversible: do not reset production security state to make tests green; isolate suites in processes and verify both orders. Rust and Docker are not installed locally; remote focused jobs are not a substitute for the full suite.

## Compression telemetry benchmark

20,000 records followed by 200 snapshots; same interpreter, baseline `0800f13`. Tracemalloc measures retained Python allocations from the write phase, not process RAM.

| Metric | Baseline | Fixed |
|---|---:|---:|
| Snapshot P50 / P95 / P99 ms | 1.356661 / 1.561401 / 2.447682 | 0.002930 / 0.003210 / 0.004350 |
| Retained Python bytes | 3,855,320 | 1,216 |
| Record throughput with tracemalloc, req/s | 471,356 | 108,224 |
| RSS phase-boundary floor / ceiling MiB | 18.32 / 24.67 | 24.67 / 24.68 |

Snapshot P99 fell ~563x; retained Python allocations fell 99.97%. Writes are slower because locking and defensive copies buy correctness. The old module remains loaded in the same-process comparison; RSS figures do **not** demonstrate a process-RAM reduction. No allocator rewrite or 100x end-to-end throughput claim.

## Gateway: synthetic chaos and bounded live traffic

Re-ran 100 synchronized callers per fault using real cooldown/backoff, comparing main to the hardened branch. Local synthetic 429/503 responses followed by a healthy fallback; no artificial no-op sleeps.

| Fault | P50 / P95 / P99 baseline ms | P50 / P95 / P99 hardened ms | Throughput before -> after |
|---|---|---|---|
| 429 | 1004.983 / 1006.898 / 1007.374 | 4.104 / 4.466 / 4.479 | 97.15 -> 3591.20 req/s |
| 503 | 1007.336 / 1010.383 / 1012.287 | 3.740 / 4.681 / 4.698 | 96.32 -> 4458.73 req/s |

All 200 hardened requests succeeded; P99 below 200ms. RSS sampled every 5ms: baseline 26.40–30.55 MiB, hardened 29.03–30.62 MiB. This re-verifies Session 10's gateway fixes; it is not a new gateway code change, live latency SLO, or proof of worst-case lock timing.

Authenticated live catalog included all four configured model IDs. Four concurrent logical requests, one primary per model, max 256 completion tokens per attempt, zero same-route retries, timeout 6s, total budget 20s, maximum 16 attempts:

| Primary | Logical success | Latency | Observed route |
|---|---|---:|---|
| GLM-5.3 | Yes | 8.110s | Timeout, then GLM-5.3 Flash |
| GLM-5.3 Flash | Yes | 1.480s | Primary |
| Kimi K3 | Yes | 2.631s | Primary |
| Qwen 3.8 27B | Yes | 1.345s | Primary |

Successful completion counts: 13, 13, 36, 37, each within 256. Timeout attempts may still be billed. One sample per primary does not certify availability or percentile latency. Model budget rejection/fallback regression tests passed; aggregate spend reservation is still not implemented. High-volume faults remained local, not sustained external-provider hammering.

## Ingress: honest capacity results

300 real extraction requests per phase; 1 then 100 clients, four server workers, bounded admission, loopback socket, same fixture. Baseline `0800f13`; final production changes retain serialization.

| Phase | 200 / 503 | P50 / P95 / P99 ms | Total / useful req/s | RSS MiB |
|---|---|---|---|---|
| Baseline 1 client | 300 / 0 | 271.29 / 287.88 / 317.14 | 3.66 / 3.66 | 79.86–92.62 |
| Baseline 100 clients | 26 / 274 | 820.10 / 4141.34 / 6760.32 | 35.75 / 3.10 | 92.61–112.78 |
| Final 1 client | 300 / 0 | 276.04 / 533.93 / 732.00 | 3.11 / 3.11 | 80.05–92.96 |
| Final 100 clients | 26 / 274 | 750.13 / 3982.62 / 6752.71 | 34.82 / 3.02 | 92.96–113.34 |

**91.3% shed at 100 clients.** No unexpected HTTP statuses or transport errors; readiness and explicit lifespan-complete marker passed; SIGTERM exit -15 expected. Other validation and dependency installation overlapped parts of measurements; not isolated production benchmarking. These results do not establish useful capacity growth. The final code fixes telemetry and correctness, not the extraction CPU bottleneck.

## Five-point launch premortem / next owner

1. **Worker starvation / CPU saturation — Architect:** retain bounded queues; profile grounding/extraction CPU; evaluate isolated process workers under resource limits and compare useful throughput, not 503 throughput.
2. **Unhandled async/lifecycle failures — Architect:** extraction cancellation regression remains green; fix legacy SQLite/ZipFile closure and require process exit 0 under strict warnings.
3. **Memory/logging pressure — Red team:** constant-retention telemetry fixed; perform sustained multi-replica RSS soak and alert on dropped logs, not just JSON format.
4. **Provider cascades/spend — Red team + product:** local fallback tail passes; live timeouts persist. Add aggregate billable-attempt budget reservations and establish customer-facing latency SLOs.
5. **Release/dependency drift — Founder:** resolve full-suite blockers, isolate sealed/connected tests, pin reproducible environment, define acceptance throughput and connect deployment/collector backends. Focused green CI does not override this NO-GO.

No production endpoint, cluster or collector credentials were supplied. Existing health/readiness, JSON stdout and local OTel context are tested, but production deployment, backend ingestion and multi-replica rollout are unverified. No merge until the mission's unit/integration/E2E and capacity gates pass. Both credentials were used at call time only, not stored in git configuration or artifacts; **rotate the exposed credentials before release**.

Evidence: `docs/axiom/evidence/session11-*`; reproducible scripts under `scripts/benchmark_*`.
