# Session 13 — resource ownership repaired; launch remains NO-GO

**15 September 2026. Branch: `harden/axiom-grid-prod`. PR #20 stays draft; no merge or deployment.**

## Concrete progress

Read both attached Session 12 documents, cloned the requested branch at `5989e3a`, and verified the live PR and all 16 remote branches. `main` was `cb9cd579`; the original four focused checks were successful. Other branches were inventoried, not merged.

- `e3c9afc`: restored truthful Python development/dependency and platform-support contracts in README. Regenerated corpus fingerprint as version 1.3.2: the only addition is the existing `wedge/adversarial_ground_truth.json`; no fixture content changed.
- `aa2b1b8`: repaired actual resource ownership, with five regression cases that each failed on unfixed code. Added a dedicated Python 3.14 strict-resource CI job.
  - `MemMachineClient._connect`: close the SQLite handle if PRAGMA/setup fails before ownership transfers to the caller.
  - `recall_contextualized`: use `contextlib.closing`; SQLite's transaction context manager alone does not close a connection.
  - `WeKnoraPipeline.ingest`: the initial schema query was outside the closing `finally`. Allocation instrumentation traced the legacy E2E leak to this call. The entire connection lifetime is now protected, including early returns and schema/parser failures.
  - `ExcelWriter`: `keep_vba=True` owns a separate ZIP archive that `Workbook.close()` does not release. Close both in `finally`, preserving macro handling and existing error semantics.

No warning suppression, sleeps, dependency bypass, security-state reset or serialization removal was used to manufacture green results. Resource instrumentation was diagnostic only and was not shipped.

## Validation actually executed

| Gate | Result |
|---|---|
| Original focused Python strict gate | 219 passed, 77.76s while broad tests also ran |
| Final focused Python + compressor, strict resource/unraisable warnings | 230 passed, 24.63s |
| Final root `tests/` directory (not entire repository) | 1116 passed, 4 skipped, 56.62s; previous post-doc run also 1116/4 |
| Documentation/platform/corpus subset | 53 passed, 1 skipped |
| Legacy trace/receipt strict process before repairs | 23 assertions passed but process failed at finalization: SQLite + ZipFile exceptions |
| Same legacy trace/receipt strict process after repairs | 23 passed, 1.02s, exit 0 |
| Resource regression + memory + legacy trace/receipt combined | 41 passed, 0.74s, strict, exit 0 |
| Same 41 tests in fresh minimal virtualenv matching new CI dependencies | 41 passed, 0.70s, strict, exit 0 |
| Excel writer regression subset | 17 passed, 1.36s, strict |
| Node UI | 17 passed |
| Changed Python lint E9/F and git diff whitespace | Passed |
| Entire repository bounded run, before final resource fixes | **20 failed, 1549 passed, 28 skipped**, 67.22s; xdist overshot maxfail=15. Not a final all-green gate. |

The initial dependency install failed: embed-anything 0.7.x pins ONNX Runtime 1.22 without a Python 3.14 wheel. Installed the other declared dependencies without `--no-deps`; kept embed-anything explicitly unresolved. A first 16-worker run lost a worker and was stopped; it is not counted as a valid result. Subsequent runs used two workers and bounded BLAS threads. Vendored semantic weights already exist; installing model2vec recovered root PDF E2E tests. Session 12's missing-model explanation is not a current blocker for that root suite.

## 100-client benchmark evidence

Gateway rerun in isolation, baseline `cb9cd579` versus current router. Synthetic 429/503 transport, real routing and backoff, 100 barrier-synchronized callers; these are re-verifications of prior router fixes, not improvements caused by this session's resource changes.

| Fault | Before P50/P95/P99 ms | Current P50/P95/P99 ms | Throughput before/current req/s | RSS before/current MiB |
|---|---|---|---|---|
| 429 | 1004.599 / 1006.325 / 1007.104 | 2.436 / 2.936 / 3.032 | 97.49 / 5933.81 | 25.58–27.08 / 27.07–28.20 |
| 503 | 1003.351 / 1004.453 / 1005.455 | 3.793 / 4.351 / 4.387 | 98.13 / 4102.96 | 25.95–27.82 / 27.06–27.82 |

