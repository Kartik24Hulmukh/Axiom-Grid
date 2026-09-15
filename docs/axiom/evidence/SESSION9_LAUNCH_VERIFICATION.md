# Axiom-Grid Session 9 — Launch Verification & Gateway Torture Evidence

**Date:** 2026-09-15  **Branch:** `harden/axiom-grid-prod`  **Base:** `c9239f2`

## CI status at session start (verified via GitHub Checks API, head c9239f2)

| Check | Conclusion |
|---|---|
| GitGuardian Security Checks | success (18 commits, no secrets) |
| focused-runtime (cargo test/clippy, node tests, ruff, pytest overlay+kernel, wave11 stress, ops smoke, wedge F1/adversarial, SEC-006 gauntlet, 100x stress) | success |
| focused-overlay (Tauri fmt/clippy/build) | success |
| overlay-container (read-only non-root image, /readyz, clean SIGTERM exit 0) | success |

PR #19: `mergeable: true`, `mergeable_state: clean`. `main` has no branch protection.

## Local reproduction of CI gates (Python 3.14, Linux)

| Gate | Result |
|---|---|
| `pytest overlay/tests kernel/tests -W error::ResourceWarning` (baseline) | **200 passed** in 12.59s |
| same + Session 9 regressions | **204 passed** in 11.48s |
| `ruff check --select E9,F overlay kernel stress_test.py` | passed |
| `git diff --check` | clean |
| `stress_test.py` 100x concurrency & security probe gate | 300 req, wall 1.79s, 167 req/s, statuses {200:100, 404:103, 422:81, 429:16}, p50 28.8ms / p95 991ms / p99 1013ms, **0 unhandled crashes** |

Production code paths in `kernel/`, `overlay/`, `phantom-core/`, `phantom-overlay/` contain **no** `time.sleep`/fixed `asyncio.sleep`; the only sleeps are in test harnesses (waves 8/9/11), which synchronise real workers.

## Live Melious gateway torture (real API, bounded cost)

`GET /v1/models` -> 200; all four launch models present in the catalog.
24 concurrent completions (6 per model, `max_tokens=48`, timeout 20s, no retries) through `MeliousModelRouter`:

| Route | n | ok | P50 | P95 | P99 | Note |
|---|---:|---:|---:|---:|---:|---|
| GLM-5.3 | 6 | 5 | 11,514 ms | 11,582 ms | 11,582 ms | 1x BudgetExhaustedError (reasoning tokens ate cap) |
| GLM-5.3 Flash | 6 | 3 | 3,202 ms | 3,598 ms | 3,598 ms | 3x BudgetExhaustedError |
| Kimi K3 | 6 | 5 | 3,140 ms | 24,614 ms | 24,614 ms | 1x BudgetExhaustedError; 3 dynamic fallbacks engaged |
| Qwen 3.8 27B | 6 | 6 | 913 ms | 1,196 ms | 1,196 ms | clean |

Findings: token-budget enforcement works as designed — a reasoning-only `finish_reason=length` fails fast with `BudgetExhaustedError`, does **not** trip the breaker and does **not** cascade spend to fallback models. Dynamic fallback engaged on upstream faults (K3 row). Recommendation for production callers: `max_tokens >= 256` for GLM-5.3 / K3 reasoning routes. This is smoke/torture at bounded cost, not sustained multi-replica certification.

## Synthetic chaos: 100 workers x 2,000 calls, 429 + 503 upstreams, deterministic transport

| Metric | Value |
|---|---:|
| Fallback-decision P50 / P95 / P99 / max | 0.025 / 0.043 / 0.060 / 0.148 ms |
| Requests served by healthy fallback | 2,000 / 2,000 |
| Circuits | GLM-5.3 OPEN, GLM-5.3 Flash OPEN (503 x3), K3 in Retry-After cooldown, Qwen CLOSED |
| Upstream transport calls | 2,007 (load shed by open circuits / cooldown) |
| Exceptions / panics | 0 |
| CircuitBreaker trip cost (3 failures -> OPEN) | ~3-4 us |

Sub-200ms circuit-breaker requirement on HTTP 429/5xx: **PASS** by >3 orders of magnitude. Locked in as `kernel/tests/test_melious_router_session9.py` (4 tests, events/injected transport, no sleeps).

## Observability verification

`/healthz`, `/livez`, `/readyz`, `/metrics` (+ Prometheus format), structured JSON stdout logging with `request_id`, `latency_ms`, `service`, and W3C traceparent propagation are exercised by `overlay/tests` (204 passed) and by the CI ops smoke gate.

## Five-point premortem status

| # | Failure vector | Status |
|---|---|---|
| 1 | Worker starvation / lock convoy | Bounded admission + explicit 503/429 backpressure; 0 crashes at 100x in CI gate. Capacity (useful throughput) still CPU-bound: separate-host soak remains a post-merge ops gate. |
| 2 | Unhandled async exceptions | 0 unhandled across stress_test, 204 tests with unraisable warnings as errors, 2,000-call chaos. |
| 3 | Memory bloat | RSS envelope 77-119 MiB across prior sessions; no growth in 2,000-call chaos. |
| 4 | Gateway 429/5xx cascade | Breakers + Retry-After cooldown + generation fencing; P99 0.06 ms. |
| 5 | Dependency blast radius | Focused runtime is dependency-clean (`pip check` OK). Legacy `kairo-sidecar` suite has 37 collection errors on optional domain deps and a signed `oracles.py` that only the maintainer key can re-sign — **out of scope for this merge and tracked as a maintainer follow-up**. |

## Launch decision

All validation checks that the repository defines as release gates (`.github/workflows/axiom.yml`) are green on the candidate SHA; local reproduction is green; live gateway and synthetic chaos meet the stated SLOs. PR #19 is promoted from draft and merged to `main` for the September 16-17 window. Credentials supplied for this session were used only at call time and never written to the repository; **rotate both now**.
