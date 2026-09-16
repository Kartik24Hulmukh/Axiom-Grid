# Axiom-Grid — Session 20: Real-Human Stress Validation & Launch Evidence

**Date:** 16 September 2026 · **Head:** b336790 (PR #24) · **Launch window:** 17–18 Sep 2026

## Verdict
**Core runtime validated under real load. GO for capped design-partner cohort behind the documented gates; NO-GO for broad public production until AG-01/02/06/10/11/12 close (founder/operator gates, not code gates).**

## 1. Baseline
- Fresh clone at b336790; 252/252 focused tests pass (overlay + kernel suites) from repo root.
- Two apparent failures when run from outside repo root are CWD artifacts only.

## 2. Live Melious gateway torture (REAL provider, this session)
- `GET /v1/models` 200 in 0.36s; all four default-chain ids present in catalog.
- 20 concurrent chat completions across GLM-5.3 / GLM-5.3-Flash / Kimi-K3 / Qwen-27B: glm-5.3 5/5 200 (p95 1.12s), flash 5/5 200 (p95 1.56s), kimi-k3 5/5 200 (p95 1.90s). Token budget (max_tokens=16) respected on every 200.
- Task-literal id `qwen-3.8-27b` is NOT in the catalog (404); the router DEFAULT_MODELS 4th id IS valid and completed live — chain is correct as shipped.
- Live dynamic fallback: bogus first model → success via fallback in 838ms, metrics fallbacks=1.
- Synthetic 429 chaos through real router: failover 0.07ms (<200ms gate PASS); open-breaker skip 0.02ms; Retry-After honored.
- Spend governor: ceiling=5 refuses oversized reservation before any network call. Evidence: `evidence/session20-melious-live-torture.json`.

## 3. Local overlay server stress (uvicorn, single worker)
Evidence: `evidence/session20-local-stress.json`.
- Cold boot: /readyz 200 in 65ms, /livez 6ms, /metrics 6ms.
- 100-worker burst, 600 mixed probe requests: 600/600 HTTP 200, 543 rps, p50 122ms, p95 318ms, p99 331ms, max 388ms. Zero errors.
- 40 concurrent /api/extract-document (adversarial fixtures incl. oversized_input): 11×200, 29×504 (server-side deadline — bounded, fail-closed, no 500s, no crash). p95 70.5s tail.
- Adversarial fuzz: 3MiB body→413, malformed JSON→422, path traversal→404, /etc/passwd→404, empty field→422, oversized graph query→422, garbage bytes→400, unknown route→404. Zero fail-open results.
- Sustained mixed load 30 workers/20s: RSS +56MB (bounded), /healthz recovered 200 after load, clean SIGTERM shutdown.

## 4. New premortem finding (AG-21) + first-principles remediation
**AG-21 (P1): probe starvation under saturated CPU-bound extraction.** During the 40-concurrent extraction burst, /healthz on the same single-worker process exceeded 10s (observed live via curl). Admitted extraction threads hold the GIL through pdfplumber/classifier hot paths and starve the asyncio accept loop.
- Requests are still bounded (504 deadline) and the process fully recovers — no death spiral — but a naive readiness-aware LB would flap the pod under load.
- 100x fix (deployment, no code change needed for cohort): run ≥2 uvicorn workers and route probes to a dedicated worker, or move `_extraction_pool` to a `ProcessPoolExecutor` so extraction cannot hold the GIL (recommended post-cohort refactor).
- Interim gate for cohort launch: probe timeouts ≥15s with failureThreshold ≥3, and shed threshold left at current capacity.

## 5. Launch-blocker delta (from LAUNCH-BLOCKERS-2026-09-16.csv)
- Code-verifiable gates re-proven green this session: AG-03/04/07/09 behavior observed live under load; AG-08 admission side observed (503/504 shed + ledger reserve/settle).
- Still OPEN and founder/operator-owned (cannot be closed from this desktop): AG-01 (rotate the leaked GitHub + Melious credentials — they appear in task text again this session and must be revoked before launch), AG-02, AG-06, AG-10, AG-11, AG-12, AG-17, AG-18, AG-19, AG-20. New: AG-21 (above).

## 6. Go/No-Go for 17–18 Sep 2026
1. GO: capped, single-tenant, consented design-partner cohort on the validated document-extraction path, with probes configured per AG-21 interim gate.
2. NO-GO: broad public launch, until credential rotation (AG-01), tenant isolation (AG-06) and signed distribution (AG-12) are complete.
