# Axiom-Grid — Session 16: final-head CI certification + pre-push gate

**Verified September 15, 2026 · target launch September 16–17 · PR #20, branch `harden/axiom-grid-prod`**

## 1. Final-head CI certification (Session 15 next-step #1) — CLOSED

Checks API on the current PR head `d94b585`:

| Check | Status |
|---|---|
| focused-runtime | success |
| focused-overlay | success |
| overlay-container | success |
| legacy-resource-lifecycle | success |
| GitGuardian Security Checks | success |

5/5 green on the exact head. The Session 14/15 `focused-runtime` lint failure (PLR1730) is confirmed resolved on the certified head.

## 2. Root cause of the escaped lint failure — fixed at the process level

The local gate ran pytest but never ruff, so a lint-only regression could only be discovered by CI, one push late. Fixed by making lint and tests one gate:

- `ci/pre-push.sh` — runs the broad `ruff --select E9,F` gate, the exact CI changed-file ruff set, the focused `overlay/tests kernel/tests` suites under `-W error::ResourceWarning -W error::pytest.PytestUnraisableExceptionWarning`, and `py_compile scripts/axiom-live-e2e.py`. It refuses to run outside the repository root, because ruff first-party detection is cwd-dependent (the cause of the spurious I001 reported in Session 15).
- `make lint` / `make pre-push` targets wired to the same commands.

Local result: `PRE-PUSH GATE: PASS`, exit 0 — ruff both gates clean, **237 passed in 11.94 s**, runner syntax clean.

## 3. Live model gateway verification — 4/4 routes, up from 2/4

Real gateway, real `MeliousModelRouter`, one call per configured route, `max_tokens=64`, `max_retries=0`, process-local ceiling 512 tokens per router. Catalog `GET /v1/models` confirms every id in `DEFAULT_MODELS` is live (a dead id silently shortens the fallback chain).

| Route | Outcome | Latency | Ledger committed | Reserved after settle |
|---|---|---:|---:|---:|
| GLM-5.3 | success, visible completion | 0.592 s | 30 | 0 |
| GLM-5.3 Flash | success, visible completion | 1.227 s | 79 | 0 |
| Kimi K3 | success | 1.424 s | 163 | 0 |
| Qwen 27B | success | 0.832 s | 42 | 0 |

314 tokens accounted, zero reservations leaked, zero spend refusals. Session 14 reasoning-budget exhaustion on the two GLM routes did not reproduce. Note: reasoning tokens dominate short completions (57/59 and 64/64 on Flash and K3), so any latency or cost model must budget reasoning tokens explicitly.

## 4. Remaining open blockers (unchanged, still gating merge)

1. **Useful ingress capacity — OPEN.** `/demo` funnels the whole pipeline through one global `orchestrator_lock` (overlay/server.py) protecting shared SQLite/provenance state, behind a 4-worker pool and a 20-slot admission semaphore. At 100 clients this sheds ~80–91% as designed backpressure; the fix is stage isolation (parse concurrent, store commit serialized per-connection) plus process-level replicas, not deeper queues. Not attempted this session: it is a multi-session refactor and must be benchmarked on useful throughput, not request count.
2. **Dependency / release drift — OPEN.** Python 3.14 wheel gaps (embed-anything, ONNX), parquet engine, faster-whisper, fitz licence, LibreOffice; whole-repository suite therefore not 100% green.
3. **Observability topology — UNVERIFIED.** JSON logs, OTel tracing, `/healthz` `/readyz` `/livez` and Prometheus exist and pass locally and in the container gate; collector ingestion, alert rules and a multi-replica soak have no staging environment here.

## 5. Release decision: NO-GO for auto-merge

Every gate that exists in CI is green on the certified head and the router/spend work is complete, but the Definition of Done (100% green unit/integration/E2E **and** zero shed at 100x offered load) is not met while blockers 1–2 are open. Merging would satisfy the checkbox and violate the guardrail. PR #20 is therefore taken out of draft (code gates green, ready for human review) and left unmerged, with the two blockers escalated.

No module exceeded the five-cycle convergence limit; this session used one cycle (process/lint gate).

**Security:** rotate `GIT_AUTH_TOKEN` and `MELIOUS_API_KEY` — both were pasted into the task prompt. Neither was written to any file, commit or PR body; the git remote carries no credentials.
