# Axiom-Grid: executed hardening checkpoint

**15 September 2026 • Production decision: NO-GO; concrete fixes submitted for review.**

## What changed versus the supplied handoff
The public repository is accessible and was cloned successfully. The earlier “no repository available” claim does not describe this run. Baseline: `a9afd8c` (PR #16 merged). There were no open PRs when checked; the four latest focused workflow runs were green. Existing remote hardening branches were inspected; the requested branch is an ancestor of main, allowing a normal fast-forward push, not a force push.

I performed parallel diagnostic/test processes, not independent AI-agent reviews; this environment provides no subagent facility. Founder, architecture, and red-team perspectives are covered below. No traction or future model-release claims are certified.

## Resolved root causes
| Finding | Reproduction and correction | Verification |
|---|---|---|
| Entire runtime state directory publicly mounted | `/static/overlay_store.db` returned the SQLite database. Mount only `page_images`, protect it with API authorization. | Regression failed before, passes after; missing database path now 404 without auth enabled. |
| Request cap trusted Content-Length | Chunked oversized JSON bypassed limit; negative length was accepted. Added bounded ASGI byte accounting before parsing; rejects duplicate, negative and enormous numeric length headers. | Four initial boundary regressions failed before; expanded positive/negative tests pass. |
| Empty model output counted as success | A structurally valid empty completion was accepted, preventing fallback. Reject empty/whitespace content and fall back. | New injected-transport test fails before/passes after. |
| Read-only non-root deployment had no writable state | SQLite initialized under `/app/.kairo`, without an owned writable mount. Introduce `AXIOM_STATE_DIR`, owned image directory and named volume; align image writer. | Local custom-state smoke passes. Actual Docker gate added, execution pending. |
| Tracing configured but runtime missing SDK launcher | Image omitted telemetry requirements and initialized no SDK exporter. Install pinned telemetry requirements, invoke OTel launcher, explicitly select HTTP/protobuf. | Local smoke reports real TracerProvider, trace-correlated JSON logs and readiness 200. Collector delivery not proven. |
| Edge forwarded attacker-controlled first XFF entry | App trusts first XFF when configured; edge previously appended. Replace with immediate peer address, pass Host. | Configuration reviewed; deployed Nginx test still required. |

Container command now explicitly bounds concurrency at 128 and graceful shutdown at 20 seconds. This is a per-worker safety bound, not a globally coordinated quota.

## Test evidence
- Baseline focused Python: **172 passed**.
- Final focused Python: **181 passed**, 12.60 seconds, ResourceWarning and unraisable warnings treated as errors.
- UI Node suite: **17 passed**. These are simulated UI tests, not native desktop E2E.
- Ruff E9/F overlay + kernel: passed.
- Full repository collection: **2,607 collected, 41 errors** (missing inherited dependencies and duplicate module names). Not green; not hidden or arbitrarily quarantined.
- SEC-006 live socket auth matrix: **400 requests, 40 threads, zero transport errors**, all expected status invariants held.
- Mixed extraction/security stress: 16/16 probes; 300 requests, 30 threads; statuses 200:100, 404:103, 422:81, 429:16; no unhandled crashes. P95 1,143.07 ms, P99 1,175.79 ms. This does not meet a 120/250 ms all-request target.
- Undrained stderr: 2,000 health requests; no failures, shutdown 0.214 seconds; logs shed 1,715; RSS grew 5,648,384 bytes after warmup. Short-run evidence, not a memory-leak soak.
- Wedge F1 0.996, adversarial F1 0.977. Fixture evidence only.
- Cargo and Docker are absent locally. New CI job builds/runs a read-only, non-root overlay container and checks fail-closed authorization, readiness and shutdown.

## Probe benchmark deltas
Same host/cgroup, Python 3.14.6, one server worker. Closed-loop GET requests across healthz/livez/readyz/metrics; 100 concurrency means 4 client processes ×25 threads. Baseline and changed trees measured sequentially. Other diagnostic work in the sandbox and lack of repeated trials limit causal attribution. RSS is process-tree VmHWM sum, not a proven memory ceiling.

| Revision | Concurrency | Requests | P50 ms | P95 ms | P99 ms | req/s | Errors | RSS MiB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| a9afd8c | 1 | 500 | 1.25 | 1.61 | 12.91 | 566.0 | 0 | 80.9 |
| a9afd8c | 100 | 2000 | 150.83 | 230.83 | 394.16 | 567.6 | 0 | 101.8 |
| working-tree | 1 | 500 | 1.26 | 1.66 | 1.95 | 619.2 | 0 | 80.2 |
| working-tree | 100 | 2000 | 113.97 | 188.83 | 322.8 | 695.5 | 0 | 102.1 |

At concurrency 100 the observed P95 fell 18.2%, P99 fell 18.1%, throughput rose 22.5%, and RSS rose 0.3 MiB. These single-run differences do **not** prove a performance improvement. **P95 188.83 >120 and P99 322.8 >250: release targets FAIL.** Concurrency rose 100-fold, but offered traffic/capacity did not; this is NOT a successful 100× production load certification.

## Live gateway smoke
With the user's explicit authorization, the supplied credentials were verified and used narrowly: GitHub identity/repository operations and one catalog request plus two serial rounds of four tiny model completions. No prompt contains customer data. No provider flood, no credential values saved in code or evidence. The initial 32-token round was insufficient to guarantee useful text; post-fix round used max_tokens=128, zero retries and one request per model. All four returned nonempty text with `finish_reason=stop`:

| Model | Router success | Elapsed ms (one sample) | Total tokens | Nonempty text |
|---|---|---:|---:|---|
| glm-5.3 | True | 5336.25 | 20 | True |
| glm-5.3-flash | True | 7396.85 | 63 | True |
| kimi-k3 | True | 1395.62 | 162 | True |
| qwen3.8-27b | True | 875.47 | 51 | True |

These are connectivity/content smoke checks, **not percentile benchmarks** or live outage/fallback verification. Existing injected-transport tests exercise 429, 5xx, Retry-After, budgets and breakers. Breakers and quotas remain process-local. Rotate both exposed credentials after handoff; original attachments themselves contain the values. Current tracked-file pattern scan found one test fixture candidate, not an exhaustive Git-history audit. Never publish original attachments as evidence.

## Five-point launch premortem / remaining blockers
1. **Overload and amplification:** per-worker queues, middleware body buffering, demo serialization and parser rereads can still overload a replicated service. Need separate-host offered-rate extraction soak, cancellation/fault matrix, CPU/RSS limits and quotas calibrated to an actual baseline.
2. **Document isolation failure:** public DB mount closed, but arbitrary file-path APIs still admit broad workspace/temp roots. No per-tenant document ownership enforcement was established. Do not sell this as multi-tenant SaaS. Restrict to isolated single-tenant preview; design opaque document IDs + tenant-bound storage before public hosting.
3. **Provider recovery failure:** routing is bounded locally, not a distributed breaker or spend ledger. Validate request-wide deadlines under slow streaming, global quota coordination, cancellation, provider retention terms and controlled staged failover.
4. **Deployment and observability drift:** container CI must actually pass. Image digest/SBOM, dependency audit, persistent-state backup/restore, collector export, TLS/edge routing, readiness/metrics access and 60-minute canary/rollback remain unverified. A shared volume does not establish multi-replica application-state consistency.
5. **Product trust failure:** README describes a local writing copilot, while overlay remains deterministic preview extraction with test-mode gateway and synthetic apply semantics. Do not market cloud routing as desktop end-to-end inference or “safe insertion.” Pick one product boundary and validate it with native tests and users.

## Launch verification checklist
- [x] Clone/audit baseline and branches; reproduce concrete regressions.
- [x] Focused Python and UI suites green; security/fault smoke evidence attached.
- [x] Four model routes return useful bounded text in live smoke.
- [ ] Rotate exposed credentials; verify incident scope/history purge.
- [ ] Independent reviewer approves code and deployment topology.
- [ ] Intended full-suite scope established; no unexplained collection failures.
- [ ] Native runtime/desktop E2E and actual image CI green.
- [ ] Exact image SBOM, dependency/license audit and vulnerability disposition.
- [ ] Tenant isolation or explicit single-tenant deployment boundary enforced.
- [ ] Separate-host offered-rate soak passes P95≤120ms, P99≤250ms, zero unexpected errors, RSS<85% limit.
- [ ] Live staged provider failover/Retry-After/budget behavior verified after rotation.
- [ ] Collector export + alerts proven; 5% canary 60 minutes, rollback<5 minutes.
- [ ] Signed distribution, support/recovery docs and real-user activation verified.

## Founder decision / value experiment
Do not promise September 16–17 production readiness. Offer a **single-tenant deterministic memo-extraction design-partner preview** only after closing file access boundaries. Do not label cloud-enabled behavior air-gapped. Lead with source-grounded, reviewable extraction on supported text fixtures—not universal office automation, GPT release speculation or 100× claims.

Proposed (not achieved) next experiment: recruit five regulated-workflow reviewers; each evaluates ten consented/redacted memos against manual work. Measure median time-to-reviewed-result, correction rate, first-session completion, week-one return and willingness to pay. Target ≥30% review-time reduction without quality regression and three repeat users before broadening scope. Avoid raw-document analytics. Product-market fit cannot be manufactured by a code PR.

## Reproduction
```sh
python3 -m pip install -r docker/requirements-runtime.txt -r requirements-telemetry.txt pytest pytest-asyncio hypothesis httpx psutil ruff
python3 -m pytest -q overlay/tests kernel/tests -W error::ResourceWarning -W error::pytest.PytestUnraisableExceptionWarning
node --test phantom-overlay/tests/app.test.cjs
python3 scripts/stress_sec006_gauntlet.py
python3 scripts/stress_wave11.py
python3 bench/scaleout_bench_mp.py --workers 1 --procs 4 --threads 25 --requests 2000
```
All modules stayed below five remediation cycles. No production merge authorized by this evidence. Keep the PR draft until review and release gates close.
