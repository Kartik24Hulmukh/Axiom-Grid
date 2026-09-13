# Axiom-Grid production hardening checkpoint — 2026-09-13

**Decision: HOLD production release.** This PR fixes reproduced architectural faults but does not meet the directive's full definition of done. Do not merge/deploy as a production certification.

Base: `cda452487a90a10c2f4024939471ebf3ac82bfbc`. Branch: `harden/axiom-grid-prod`.

## Repository diagnostics and evidence provenance
- Both attached Markdown reports were read. GitHub confirms PRs 11, 13 and 14 merged; current main is cda45248, superseding the older certification's 131d719f deployment advice. Main's latest focused CI is green, but README explicitly calls the product an engineering preview.
- Remote has 14 branches, including three prior harden/axiom-grid-v1-prod variants. No open PRs at audit start. Work is isolated from those branches.
- Runtime dependencies: focused standalone Rust axiom-runtime; inherited Cargo workspace contains phantom-core, Tauri overlay, MCP and agent SDK; Tokio/serde/tracing shared. Python overlay depends on FastAPI/Pydantic, SQLite, kernel/sidecar and document packs. Node preview has independent browser-behavior tests. Requirements-test includes broad optional document/ML engines and duplicate pdfplumber; Docker installs floating FastAPI/Uvicorn/Pydantic, not requirements.lock. This is a reproducibility blocker, not a completed supply-chain certification.
- Baseline focused Python: **151 passed / 0 failed**, 14.34s. Node: **17 passed**. Full Python collection: **2,606 collected / 41 collection errors** (optional dependencies, import collisions). No Rust toolchain here; current branch native gates delegated to CI. No native desktop real-model E2E was executed.
- Attached MP4 is a 30.27-second 1920x1080 screen recording, no audio stream. Frames were extracted but the browser could not display local files; it is not used as verification evidence.

## Five-point premortem
| Catastrophic failure at 100x concurrency | Evidence / mitigation | Residual gate |
|---|---|---|
| Cold readiness calls delete each other's probe, removing healthy pods | Reproduced 503 in baseline; publish success and clean up under the worker lock; private temporary directory isolates processes and symlinks | Readiness remains a startup extraction certification, not continuous DB/model health |
| Gateway stampede exhausts sockets/worker memory | Previously only metadata lock was bounded; add nonblocking 32-call bulkhead and 100-contender regression | Tune admitted capacity to actual provider quota; synchronous calls still need off-event-loop execution |
| Retry storm amplifies 429/5xx and recovering half-open probes | Retry-After was clipped to 2s; honor date/seconds, share cooldown across calls, skip permanent 4xx, single half-open attempt | In-flight pre-cooldown calls cannot be revoked; no distributed breaker across replicas |
| Oversized prompt/response or malformed metadata exhausts memory/budget | Add 256 KiB encoded request and 2 MiB response caps; retain completion cap and validated atomic accounting | Byte cap is not tokenizer-accurate input cost; options serialize before final byte check; socket timeout is not an interruptible wall-clock transport deadline |
| Logging stalls, SQLite contention or queue starvation collapse tail latency | Existing bounded log queue and extraction pool retained; undrained-stderr fault gate passes; opt-in OTel spans and correlated JSON trace IDs | Mixed extraction P95 ~1s; log records are intentionally dropped under pressure; long-duration durability/soak not proven |

## Resolved root-cause log
1. **Readiness publication race:** worker released lock before the event-loop caller set the ready event; cleanup lived outside the lock on one shared filename. Next worker could rewrite while previous caller unlinked. Initialization, event publication and cleanup now share one ownership boundary. Regression: 1,000 cold requests at 100 workers execute extraction exactly once; failure is not cached.
2. **Router admission and amplification:** no actual outbound concurrency ceiling; Retry-After shortened; malformed HTTP-date could lose HTTP status; half-open probe retried. New bulkhead, per-request scheduling budget, shared 429 cooldown, correct retry parsing, permanent-error bypass and one probe attempt.
3. **I/O and token boundaries:** unlimited response read and unlimited message bytes despite completion caps. Bound request/response bytes, reject nonfinite JSON; preserve max_tokens/max_completion_tokens semantics. Add GLM-5.3 Flash to catalog-verified defaults.
4. **Observability gap:** structured JSON and health probes already existed but no native OTel spans. New opt-in middleware uses real OTel API, safe route templates and status, no headers/query/body capture; JSON logs carry active trace/span IDs. SDK in-memory export regression verifies correlation. No fake exporter or unsolicited telemetry egress.
5. **Benchmark memory visibility:** start/end RSS omitted peak. Harness now reports Linux VmHWM. This is observed process peak, not an enforced memory ceiling.

## Benchmarks — retain failures, do not cherry-pick
Same host, 2,000 live HTTP requests per run, five probe/metrics paths, all expected 2xx. Baseline tests ran concurrently with the 1-thread baseline; first exploratory after run overlapped tests. Final runs were serial and uncontended. Results are directional, not a controlled performance claim.

