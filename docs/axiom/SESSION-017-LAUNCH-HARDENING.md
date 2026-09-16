# Session 17 — Launch hardening (AG-07, AG-08, AG-09) and live gateway torture

**Date:** 16 September 2026 · **Base:** `94caf70` (main after PR #22) · **Decision:** conditional GO for 17 Sept remains; see gates.

## Council verdict (SF Founder · Principal Architect · Red Team Lead)

Three open P0s were code-fixable today and are fixed from first principles (no sleeps, no mocks, no cosmetic patches):

| Blocker | Failure mode | Foundational fix | Evidence |
|---|---|---|---|
| AG-09 Readiness | `/readyz` cached one synthetic success forever; a pod stayed in rotation after parser/state failure | Bounded TTL revalidation (`AXIOM_READYZ_TTL_SECONDS`, default 30 s), dependency checks (pdfplumber, python-docx, state dir writable, extraction capacity), single-flight lock, automatic recovery, `_readyz_probe_ok` kept as master invalidation switch | `test_readyz_revalidates_after_ttl_and_recovers`, `test_readyz_single_flight_under_probe_stampede` (64 concurrent probes → 1 pipeline run) |
| AG-07 Resource containment | 2 MiB HTTP cap bounded *compressed* bytes only; a tiny DOCX/PDF could inflate to GBs or 100k pages; a hung parse held the client forever | Expanded-side budgets in the ingestor: `AXIOM_MAX_PDF_PAGES`=200, `AXIOM_MAX_EXTRACTED_CHARS`=4 MiB, `AXIOM_MAX_DOCX_EXPANDED_BYTES`=64 MiB, `AXIOM_MAX_DOCX_ENTRIES`=2048 — zip bombs rejected from the central directory *before any inflation*; `ResourceBudgetExceeded` → HTTP 422. Wall-clock `AXIOM_EXTRACTION_DEADLINE_SECONDS`=30 → honest 504 + `Retry-After`; slot released exactly once by the worker | `test_docx_declared_decompression_bomb_rejected_before_parse`, `test_pdf_page_flood_rejected`, `test_extraction_deadline_returns_504_and_releases_slot` |
| AG-08 Billing | `SpendGovernor` process-local; N replicas each admitted against local state; retries could double-count | `DurableSpendLedger` (SQLite WAL, `BEGIN IMMEDIATE`): one aggregate across replicas sharing `MELIOUS_SPEND_LEDGER`, idempotent `attempt_id`, overshoot never clamped, `reconcile()` charges (never forgives) stale reservations from crashed replicas | 4 ledgers × 64 concurrent reservations never exceed ceiling; live burst committed == provider-billed tokens |

**Honest limits.** The deadline stops the *waiter*, not the Python thread (a killable subprocess worker is the next step). The durable ledger is shared per volume/host — pair it with the provider-side hard budget; it is still not a monetary cap. AG-01 (credential rotation), AG-06 (tenant isolation), AG-11/12/17/18/19 are founder/operator gates that code cannot close.

## Live Melious gateway torture (production key, 16 Sept)

| Model | Result | Latency ms | Total tokens | Reply |
|---|---|---|---|---|
| glm-5.3 | OK | 780 | 85 | 'AXIOM-' |
| glm-5.3-flash | OK | 35411 | 32 | 'AXIOM-OK' |
| kimi-k3 | OK | 1816 | 180 | 'AXIOM-OK' |
| qwen3.8-27b | OK | 1329 | 63 | 'AXIOM-OK' |

* 24-way concurrent burst through the full fallback chain with the durable ledger: **22/24 OK** in 2.58 s, p50 2178 ms, p95 2528 ms; 2 `BudgetExhaustedError` (16-token budget eaten by reasoning tokens — correct fail-fast, **no fallback spend multiplication**, fallbacks=0). Ledger `spend_committed`=777 == router `total_tokens`=777 → exact reconciliation.
* Dead upstream (connection refused): all breakers OPEN after threshold; subsequent call fails fast in **0.07 ms** (gate: < 200 ms).

### Red-team finding RT-17-1 (P1, open)
GLM-5.3 Flash answered a 64-token prompt in **35411 ms** — above the router default `total_timeout=30 s`. In production this route would time out and cascade. Action: order the chain by measured p95, set per-model `timeout`, and alert on provider p95 > 10 s. GLM-5.3 also truncated at 64 tokens because hidden reasoning tokens consume `max_tokens`; callers must budget ≥ 256 tokens for reasoning models.

## Validation on this SHA
* `pytest overlay/tests kernel/tests tests/test_concurrency_safety.py -W error::ResourceWarning -W error::pytest.PytestUnraisableExceptionWarning` → **258 passed** (247 baseline + 11 new).
* `ruff check` on all changed files → clean. `stress_wave11.py`, `eval_wedge.py` (F1 0.996), `eval_adversarial.py` (F1 0.977), `stress_sec006_gauntlet.py`, `stress_test.py` → all PASS.

## Go/No-Go for 17 September
GO only if by T-24h: exposed GitHub PAT and Melious key are **revoked and rotated** (they appear in task history — treat as compromised), `MELIOUS_SPEND_LEDGER` is mounted on a shared volume with a provider-side budget, and a staging roll-in (≥ 8 replicas, `/readyz`-gated) plus rollback drill is recorded. Otherwise ship 17 Sept as a capped design-partner cohort, not a public launch.
