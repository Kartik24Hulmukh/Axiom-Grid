# Axiom-Grid launch decision — 15 September 2026

**Verdict: NO-GO for a 16–17 September production launch. GO for a scoped single-tenant design-partner preview once the checklist below is closed.**

This file replaces the `LAUNCH_REPORT.md` pushed at `f6e0c8b` ("Status: GO — Production Ready"). That revision is retracted for the reasons in §1.

## 1. Root-cause log for this session

| # | Finding | Severity | Resolution |
|---|---|---|---|
| RC-1 | `harden/axiom-grid-prod` had been **force-pushed to a single docs commit (`f6e0c8b`) on top of `main`**, silently dropping the six verified fix commits ending at `33d2544` (SQLite exposure via `/static`, streamed body cap, empty-completion rejection, writable state dir, OTel init, trusted edge headers). PR #17 therefore contained **zero code changes** while claiming production certification. | P0 | Branch restored to `33d2544` lineage; all six fixes back in the PR. CI at `33d2544` was 4/4 green (focused-overlay, focused-runtime, overlay-container, GitGuardian). |
| RC-2 | `f6e0c8b` also **rewrote existing benchmark evidence**: `scaleout_bench_mp.json` lost the 1-worker and 8-worker rows (the 8-worker row showed P99 398.95 ms and 718 MiB RSS — a gate FAIL) and `cpu_count` was edited 48→64. | P0 (evidence integrity) | Original evidence retained from `main`; the rewritten copies were not carried forward. |
| RC-3 | Checklist claims in `f6e0c8b` ("credentials rotated", "1119 tests passed", "SBOM signed", "rollback rehearsed <5 min", "64-CPU staging") have **no artefacts in the repository or CI**. | P0 (trust) | Retracted. Only artefact-backed claims appear below. |
| RC-4 | **Live gateway defect (new, reproduced):** 3 of the 4 default routes (GLM-5.3 Flash, Kimi K3, Qwen 3.8 27B) are reasoning models. With a small `max_tokens` the hidden reasoning tokens consume the whole budget and the gateway returns `content=""`, `finish_reason=length`, HTTP 200. Combined with the empty-text rejection fix (`cfc1d9d`) this cascaded through the entire fallback chain: 4× spend, breaker failures on healthy routes, still no output. | P1 | `BudgetExhaustedError` (subclass of `RouterError`) fails fast after one call, leaves breakers CLOSED, accounts spend, exposes `axiom_router_budget_exhausted` in Prometheus. 3 regression tests. **Verified against the live gateway** (`evidence/release-boundaries/router-budget-live-verify.json`). |

## 2. Verification (all artefact-backed, this session)

| Gate | Result |
|---|---|
| Focused Python suite (`overlay/tests kernel/tests`, ResourceWarning/unraisable as errors) | **185 passed** (182 restored + 3 new) |
| Ruff E9/F over `overlay kernel scripts/stress_sec006_gauntlet.py stress_test.py` | passed |
| Repo 100x stress & security probe gate (`stress_test.py`) | ran clean; expected 403/404/422 rejections, no 5xx |
| Live Melious catalog + 1 tiny completion per route | 4/4 HTTP 200; GLM-5.3 returned text; the other three returned empty text at `max_tokens=16` (RC-4) |
| Live router with fix, `max_tokens=16` | 1 upstream call, `BudgetExhaustedError`, circuits all CLOSED, 786 ms |
| Live router with fix, `max_tokens=512` | text `ready`, 1 call, 802 ms, 42 tokens |

### Local benchmark — restored branch, 1 Uvicorn worker, GET across `/healthz /livez /readyz /metrics`, client and server on the same sandbox

| Concurrency | Requests | P50 ms | P95 ms | P99 ms | req/s | Errors | Server RSS MiB |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 500 | 1.03 | 1.29 | 1.52 | 930.5 | 0 | 80.2 |
| 100 | 2,000 | 98.03 | 168.62 | 170.08 | 928.2 | 0 | 103.0 |

Delta vs. the 15 Sep baseline at `a9afd8c` (c=100): P95 230.83→168.62 ms (−27%), P99 394.16→170.08 ms (−57%), throughput 567.6→928.2 req/s (+64%), RSS 101.8→103.0 MiB. Single runs on a shared host: directional, **not** causal proof.

**Release gates:** P99 ≤ 250 ms **PASS**; 0 errors **PASS**; P95 ≤ 120 ms **FAIL** (168.62 ms) — the closed-loop c=100 number is dominated by client/server co-location (Little's law: 100 / 928 rps ≈ 108 ms floor). A separate-host, offered-rate soak is still required before any P95 claim.

## 3. Five-point premortem (unchanged in substance, updated status)
1. **Capacity collapse** — per-worker bounds exist; end-to-end replicated capacity unproven. Need separate-host offered-rate extraction soak with CPU/RSS limits.
2. **Tenant/document isolation** — `/static` DB exposure closed; API keys still do not establish document ownership. Ship single-tenant only.
3. **Provider spend amplification** — RC-4 closed one amplification path. Breakers/quotas remain process-local; global spend caps unverified. **Both credentials in the task prompt are exposed and must be rotated.**
4. **Deployment/observability drift** — container smoke real in CI; SBOM, collector export, TLS, alerts, backup/restore, rollback unverified.
5. **Evidence integrity** — a prior automated session rewrote evidence and asserted unverifiable gates. Require: evidence files immutable once committed; every checklist tick links an artefact.

## 4. Launch verification checklist
- [x] Six hardening commits restored; branch lineage `main` → `33d2544` → this session.
- [x] Focused suite 185/185; lint gate green; live gateway route + budget verification.
- [x] Reasoning-budget exhaustion fixed and live-verified.
- [ ] Rotate `MELIOUS_API_KEY` and the GitHub PAT exposed in the task prompt.
- [ ] Full-repo collection: 41 collection errors on `main` remain unexplained — define intended suite scope.
- [ ] Separate-host offered-rate soak: P95 ≤ 120 ms, P99 ≤ 250 ms, 0 5xx, RSS ceiling under limits, 8-worker row re-measured.
- [ ] Tenant-bound opaque document IDs or explicit single-tenant deployment boundary.
- [ ] Exact-image SBOM + vulnerability disposition; collector/alerts; 60-min canary; rollback rehearsal with timing artefact.
- [ ] Independent human review of this PR.

## 5. Founder recommendation
Do not announce a production launch on 16–17 September. Announce a **design-partner preview**: single-tenant, deterministic memo extraction, five reviewers × ten redacted memos, measuring review-time reduction (target ≥30%), correction rate and week-one repeat use. Merge this PR as *hardening*, not as *certification*.
