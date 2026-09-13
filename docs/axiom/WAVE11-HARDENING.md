# Wave 11 — Production hardening, independently reproduced

**Decision: NO-GO for production. Reviewable hardening changes, not enterprise certification.**

## Scope and provenance
- Repository: Kartik24Hulmukh/Axiom-Grid. Started from PR #8 head `af856b73c203611d2496d8b26cb790b06e4cc221` on dedicated branch `hardening/wave11-readiness-verification`.
- Main observed at `4e304bd`. No main push, merge, or deployment performed.
- Read the supplied Wave 10 report, then cloned and tested actual source. Its blanket “production readiness achieved” conclusion is not supported by this run.
- Tests ran in Linux, Python 3.14.6; Rust/Cargo and Tauri system dependencies unavailable locally. No native real-model E2E was executed.

## Baseline BEFORE changes
- Initially pytest and Ruff were absent. Installed test tooling; this is an environment prerequisite, not a code regression.
- Existing focused CI Python selection: **65 passed (13.81 s)**.
- Node UI tests: **17 passed**.
- Repository-wide pytest collection: **2,537 tests collected, 41 collection errors**. Causes include missing document/office dependencies, missing `packs.wedge`, and duplicate `latency_test` / `memory_leak_test` module names. Therefore the full unit/integration/E2E suite did NOT pass.
- Changed production-file Ruff baseline: **13 errors**, not merely F401 warnings.
- Full-tree Ruff scan later found **2,074 issues across 325 files**, including 55 invalid-syntax findings; this includes inherited code, not solely the focused executable.
- Ground-truth / adversarial F1 rerun: **0.996 / 0.977** (offline deterministic; not live model accuracy).

## Defects reproduced and remediated
| Issue | Red evidence | Patch and verification |
|---|---|---|
| Origin gate uses URL prefix matching | Accepted userinfo, invalid ports and paths; configured non-local origin denied | Parse exact authority; reject userinfo/path/query/fragment/control characters; honor explicit allow-list; retain valid local ports |
| Non-ASCII request IDs | Raw high byte survived `isalnum` filtering | Restrict correlation IDs to ASCII safe characters |
| Malformed upstream usage corrupts accounting | Success increments before usage validation; partial token accumulation; negative/bool counts accepted | Validate all counts before changing success/breaker/token state; malformed metadata follows fallback |
| Router exception disclosure | Arbitrary exception text copied into successful fallback output and failure trace | Replace raw detail with bounded static text / numeric HTTP status; preserve compatibility for HTTP status diagnostics |
| Cancellation defeats extraction admission | Cancelled coroutine freed semaphore while worker continued | Capacity released on the concurrent future completion, not coroutine cancellation; failed submission releases immediately |
| Uvicorn lifecycle logging still blocks SIGTERM | Default INFO + undrained stderr: 2,000 successful requests then shutdown >5 s, twice; warning-only variant shut down in 0.164 s | Route Uvicorn loggers through existing bounded queue, avoiding synchronous lifecycle sink; identical default-level test now exits in 0.114 s |

Initial adversarial run: **18 failed / 3 passed**; cancellation regression independently failed before patch. New regression module count is 26 (including timeout, dropout, bounded synthetic 429 retry, and out-of-order token accounting). No component exceeded 5 remediation cycles. Router compatibility required a second iteration. Serving fixes and logging verification converged within the limit.

## Final local verification
- `python3 -m pytest -q overlay/tests kernel/tests --cov=overlay.server --cov=kernel.sidecar.melious_router --cov-report=term-missing`: **128 passed, 5 ResourceWarnings, 13.65 s**.
- Coverage: **overlay server 79%; model router 91%; combined statement coverage 81%**. Not whole-repository coverage.
- ResourceWarnings identify unclosed SQLite connections; full lifecycle cleanup remains unresolved.
- Changed-file Ruff gate: **PASS**. `git diff --check`: **PASS**.
- Node UI suite: **17 passed**.
- Existing security stress: **16/16 probes**, 300 mixed requests, 30 threads, no unhandled crashes.
- SEC-006: 400 requests / 40 threads, **zero transport errors**. One readyz request returned 503; the existing gauntlet permits this. This is not 100% readiness success.
- New socket spike: 4 batches × 500 requests / 40 threads; **2,000/2,000 HTTP 200**, P99 < 500 ms local test gate, shutdown <5 s, RSS growth after warmup <32 MiB local observation gate.

## Before / after benchmarks (same sandbox; not production SLO certification)

| Workload | Before P50 / P95 / P99 (ms) | After P50 / P95 / P99 (ms) | Before → after throughput |
|---|---|---|---|
| 300 mixed requests, 30 threads | 29.48 / 1124.61 / 1158.25 | 29.09 / 1028.69 / 1038.91 | 134.26 → 146.73 req/s |
| SEC-006 400 requests, 40 threads | 48.63 / not recorded / 86.16 | 47.58 / not recorded / 83.93 | 837.8 → 861.7 req/s |
| Undrained stderr, final 500-request batch, 40 threads | 40.67 / 42.74 / 43.17 | 42.38 / 51.58 / 53.48 | 978.30 → 929.60 req/s |

