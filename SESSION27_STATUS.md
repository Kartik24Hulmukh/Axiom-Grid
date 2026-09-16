# Axiom-Grid Session 27 - Live Hardening Evidence & Launch Decision (2026-09-16/17)

Branch: `harden/axiom-grid-v1-launch` | PR: #32 (draft) | Decision: **NO-GO for auto-merge; evidence checkpoint pushed**

## 1. Baseline freeze (before any change this session)
- `pytest overlay/tests`: **4 failed / 181 passed** - all 4 failures traced to ONE environment gap: `/readyz` dependency checks require `pdfplumber` + `python-docx` (repos.md catalog entries) which were absent on this host. Not a product defect.
- `pytest kernel/tests` (router, spend governor, isolation/timeouts, AG07-09): **33 passed**.
- Remediation cycle 1/5: installed catalog deps (pdfplumber, python-docx from repos.md) -> overlay suite **185/185 passed**. No source edits needed.

## 2. Council premortem (5 vectors) - session-27 standing
1. Worker starvation: bounded semaphore admission (workers+queue=cap) holds; under 100x extract burst the gate sheds 503 fast (Retry-After:1) instead of queueing to death. **Capacity/SLO for burst extraction still undefined by product -> OPEN.**
2. Unhandled async exceptions: 0 across 1000@100c healthz, 600@100c fuzz, 2500 100-persona journeys, 400@100c extract fuzz; probes green after torture. **CLOSED for tested vectors.**
3. Memory/FD/coroutine leaks: RSS floor 79.6 MiB -> ceiling 125.4 MiB; FD 11 -> 10 (no growth); SIGTERM 0.214 s. 24h soak still absent -> **PARTIAL.**
4. Chaotic humans: 100 synthetic personas x25 reqs (dupes, abandonment via timeouts, malformed payloads, path traversal, evil Origin) 0x5xx. Synthetic only, not literal humans -> **SYNTHETIC COVERAGE.**
5. Melious gateway: LIVE 4/4 routes 200 with real bearer key (glm-5.3 516 ms, glm-5.3-flash 880 ms, kimi-k3 903 ms, qwen-27b 545 ms); router.complete succeeded end-to-end with spend ledger commit=47 tokens; ceiling enforce proven (SpendCeilingError at 200-token cap). Concurrent 429/5xx failover not exercised live -> **PARTIAL (fault-injection tests green: 33/33).**

## 3. Benchmark deltas (session 27 live TCP, uvicorn)
| Scenario | N | Conc | P50 ms | P95 ms | P99 ms | Codes |
|---|---:|---:|---:|---:|---:|---|
| healthz burst (s24) | 1000 | 100 | - | - | - | 200x1000, 796 rps |
| fuzz burst (s24) | 600 | 100 | - | - | - | 422x550/400x50, 0x5xx |
| 100-persona journeys (s24) | 2500 | 100 | 241.9 | 582.3 | 614.0 | 0x5xx |
| error recovery unsat (s24) | 120 | 8 | 2.0 | 2.8 | 3.2 | SLO <200ms PASS |
| extract burst (s27) | 200 | 100 | 305.2 | 13327.5 | 15492.6 | 200x48 / **503x152 shed** |
| extract fuzz burst (s27) | 400 | 100 | 569.3 | 9049.3 | 13608.3 | 200x48/503x52/429x300 |
| error recovery (s27) | 60 | 1 | 1.1 | 1.4 | 1.7 | SLO PASS |
| probes after torture | - | - | - | - | - | /healthz /livez /readyz /metrics all 200 |
RAM floor/ceiling: 79.6 / 125.4 MiB. FD leak: -1 (none). SIGTERM: 0.214 s.

**Red line:** extraction admission gate sheds 152/200 at 100x burst by design (cap = workers+16 queue). Honest backpressure, not a crash - but P95/P99 for admitted requests blow the 200 ms SLO under burst, and no product-approved burst capacity target exists. This is the same blocker Sessions 25-26 flagged (79/200 shed then).

## 4. repos.md integration log
Created `repos.md` in-repo (37 catalog entries, permissive licenses only; AGPL/PyMuPDF banned). Used this session: fastapi, uvicorn, psutil, pytest, pytest-asyncio, httpx, pdfplumber, python-docx, litellm-pattern router. Full table in repos.md.

## 5. Launch decision
**NO-GO for Sept 17-18 auto-merge.** Green: overlay 185/185, kernel router 33/33, 0 unhandled panics, 0 leaks, sub-4 ms error recovery, live 4-model Melious routing with token budgeting. Red/open: burst-extraction SLO+capacity undefined, no 24 h soak, no real-human UX eval, full-repo suite (all domains) not re-run green here. PR #32 stays draft as honest checkpoint; this commit adds evidence, not a fake merge.

## 6. Security flag (carried)
`MELIOUS_API_KEY` and `GIT_AUTH_TOKEN` were pasted in plaintext task text. Treat as compromised: **rotate both immediately.** PAT used only for: read-only API verify, one non-destructive push of this evidence commit to the existing draft-PR branch, and a PR comment. No merge, no protection changes.
