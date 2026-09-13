# v1.0-PROD independent release review

Status: NO-GO. Baseline commit c1fbe270ee7144a1ff3cd85c5a77735cd499969a.

## Frozen baseline
128 focused tests passed with ResourceWarning and unraisable exceptions fatal; 17 Node tests passed. Broad overlay/kernel lint: 89 findings. Repository-wide collection: 2563 tests collected, 41 errors (missing dependencies and missing packs.wedge). Rust toolchain unavailable locally. Existing PR #11 CI failed on import order.

Baseline probe harness: 2000 requests/100 threads, P50 103.18ms, P95 136.43ms, P99 167.48ms, 1088.1 RPS; **only 1350 HTTP 200, 150 HTTP 404, 500 HTTP 429**. Zero transport errors is NOT availability. RSS 78.3→100.3 MiB. Short probe-only test is NOT a 100x mixed workload or uptime certification.

## Premortem (hypotheses, not all resolved)
1. Admission overload: bounded extraction slots shed 503; rejected useful requests consume the availability error budget.
2. SQLite concurrency/lifecycle: shared connections, close without coordinating workers, repeated ASGI lifespans leave closed references.
3. Router failure amplification: per-route timeouts compound, malformed choice bodies pass shallow validation, no enforced completion budget.
4. False-positive release gates: benchmark counts HTTP 404/429 as successful transport and always exits zero; no defined baseline RPS or soak.
5. Deployment mismatch: process-local quota/circuit states multiply across workers; demonstration inference and absent unified OTel cannot establish production E2E.

## Safety
Credentials were present in supplied certification/chat. Rotate both credentials; never copy attachments into git. Do not delete the SQLite database during rollback. Preserve and snapshot durable state.

## Dependency graph and scope
- Python overlay: FastAPI/Pydantic + Uvicorn → ingestor/security filter → pack extractor → tiered inference/quality gate → SQLite store/provenance. Optional document engines and headroom compression are unavailable in this environment; compressor uses fallback.
- Melious router: independent synchronous urllib gateway with threaded circuit state. Overlay inference does **not** call this router; live model smoke is not end-to-end application verification.
- Rust workspace: phantom-core, Tauri overlay, MCP server, agent SDK → Tokio/Serde/tracing. Separate axiom-runtime workspace → Axum/Reqwest/Tokio/Yrs. Local Rust compilation not performed (no toolchain). Existing remote checks are evidence only for their exact prior SHA.
- `requirements-test.txt` and `requirements.lock` use minimum-version ranges, not a reproducible transitive lock. No clean all-product release build established.
- Baseline coverage: 72% over overlay/kernel including tests; **not production-only coverage**. Server 79%, router 91%, store 84%. Full repository collection is blocked; do not describe focused green as full green.

