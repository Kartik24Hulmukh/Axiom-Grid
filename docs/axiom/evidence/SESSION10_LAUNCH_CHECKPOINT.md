# Session 10 — production launch checkpoint

**Decision: NO-GO for the requested full production release.** September 16–17, 2026 remains the target, not a verified readiness claim. PR #20 is deliberately draft and must not auto-merge while the full-suite gate is red.

## Repository and delivery
- Reverified PR #19 merged at `cb9cd579c52fc30647bf12e3f2f99b4148bfd43a`; three main workflow jobs were successful. This was not accepted as proof that every suite passes.
- Audited 16 remote branches (including main; origin/HEAD is a symbolic reference). All work is on `harden/axiom-grid-prod`; no unrelated branches changed.
- Follow-up PR: https://github.com/Kartik24Hulmukh/Axiom-Grid/pull/20
- Semantic commits: `d33fa6b` gateway + 10 regressions; `ae5a9c2` oracle fixture repairs; `ef5217d` reproducible loopback benchmark. Later evidence commit contains this checkpoint and shutdown-observer correction.

## Root causes actually remediated
1. **429 worker starvation:** Retry-After below the total deadline slept on an inflight permit before fallback. Session 9 injected a no-op sleep and tested a 120-second cooldown, which missed this defect. A new parameterized test failed for 0, 0.01, 1 and 10 seconds before the fix. Route cooldown remains shared, but the current caller moves directly to fallback.
2. **5xx retry amplification:** retries on a failing route delayed a healthy later route. Four failing regressions were reproduced before preferring fallback; bounded retries remain on the last route. Ten new deterministic tests pass, including final-route retry preservation. Two gateway remediation cycles, below the five-cycle limit.
3. **Email fixture corruption:** attachment.bin contained base64 rather than the bytes specified by the existing ground truth. Decoded 1024 bytes match SHA-256 `785b0751fc2c53dc14a4ce3d800e69ef9ce1009eb327ccf458afe09c242c26c9`. Expected oracle values were not edited.
4. **Missing slide fixture:** tests referenced a nonexistent test_image.png and the engine omitted the image. Added a deterministic real PNG fixture; no production mocks and no relaxed assertions. Email, PowerPoint and analytics suites: 57 passed.
5. **Benchmark shutdown observer:** Uvicorn 0.51 deliberately re-raises SIGTERM after shutdown. The first harness incorrectly required exit 0; a second relied on an INFO log filtered by application logging. Final harness wraps the actual lifespan and requires an explicit completion marker plus exit 0 or SIGTERM. The failed observer evidence is retained, not hidden.

## Validation scope
| Gate | Current evidence |
|---|---|
| Focused overlay + kernel | **214 passed** (baseline 204); ResourceWarning and unraisable exceptions treated as errors |
| Node frontend suite | 17 passed |
| Wedge / adversarial F1 | 0.996 / 0.977; both above 0.80 |
| Targeted restored domain fixtures | 57 passed |
| Python E9/F lint and git whitespace | passed |
| Installed dependency consistency | pip check: no broken requirements |
| Full repository collection | 39 initial errors → zero with actual optional dependencies and importlib mode; 3294 tests at collection checkpoint |
| Full repository execution | **831 passed, 15 failed, 17 skipped**, stopped at 15 failures; not a full green run |
| Legacy tracing/E2E in isolation | 23 passed, but ZipFile deallocator warning remains; not strict-warning certified |
| Local Rust / container | cargo and docker unavailable; remote CI must establish these gates |

The broad execution was attempted four times (dependency/toolchain recovery, then fixture recovery); no module exceeded five remediation cycles. Collection and diagnostics were not disguised as passing execution.

### Remaining full-suite blockers
- NotebookLM credential missing; local TTS backend missing; faster-whisper missing. Melious credentials do not authorize other providers.
- Collection imports `tests/test_acceptance_gauntlet.py` and `tests/test_canary_break.py`, which set sealed/offline mode globally. This suppresses Opik trace writes in other suites. The same 23 trace/E2E tests pass when run alone. Fix scope isolation without weakening sealed-mode guarantees.
- ZipFile destructor emits an unraisable ValueError in legacy E2E. Needs lifecycle remediation, not warning suppression.
- Duplicate script/test module basenames require importlib collection mode or proper package isolation.
- Runtime compression falls back when headroom is absent. Optional backend behavior and full dependency manifest remain separate from the focused deployment lock.

## Real-sleep gateway benchmark
100 simultaneous callers, first failing transport synchronized by a barrier, healthy second route. Synthetic transport, **real backoff**, threshold raised only in the benchmark to keep all failures exposed. Percentiles nearest-rank; throughput includes thread startup; RSS sampled every 5ms in the same process. This is not live-provider capacity.

| Fault | P50 before → after ms | P95 before → after ms | P99 before → after ms | req/s before → after |
|---|---:|---:|---:|---:|
| 429, Retry-After 1s | 1003.683 → 5.743 | 1005.891 → 6.953 | 1006.571 → 7.127 | 97.43 → 3598.81 |
| 503, Retry-After 1s | 1004.228 → 3.843 | 1006.614 → 6.387 | 1007.736 → 6.756 | 97.68 → 3928.69 |