The undrained-stderr comparison is before/after the Uvicorn logging fix with other Wave 11 changes already applied. Its improvement is termination reliability, NOT a claimed latency improvement. Before SIGTERM: >5 s (killed); after: **0.114 s**. Final short-run RSS increased **5,283,840 bytes** after warmup; no long-duration or extraction-memory leak claim. **1,715 logs dropped** under intentionally blocked sink: availability preserved, log loss visible. Mixed stress produced expected 404/422/429 responses; these are not transport failures. `100x` is the inherited script label, not a demonstrated multiple of a measured production arrival rate. Runs are short and not statistically significant performance proofs.

## Live Melious verification and secret handling
- Credentials consumed from process environment; neither credential saved in source, evidence, Git config, or PR body. The original supplied values are already exposed in task text: rotate both after this run.
- GitHub authentication and Melious catalog lookup each returned HTTP 200.
- Three bounded live router calls, one per configured default model, max_tokens=16 and timeout=12 s, all returned structurally valid completions.
- GLM-5.3: **506.09 ms; 16 prompt / 3 completion / 19 total tokens; 1 reasoning token**.
- Kimi K3: **1127.80 ms; 128 prompt / 16 completion / 144 total; 16 reasoning**.
- Third configured 27B route: **624.32 ms; 14 prompt / 16 completion / 30 total; 16 reasoning**. Use exact catalog ID in evidence; do not infer provider capability/version from a marketing name alone.
- Total **193 tokens** reported. One sample/model cannot support P50/P95/P99, sustained rate-limit or soak claims; completion success does not prove useful final text when reasoning exhausts the tiny output budget.
- Mock tests cover 429 fallback, network timeouts/dropouts and concurrent/out-of-order accounting. No intentional saturation of the external provider.

## Architecture delta
Request → auth/rate-limit/origin validation → bounded extraction admission → worker-owned future → response. Cancellation no longer admits replacement work until the original worker completes. Uvicorn and application logging share the bounded nonblocking log queue. Router accounting is validated before atomic state update. No database migration or horizontal-state redesign was made.

## Top five 100x-load premortem risks still relevant
1. **Process-local state and global orchestration lock:** multiple replicas have divergent in-memory stores, rate buckets and breakers; one global lock serializes worker work. Externalize authoritative state and enforce idempotency/transactions before horizontal rollout.
2. **Incomplete I/O admission:** file read/classification and per-request SQLite setup happen before extraction semaphore acquisition; full-file reads and request bodies without trusted Content-Length need actual-byte limits. Bound admission before allocation and test chunked inputs / large authorized files.
3. **Upstream amplification:** per-attempt timeouts are not an end-to-end deadline; retries/fallback multiply latency and token cost. Add aggregate request deadline, shared quotas, Retry-After policy and coordinated half-open validation.
4. **Resource lifecycle / termination:** cancellation and Uvicorn INFO stall fixed here, but SQLite ResourceWarnings and short-only RSS testing preclude leak certification. Require extraction soak, dependency loss and rolling-shutdown tests with production log sinks.
5. **Readiness/telemetry blind spots:** readiness can return 503 under concurrency; cached successful probe is not proof of every dependency. Prometheus `otel` alias is not an OpenTelemetry SDK/exporter. Implement real OTLP and failure-responsive dependency readiness.

## CI/CD and deployment checklist
- [x] Dedicated branch; semantic commits; new regressions and changed-file lint wired into focused GitHub Actions workflow.
- [x] Add reproducible loopback spike / undrained logging / shutdown gate, no external calls.
- [ ] Review stacked base: this branch contains unmerged PR #8 prerequisites. Do not merge blindly or duplicate their commits in another release branch.
- [ ] Await current-head GitHub Actions (runtime and Tauri); local Python success is not their substitute.
- [ ] Establish supported Python/dependency lock; `requirements.lock` currently contains lower bounds, not a reproducible lock; Docker installs unpinned packages.
- [ ] Resolve full-suite collection/lint failures or explicitly ratify focused product scope and segregate inherited suites. Do not label unexecuted suites green.
- [ ] Implement real OpenTelemetry SDK/exporter; provision collector, verify traces and metrics, and bound cardinality.
- [ ] Define approved peak arrival rate, workload mix, duration, error budget and P95/P99 targets; execute extraction/worker/memory soak against representative staging data.
- [ ] Resolve horizontal state, persistence, authorization boundaries and connection cleanup; test duplicate/out-of-order writes and dependency outage.
- [ ] Rotate exposed tokens; store replacements in CI/environment secret stores; enforce production auth, exact CORS and TLS ingress limits.
- [ ] Build/scan image and dependency SBOM; stage one replica, probe health/liveness/readiness, then canary with explicit rollback to prior immutable image. No migration performed by this patch.

**Release gate remains blocked. No deployment target or production infrastructure was supplied. No deployment was attempted.**