## Implemented fixes and regression evidence
1. Integrated previously omitted Wave 10 lint branch (#9), preserving SQLite lifecycle improvements. Fixed import ordering that broke PR #11 CI; broad focused lint now clean. Concurrent remote branch updates were merged, not overwritten.
2. Router now caps completion budgets at 4096 by default, rejects invalid/conflicting budgets before egress, refuses streaming/multiple completions, validates text-choice schema and rejects reported over-budget completions before success/accounting. This is a per-request completion ceiling, **not tenant spend accounting or prompt-token estimation**. Text-only router contract; tool-call payloads are not supported.
3. Benchmark closes HTTP error bodies, validates arguments, reports useful HTTP success separately from transport success, and exits nonzero on latency or availability failure. Workload paths can be specified explicitly. Default legacy workload intentionally remains reproducible and fails on nonexistent `/api/health` plus quota shedding.
4. ASGI shutdown joins extraction workers before closing durable SQLite; repeated lifespans reopen the same store object so consumers retain valid references. Native pytest lifespan fixture stops tests using a dead application. A permanently stuck native parser still requires process isolation/termination-grace handling; joining is not a hard cancellation guarantee.
5. 23 added tests (16 router boundary/property tests, 1 lifecycle regression, 6 benchmark regressions). CI now runs all focused kernel/overlay tests and fatal ResourceWarning/unraisable gates rather than selected 91 tests. Router red baseline: 15 failures/1 pass; lifecycle red: worker remains alive. Remediation: router one cycle, lifecycle two, lint two; no module exceeded five cycles.

## Final local gates
| Gate | Result |
|---|---|
| Focused unit/integration/property suite | **151 passed**, 12.97s; ResourceWarning/unraisable fatal |
| Node overlay suite | **17 passed** |
| Broad overlay/kernel + benchmark Ruff | **Pass** |
| CI E9/F lint | **Pass** |
| SEC-006 live socket adversarial matrix | 400 requests, all expected classifications; P99 93.54ms |
| Undrained stderr | 2000/2000 HTTP 200, 40 threads; final batch P95 49.18/P99 50.56ms; shutdown 0.164s; 1715 logs shed |
| Resource stability | stderr workload RSS +6 MiB after warmup; short window only, no bounded long-soak proof |
| Production SLO gate | **FAIL / NO-GO** |

## Before → after, identical legacy workload (2000 requests / 100 threads)
| Metric | Before c1fbe27 | After lifecycle/router/harness fixes |
|---|---:|---:|
| P50 ms | 103.18 | 99.63 |
| P95 ms | 136.43 | 153.20 |
| P99 ms | 167.48 | 167.08 |
| RPS | 1088.1 | 1099.4 |
| RSS start/end MiB | 78.3 / 100.3 | 78.2 / 100.2 |
| HTTP 2xx | 1350 / 2000 | 1350 / 2000 |
| Request success ratio | 67.5% | 67.5% |
| Transport errors | 0 | 0 |
| SIGTERM seconds | 0.164 | 0.164 |
| Harness exit | 0 (false green) | 1 (correct rejection) |

Final HTTP codes: 1350×200, 149×404, 500×429, 1×503. Do not present these as useful-service availability. Valid-path diagnostic also failed (75% 2xx, P95 153.78ms). Mixed demo/security script: P95 970.54ms, P99 996.68ms, 170.94 RPS; its expected-negative traffic must not count as a useful-work availability benchmark. Short samples are noisy, and the before/after delta is not a demonstrated performance improvement.

## Live Melious smoke
Four catalog-confirmed IDs were called once each with max_tokens=20, timeout=8s, retries=0. All returned schema-valid completions: GLM-5.3 0.511s; GLM-5.3 Flash 0.950s; Kimi K3 1.201s; Qwen 3.8 27B 0.670s. Exact IDs and usage: `evidence/v1-prod-review/live-models.json`. Three responses used the full token cap (including reasoning); this is connectivity/schema/budget smoke, not semantic output quality or API latency SLO certification. Fault tests cover 429 bounded retry, timeout/dropout, malformed usage, malformed choices, breaker open/half-open, lock saturation, and out-of-order accounting using deterministic transport injection.

## Release blockers
- **P0 SECRET-ROTATION:** user-provided chat/certification contain credentials. Revoke/replace both keys. Tracked-tree pattern scan found one deliberate dummy fixture, no real matching credential; this does not certify all formats/history or remove exposure from the original documents.
- **P0 SLO:** no defined baseline offered RPS, representative authenticated request mix, or 100x soak; P95 fails. 99.99% uptime cannot be inferred from shutdown latency. Need admitted-success and overload metrics separately, plus client-observed latency without coordinated omission.
- **P0 E2E:** overlay forces gateway test mode, router is not wired into application inference; do not silently switch to billable inference. Establish intended product/API contract and wire/test it explicitly.
- **P1 BUILD:** 41 full collection errors, missing optional/document dependencies and missing packs.wedge; exact lock/build not established. Rust/Tauri final-SHA CI must pass.
- **P1 TELEMETRY:** request IDs/JSON logs/probes exist, but unified OTel ingress→worker→model exporter is not verified/implemented here. Current queue sink is stderr, not promised stdout. Production auth/probe topology and multiworker quotas need deployment verification.
- **P1 LIFECYCLE:** worker joining is now tested; unkillable native parser isolation, concurrent SQLite operations, and long-run memory ceilings remain unproven.

## Safe deployment and rollback runbook (blocked until gates pass)
1. Rotate credentials using the secret manager. Runtime receives MELIOUS_API_KEY only; GIT_AUTH_TOKEN belongs in the release job, not the serving pod. Configure actual AXIOM auth keyring and default-deny allowed origins/proxy trust. Never put secrets in shell history, git, PRs, or images.
2. Pin and lock dependencies for declared Python/Rust/Node versions; build immutable image from reviewed SHA. Re-run focused tests, full product collection/tests/fuzz, lint, dependency/secret scans, locked Rust/Tauri builds, and functional real-model E2E.
3. Define baseline RPS and request mix, payload distributions, dataset, tenant/auth topology, worker count, hardware and memory cap. Run a fixed offered-rate 100x workload with latency/error thresholds, fault phases, leak monitoring and sufficient soak; keep overload rejection visible. Require P95≤120ms, P99≤250ms, useful-service availability≥99.99%. Do not disable auth or remove expensive endpoints to make a gate green.
4. Snapshot SQLite with its backup API and test restoration; retain immutable last-known-good image digest/config. Set termination grace longer than bounded work deadlines. Do not assume two workers fixes quotas or storage concurrency.
5. Canary 5%, monitor `/livez`, `/readyz`, authenticated `/metrics?format=prometheus`, useful-success ratio, per-route latency, queue sheds, log drops, RSS, FD/thread counts, and traces. Observe at least 30 minutes after load/chaos gates; ramp only with explicit release approval.
6. On regressions stop ramp, drain traffic, restore previously validated image/config digest. `kubectl rollout undo deployment/axiom-grid-overlay` is only appropriate if this deployment actually exists and its prior revision is the validated artifact. Preserve the database; **never delete overlay_store.db as a rollback shortcut**. Restore a tested backup only for verified corruption/migration failure and account for intervening writes. Verify readiness and business operations after rollback.

## Reproduction (from repository root)
```sh
python3 -m pytest overlay/tests kernel/tests -q -W error::ResourceWarning -W error::pytest.PytestUnraisableExceptionWarning
python3 -m ruff check overlay kernel scripts/bench_v1_prod.py
node --test phantom-overlay/tests/app.test.cjs
python3 scripts/stress_sec006_gauntlet.py
python3 scripts/stress_wave11.py
python3 scripts/bench_v1_prod.py 2000 100  # EXPECTED FAIL: must block release
```

**Decision: checkpoint hardening, do not certify production or merge a production release while these blockers remain.** Older overlapping PRs may be closed only after their exact heads are proven contained in this branch; their fixes remain preserved in #11.