200/200 hardened logical requests succeeded. Max observed latency 5.169ms (429), 4.391ms (503), below 200ms. An earlier contended run is also preserved (P99 103.414/99.671ms); do not hide host-load sensitivity or infer a universal latency bound.

Real extraction, same process, 300 requests per phase, loopback; other tests shared the host during this run:

| Clients | HTTP 200/503 | P50/P95/P99 ms (all responses) | Total/useful req/s | RSS MiB |
|---|---|---|---|---|
| 1 | 300/0 | 405.64 / 685.93 / 785.17 | 2.29 / 2.29 | 75.88–109.70 |
| 100 | 28/272 | 1718.20 / 7756.24 / 11278.02 | 20.84 / 1.95 | 109.70–126.58 |

No transport errors, readiness recovered, lifespan shutdown explicitly completed. **90.7% shed at 100 clients; useful throughput fell 14.8%, not 100x improvement.** This is a capacity blocker, not a passing load gate. Cross-session absolute latency comparisons are confounded by host contention.

Auth/adversarial gauntlet: 1000 requests/100 clients, 0 transport errors, 227.5 req/s; health/readiness each 100 HTTP 200; no observed auth leaks; traversal/origin/schema rejected as expected.

Live provider: authenticated catalog 200; one logical call per configured GLM-5.3, GLM-5.3 Flash, Kimi K3 and Qwen 3.8 27B route succeeded on its primary in 0.809/1.005/1.367/0.732s. Completion tokens 23/12/41/22, within each 256-token cap. Four calls, up to four routes each, zero same-route retries, 5s attempt/12s logical budget; only four attempts needed. This is bounded smoke evidence, not provider torture/availability certification or an aggregate spend ceiling. High-volume injected faults remained local.

## Five-point premortem / unresolved launch gates

1. **Worker starvation / useful capacity:** global extraction serialization remains. Do not remove it without parser/store/provenance isolation and measured improvement. Need capacity targets, process/replica scaling, realistic fixture mix and sustained soak.
2. **Async/resource failures:** demonstrated legacy SQLite/ZIP finalizers are fixed and enforced in CI. Full repository still fails; no blanket zero-panics claim. Cross-suite sealed-mode isolation and native shutdown need complete validation.
3. **Memory/telemetry pressure:** current sample RSS ceiling 126.58 MiB under contention. Existing bounded JSON logging, W3C context propagation, probes and metrics remain. No real collector/export ingest, multi-replica soak or deployed alerts was available.
4. **Provider cascade/spend:** synthetic fallback gate and bounded live smoke pass. Aggregate/fleet spend reservation remains absent; four model calls cannot establish production reliability or cost ceilings.
5. **Dependency/security/release drift:** full bounded failures include podcast/TTS, faster-whisper, embed-anything/ONNX compatibility, missing LibreOffice recomputation, PDF fitz dependency/license conflict, prompt-shield and airgap guard assertions, native injection API drift, image resize API mismatch and stale repository-size/ignore contracts. These are blockers, not waived tests.

Rust, Docker and LibreOffice are unavailable locally. No staging endpoint, deployment cluster or collector credentials were supplied. Focused remote CI cannot substitute for full native/integration/E2E or useful-throughput certification.

## Release decision and handoff

**NO-GO for September 16–17 until the remaining gates are independently green.** Retained draft PR #20 and did not auto-merge. Changes are restricted to the requested branch with semantic commits. One remediation implementation round per changed module, followed by regression and clean-environment verification; no module exceeded five cycles. Stop rather than broaden this run into unsafe, unverified rewrites.

Next: resolve full-suite dependency/security failures in a reproducible supported environment; re-run whole-repository strict/integration/E2E checks, isolate and benchmark process-level extraction scaling, implement provider spend reservations, then stage with collector ingestion and multi-replica soak. Only after those succeed should the draft be marked ready and merged.

Rotate/revoke both credentials exposed in the task before production. Neither is written to repo files, remote URLs or delivered evidence; Git authentication was process-environment-only and provider authentication call-time-only.

Raw evidence is under `docs/axiom/evidence/session13-*`. CI status on the final evidence commit must be checked on PR #20; do not reuse the old head's green checks.