Zero errors; post-fix maxima 7.615 / 6.769ms. RSS before spans 26.52–30.76 MiB, after 29.24–30.80 MiB; sequential allocator warmup prevents claiming memory reduction. This proves fast response handling for the measured scenario, not a 200ms network response deadline or worst-case lock bound.

## Bounded live Melious verification
Catalog authenticated successfully; configured GLM-5.3, GLM-5.3 Flash, Kimi K3 and Qwen 3.8 27B routes exercised. Eight simultaneous logical requests, two per primary, `max_tokens=256`, no same-route retries, at most four routes/request. **8/8 served; 3 timeout fallbacks.** Successful responses report completion usage ≤256. Timeout attempts can still be billed upstream; this is not an aggregate spend guarantee.

| Primary | Logical successes | End-to-end latency range | Fallbacks |
|---|---:|---:|---:|
| GLM-5.3 | 2/2 | 16.677–18.007s | 2 to Flash |
| GLM-5.3 Flash | 2/2 | 2.034–5.607s | 0 |
| Kimi K3 | 2/2 | 1.404–20.503s | 1 to GLM-5.3 |
| Qwen 3.8 27B | 2/2 | 0.778–0.932s | 0 |

No meaningful tail quantile claim from two samples/model. Local fault injection, not abusive sustained production hammering, establishes 429/503 handling. Token budget, cancellation, single probe, cooldown and stale-generation fencing are covered by the focused tests.

## Actual ingress: 100× workers, not 100× useful capacity

Same local Uvicorn process, real fixture extraction, 300 requests per phase. Other local validation jobs overlapped portions of the run; these are bounded observations, not isolated production capacity deltas.

| Metric | 1 worker | 100 workers |
|---|---:|---:|
| HTTP 200 / 503 | 300 / 0 | 25 / 275 |
| All-response throughput | 3.73 req/s | 40.22 req/s |
| **Useful extraction throughput** | **3.73 req/s** | **3.35 req/s** |
| P50 / P95 / P99 | 260.15 / 298.80 / 475.75ms | 761.52 / 3470.86 / 5877.91ms |
| Sampled server RSS floor / ceiling | 79.67 / 92.15 MiB | 92.15 / 112.88 MiB |

No transport failures or unexpected response codes. Readiness remained 200 after the spike; actual lifespan shutdown completed, followed by expected SIGTERM exit -15. Admission shed 91.7% of the 100-worker requests: resilience passed for this spike, **customer capacity did not scale**. Prior report's `stress_test.py` label “100x” actually runs 30 threads; this run establishes an explicit 1-to-100 worker comparison instead.

Post-fix auth gauntlet: 1000 requests / 100 workers, 433.6 req/s, P50 225.18ms / P99 486.24ms, no transport errors or auth leaks. Host contention prevents interpreting this as a regression against the earlier 663.6 req/s run.

## Five-point failure premortem
| Failure vector | Evidence and remaining risk |
|---|---|
| Worker starvation | Gateway waiting fixed. Extraction admission is bounded but `orchestrator_lock` still serializes execution. Independent-memory ownership and pipeline safety must be proven before removing the lock. |
| Async exceptions | Focused strict tests green; legacy ZipFile warning remains. No universal zero-panics claim. |
| Memory/log pressure | 2000 health requests under undrained stdout/stderr: no hang, 1715 logs shed, RSS growth 6.60 MiB across short batches. Bounded queue works, but dropped telemetry needs alerting and longer soak. |
| Provider cascade/spend | 429/5xx fallback improved; three live timeouts demonstrate provider-tail risk. No fleet-wide spend ceiling established. |
| Dependency/gate drift | Focused preview CI is not full unit/integration/E2E certification. Broad suite remains red. |

## Observability and deployment boundaries
Existing W3C OpenTelemetry trace continuation, structured JSON logging, bounded logging queue, `/healthz`, `/readyz` and metrics were inspected and tested. No deployment endpoint or cluster was provided; no production rollout or collector-backend ingestion was verified. An installed SDK alone is not full-stack observability deployment. Multi-replica soak, queue-age alerts, dropped-log alerts and sustainable useful-throughput targets remain release gates.

## Reproduce
```text
python3 -m pytest -q -p no:cacheprovider overlay/tests kernel/tests -W error::ResourceWarning -W error::pytest.PytestUnraisableExceptionWarning
python3 -m pytest --import-mode=importlib -q --maxfail=15
python3 scripts/benchmark_router_fallback.py cb9cd579
python3 scripts/benchmark_ingress_launch.py
python3 scripts/stress_sec006_gauntlet.py 1000 100
```

No credentials were committed. Rotate both credentials supplied in the conversation. Keep PR #20 draft until failing full-suite gates, sustained-capacity targets and deployment evidence are resolved. Do not reinterpret backpressure responses as successful customer work.
