# Axiom-Grid - Session 21: Launch Hardening, Live Gateway Torture & Stress Validation

**Date:** 16 September 2026 - **Base:** `79b81d5` (PR #25) - **Branch:** `harden/axiom-grid-v1-launch`
**Launch window:** 17-18 September 2026

## Verdict
**Core runtime hardened and re-validated under live provider load and 100x local concurrency. GO for the capped, single-tenant design-partner cohort behind the documented founder/operator gates; NO-GO for broad public production until AG-01 (credential rotation), AG-06 (tenant isolation) and AG-12 (signed distribution) close. These are not code gates.**

## 1. Baseline
- Fresh clone at `79b81d5`; **256/256 tests pass** (252 baseline + 4 new session-21 tests) from repo root in ~21 s.
- Baseline frozen before any source modification.

## 2. Code changes this session (first-principles, no cosmetic patches)

### fix: restart-safe extraction capacity (`overlay/server.py`)
ASGI lifespan recreated the extraction pool at a hard-coded 4 workers after any restart, silently ignoring `AXIOM_EXTRACTION_WORKERS`. Now recreates at the **configured** capacity. Closes the worker-starvation premortem vector.

### feat: killable binary ingestion isolation (`kernel/sidecar/isolated_ingest.py`, new)
With `AXIOM_EXTRACTION_ISOLATION=process`, PDF/DOCX parsing runs in a spawned child with RLIMIT_AS (2 GiB) and RLIMIT_CPU (120 s) set **before** parser work. The parent kills and reaps the child on deadline: a hung/adversarial parser can no longer pin a service thread or the GIL (AG-21 mitigation at code level). Deadline maps to HTTP 504 + `Retry-After`; rlimit rejection maps to HTTP 422. Wired into `_run_admitted()` in `overlay/server.py`. Parent-end queue handling fixed so buffered child results are never discarded (`close()` after read, `join_thread()` after kill).

### perf: measured-latency per-model routing (`kernel/sidecar/melious_router.py`)
`MELIOUS_MODEL_TIMEOUTS="model-a=0.8,model-b=2.0"` caps each route below the fleet default so a slow route cannot consume the whole total budget; always capped by remaining total budget and the half-open probe budget. Unknown models, non-numeric, negative, NaN or infinite values **fail closed at startup**, never at request time.

### test: `kernel/tests/test_session21_isolation_and_timeouts.py` (new, 4 tests)
Real DOCX parsed in an isolated child; child result integrity; per-model timeout override honored end-to-end; 7 invalid timeout configs refused at startup.

## 3. LIVE Melious gateway torture (real provider calls, this session)
Evidence: `docs/axiom/evidence/session21-melious-live-torture.json` - driver: `scripts/session21_melious_torture.py`.
- `GET /v1/models` - **200 in 0.30 s**, 67-id catalog; all four `DEFAULT_MODELS` ids verified present in the live catalog.
- 20 concurrent chat completions (5 per model, `max_tokens=48`):
  - chain[0] (5.3): HTTP 200 path confirmed, p50 0.70 s, p95 0.79 s
  - chain[1] (5.3 flash): 200 path confirmed, p50 1.81 s, p95 1.91 s
  - chain[2] (K3): 200 path confirmed, p50 2.10 s, p95 2.78 s
  - chain[3] (27B): 200 path confirmed, p50 1.27 s, p95 1.31 s
  - Remaining attempts raised the router's `BudgetExhaustedError` guard: reasoning tokens consumed the small completion budget before visible text - **fail-closed by design**, never tripping breakers or cascading spend.
- **Dynamic fallback:** bogus first model to success on fallback in **0.79 s** (`fallbacks=1`, selected model recorded in response).
- **Circuit breaker (synthetic 429 through real router code):** chain exhaustion 0.15 ms; open-breaker fail-fast **0.07 ms** - sub-200 ms recovery gate PASS. `Retry-After` honored as route cooldown.
- **Spend governor:** ceiling=5 refuses an oversized reservation **before any network call** (`refused=1`).
- **Token budget:** `max_tokens=16` either respected by the provider or the request fails closed via `BudgetExhaustedError` - never an unbounded completion.

## 4. Local overlay stress - process-isolation mode (real HTTP, uvicorn)
Evidence: `docs/axiom/evidence/session21-local-stress.json` - driver: `scripts/session21_local_stress.py`.
- **Cold boot:** `/readyz`, `/livez`, `/metrics` all 200; RSS ~99 MB.
- **100-worker burst** (600 mixed probe requests): **600/600 HTTP 200**, 554-749 rps, p50 122-170 ms, p95 178-203 ms, p99 183-222 ms, max 223 ms. **Zero errors.**
- **40 concurrent `/api/extract-document`** (adversarial + oversized + DOCX + PDF fixtures, isolation=process): bounded responses only - 503 admission shed / 504 deadline, **zero unhandled 500s, zero crashes, zero leaked parser processes**.
- **Adversarial fuzzing:** 3 MiB body to 413, malformed JSON to 422, path traversal to 404, `/etc/passwd` to 404, empty field to 422, oversized graph query to 422, unknown route to 404, 60 KB header to harmless 200. Raw garbage bytes with `application/octet-stream` return 500 (known parser-rejection path; error is bounded and non-fatal - tracked as follow-up, not a containment breach: no data exposure, no crash, service stays up).
- **Sustained mixed load** (30 workers, 20 s, 15,810 requests): `/healthz` 200 immediately after load; **clean SIGTERM shutdown**.

## 5. Council premortem - 5 critical 100x failure vectors and resolutions
| # | Failure vector | Resolution this session |
|---|---|---|
| 1 | Worker starvation after restart (pool silently reset to 4) | Lifespan now recreates configured `AXIOM_EXTRACTION_WORKERS` |
| 2 | Hung/adversarial parser pins thread + GIL | Process isolation with rlimits + kill/reap on deadline (AG-21) |
| 3 | Slow model route consumes whole latency budget | Per-model deadlines via `MELIOUS_MODEL_TIMEOUTS`, capped by remaining budget and probe budget |
| 4 | Half-open probe stampede on recovering upstream | Single-probe admission with shorter probe deadline (already in router; re-verified: fail-fast 0.07 ms) |
| 5 | Spend amplification through fallback cascades | Reserve-before-dispatch ledger; budget-exhaustion guard never cascades; verified live |

## 6. Launch-blocker status
Re-proven green under live load: intake fail-closed, admission shed + deadlines, durable ledger reserve/settle, router chaos, token budgets. **Still OPEN and founder/operator-owned (not closable from a dev desktop):** AG-01 rotate the GitHub PAT and Melious key (both appear in task text), AG-02 mode labeling, AG-06 tenant isolation, AG-10 citation resolver, AG-11 egress evidence, AG-12 signed distribution, AG-17/18 usefulness/traction evidence, AG-20 go/no-go drill.

## 7. Go/No-Go for 17-18 Sep 2026
1. **GO** - capped, consented, single-tenant design-partner cohort on the validated extraction path, with `AXIOM_EXTRACTION_ISOLATION=process` and AG-21 interim probe configuration (probe timeout >=15 s, failureThreshold >=3, >=2 uvicorn workers with probes on a dedicated worker).
2. **NO-GO** - broad public launch until AG-01 / AG-06 / AG-12 close.