| Run | Threads | P50 ms | P95 ms | P99 ms | RPS | HTTP success | RSS end / observed peak MiB |
|---|---:|---:|---:|---:|---:|---:|---|
| Base cda45248 | 1 | 1.21 | 1.74 | 10.84 | 680.6 | 2000/2000 | 80.4 / unavailable |
| Base cda45248 | 100 | 101.98 | 164.98 | 168.10 | 884.4 | 1999/2000 (one 503) | 103.7 / unavailable |
| Early patch (test overlap) | 100 | 124.99 | 206.40 | 212.50 | 731.8 | 2000/2000 | 102.5 / unavailable |
| Final | 1 | 1.12 | 1.45 | 2.05 | 824.1 | 2000/2000 | 80.5 / 80.5 |
| Final A | 100 | 115.58 | 169.87 | 176.39 | 812.0 | 2000/2000 | 101.9 / 101.9 |
| Final B | 100 | 113.45 | 181.76 | 186.45 | 823.3 | 2000/2000 | 102.9 / 102.9 |

Base→Final A at 100 threads: P50 **+13.60ms**, P95 **+4.89ms**, P99 **+8.29ms**, throughput **−72.4 RPS (−8.2%)**, end RSS **−1.8 MiB**; HTTP errors **1→0**. P95 fails the 120ms gate. SIGTERM final 100-thread runs: 0.164s. 100 workers vs one is 100x *client concurrency*, not verified 100x production traffic or throughput.

- SEC-006 live-socket: 400 requests / 40 threads, 10 traffic classes, all invariants pass; 435.9 RPS, P50 93.15ms / P99 210.64ms, zero transport errors.
- Undrained stderr: 4×500 requests / 40 workers, all 200, 1,715 dropped logs; post-warmup RSS growth 6,512,640 bytes; clean shutdown 0.164s. Warmup P99 291ms exceeds 250ms; final batch P95 58.58ms.
- Mixed ASGI extraction/security: 16/16 security probes; 300 requests / 30 threads; status 200×100, 404×103, 422×81, 429×16, no crashes. P50 27.41 / P95 1007.74 / P99 1048.04ms; 167.64 RPS. This is not a passing production latency gate.

## Live Melious smoke (not provider load torture)
Catalog checked with bearer auth. Two maximum concurrent calls, one request/model, 32 completion tokens each (128 total configured maximum), 20s socket timeout. No real-provider 100x flood.

| Model | Result | Latency ms | Returned completion tokens |
|---|---|---:|---:|
| GLM-5.3 | HTTP 200, one choice | 938.55 | 32 |
| GLM-5.3 Flash | HTTP 200, one choice | 1065.15 | 32 |
| Kimi K3 | TimeoutError | 20412.72 | unknown |
| Qwen 3.8 27B | HTTP 200, one choice | 900.52 | 23 |

Single samples cannot establish P50/P95/P99. HTTP 200 alone does not prove useful output: GLM budgets were consumed by reasoning. Offline fault injection covers fallback, timeout, 429 cooldown, malformed usage and concurrency; it is not evidence of live failover quality.

## Verification and convergence
- Final focused Python after remediation: **171 passed, 0 failed**, 12.58s; strict ResourceWarning and unraisable-exception gates.
- Added real OTel SDK test runs in focused CI (SDK dependency added); changed-file ruff and E9/F gates pass; diff whitespace check clean.
- Router: two remediation cycles. Readiness: one cycle to update failure-injection fixture signature. Benchmark: one cycle to update RSS mock signature. Lint: one cycle. No module exceeds the five-cycle cap.
- Full repository collection and optional/native/E2E are checkpointed blockers, not silently skipped green gates. No broad dependency upgrades, DB migration or desktop behavior changes.

## Opt-in telemetry deployment
Install `requirements-telemetry.txt`, set `AXIOM_OTEL_ENABLED=1` and `OTEL_SERVICE_NAME=axiom-grid-overlay`; configure an approved `OTEL_EXPORTER_OTLP_ENDPOINT`. Run through `opentelemetry-instrument --traces_exporter otlp --metrics_exporter none --logs_exporter none python3 -m uvicorn overlay.server:app ...` with `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=fastapi,asgi` to avoid double instrumentation if auto-instrumentation packages are present. The custom middleware is the span owner. The base Docker image does not include optional telemetry packages; build an explicitly reviewed image. Test collector delivery before rollout. No prompt/body/header capture is enabled by this patch.

## Launch verification checklist
- [x] Isolated branch and semantic commits; no credentials committed.
- [x] Focused Python regression suite green; Node 17 tests green.
- [x] Security, stderr backpressure and cold readiness concurrency tested.
- [x] Baseline and after evidence retained, including failing SLOs.
- [ ] New-head native Rust/Tauri and both focused CI jobs green; independent review.
- [ ] Resolve 41 full-suite collection errors in a supported locked environment; all Unit/Integration/E2E green.
- [ ] Real native target-bound preview E2E with required installed model.
- [ ] Establish actual production baseline and pass sustained 100x mixed-workload soak and latency SLOs.
- [ ] Kimi K3 recovers; useful-output quality, fallback and input-token spending budgets verified.
- [ ] Fix remaining tail-latency regression and continuously validate readiness dependencies.
- [ ] Audit/pin runtime dependency graph, build image and vulnerability scan; configure CPU/memory limits.
- [ ] Verify OTel collector spans/log correlation and alerts on 429, breaker state, shed traffic, dropped logs and RSS.
- [ ] Rotate both credentials supplied in chat before production. Require auth, set tenant keys, trusted proxies and CORS allowlist; restrict unauthenticated metrics at ingress.
- [ ] Snapshot SQLite; canary release with rollback rehearsed; only then mark PR ready for review/merge.

Rollback: revert this PR as a unit or deploy base cda45248. Preserve/snapshot SQLite state; no schema migration is introduced. Never delete state to restore service.
