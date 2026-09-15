# Axiom-Grid — Session 15 production checkpoint

**Verified September 15, 2026 · Launch September 16–17 · Decision: NO-GO**

PR #20 remains draft. Do not merge: focused CI is not full launch certification.

## Delivered remediation

Code commit `3d14022` on `harden/axiom-grid-prod`:
- Account validated upstream usage before validating completion output. Empty/malformed choices and over-budget responses previously erased real billed usage; retries/fallbacks now accumulate all reported usage exactly once.
- Derive total usage as at least prompt + completion tokens when upstream totals are missing or understated; do not double-count reasoning tokens already included in completions.
- Always release inflight permits on admission cancellation and settlement exceptions.
- Correct the spend-governor documentation: this is an estimated **process-local admission ledger**, not a durable fleet-wide/provider billing ceiling. The English heuristic is not a tokenizer upper bound. Blocker #4 from Session 14 must be reopened.
- Add ten accounting/lifecycle regressions and a reproducible paired microbenchmark. Eight initial regression cases failed before remediation. Existing over-budget fallback assertion strengthened to count 4,099 billed completion tokens, not merely the final two accepted tokens.

Baseline CI on `8c315ed` actually had focused-runtime FAILED (ruff PLR1730), not five passing checks. Another writer pushed `f120df5` during this run; fetched and rebased without force-push, preserving that change. All five checks subsequently passed on `3d14022`: focused-runtime, focused-overlay, overlay-container, legacy-resource-lifecycle, GitGuardian. Later evidence-only head requires its own CI verification.

## Validation evidence

| Gate | Observed result |
|---|---|
| Baseline overlay + kernel | 227 passed |
| Candidate overlay + kernel, strict ResourceWarning/unraisable handling | 237 passed, 13.93 s, after rebase |
| Root `tests/`, after installing available dependencies | 1,116 passed, 4 skipped, 49.52 s |
| Legacy lifecycle/integration selection, strict warnings | 41 passed |
| Node overlay | 17 passed |
| Broad E9/F lint and focused lint | Passed |
| Whole repository, importlib mode, bounded at five failures | **5 failed, 829 passed, 17 skipped**, 43.91 s; not complete |
| Real auth gauntlet | 1,000 requests / 100 clients; zero transport errors; all security invariants passed; health/readiness 100/100 each |
| Undrained-log health spike | 2,000 HTTP 200; 40 clients; 1,715 logs deliberately dropped; shutdown 0.164 s; RSS growth after warmup 5.25 MiB |

Root skips: external training dataset, LibreOffice, PDF form fixture, missing cross-platform workflow. Whole-repository blockers observed: parquet engine missing, two podcast/TTS failures, faster-whisper missing, and trace-receipt isolation failure (0 traces expected 1). Isolated trace/lifecycle selection passes, so suite-order interaction remains to investigate. Installing embed-anything failed during dependency resolution/source metadata on Python 3.14. Do not treat dependency failures as waived or passing tests.

## Paired synthetic gateway benchmark

Same machine, `8c315ed` vs candidate, ten barrier bursts of 100 threads per fault. Real router with injected synchronous upstream; no external latency. Throughput includes pool/barrier overhead. RSS sampled between bursts in one shared process, not isolated memory peaks. A single paired run is noisy, not a speedup claim.

| Fault / version | P50 ms | P95 ms | P99 ms | requests/s | sampled RSS MiB floor–ceiling |
|---|---:|---:|---:|---:|---:|
| 429 baseline | 0.0515 | 0.0846 | 0.0982 | 7,845.65 | 26.75–27.50 |
| 429 candidate | 0.0226 | 0.0724 | 0.0988 | 11,792.45 | 26.00–26.00 |
| 503 baseline | 0.0490 | 0.0863 | 0.1047 | 7,731.68 | 26.75–27.125 |
| 503 candidate | 0.0511 | 0.0844 | 0.1087 | 7,587.82 | 24.867–25.242 |

P99 delta: +0.0006 ms (429), +0.0040 ms (503). Throughput delta: +50.3% / −1.9%, dominated by microbenchmark scheduling variability. All 2,000 candidate calls succeeded; 16,000 tokens accounted, zero reservations leaked. P99 is under 200 ms for injected faults; this does not certify live-provider detection deadlines. Most requests encounter the already-open bad route.

## Real ingress: useful capacity remains blocked

One local uvicorn process, private state, same text fixture; 60 sequential calls then 100 concurrent calls. This is 100 clients, **not a demonstrated 100x production offered-load baseline**. No ingress code changes were made; do not compare these numbers causally to Session 13's larger run.

| Clients | HTTP 200 / 503 | P50 ms | P95 ms | P99 ms | useful req/s | sampled RSS MiB |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 60 / 0 | 367.675 | 420.481 | 630.987 | 2.670 | 77.03–87.21 |
| 100 | 20 / 80 | 680.277 | 6,244.429 | 7,664.682 | 2.599 | 87.21–101.46 |

**80% shed; useful throughput fell 2.7%.** Zero observed transport errors/HTTP 500 in this sample. Shutdown took 0.169 s with return code −15 (SIGTERM), not a certified clean application exit. Admission control prevents queue explosion but does not solve extraction serialization.

## Live model smoke (four calls only)

No production torture/stampede: known capacity/budget gaps make sustained paid load inappropriate. One call per configured route, max_tokens=64, no retries, 12 s overall router budget, local admission ceiling 256 each.

| Requested route | Outcome | latency s | reported ledger tokens |
|---|---|---:|---:|
| GLM-5.3 | BudgetExhaustedError, no visible completion | 1.303 | 80 |
| GLM-5.3 Flash | BudgetExhaustedError, no visible completion | 3.321 | 84 |
| Kimi K3 | Success | 1.659 | 183 |
| Qwen 3.8 27B | Success | 0.818 | 49 |

All reservations released; 396 tokens recorded total. GLM budget exhaustion is not availability success. Kimi reports 128 prompt tokens for a 13-character prompt, directly demonstrating why the existing character heuristic cannot be a hard cap. Missing/invalid usage and billed transport failures remain unknowable locally; hard spend enforcement needs provider-side controls and a durable atomic external ledger.

## Five-point premortem and release gates

1. **Worker starvation — OPEN:** separate parser execution from shared store/provenance state; benchmark process isolation and replica scaling with fixture diversity, useful throughput and tail latency. Do not simply increase queue depth.
2. **Async exceptions/lifetimes — PARTIAL:** router admission/settlement permit leaks fixed; strict lifecycle checks pass; whole-suite trace isolation failure remains.
3. **Memory/observability — PARTIAL:** bounded logging and health/readiness tested; collector ingestion, alerts, sustained soak and multi-replica deployment not verified.
4. **Provider cascade/spend — OPEN:** rejected billed responses now counted; synthetic faults pass. Process-local estimates, unknown usage, retries and replica multiplication still prevent a fleet ceiling guarantee. External durable reserve/settle with unique attempt IDs, conservative unknown-outcome settlement and provider cap required.
5. **Dependencies/release drift — OPEN:** root tests green with four explicit skips; whole repository fails; lock supported Python/native dependencies and certify full native/integration/E2E on final head.

No merge until all gates pass. No module exceeded five remediation cycles: router two implementation/validation rounds; dependency provisioning remained bounded; no test was skipped or weakened to obtain green.

Credentials supplied in the transcript should be revoked/rotated immediately. They were used only for authorized GitHub operations and four bounded provider calls, never committed to files or remote URLs. Production deployment, collector setup and multi-replica soak were not performed.

Reproduce: `python3 -m pytest -q overlay/tests kernel/tests -W error::ResourceWarning -W error::pytest.PytestUnraisableExceptionWarning`; `python3 scripts/benchmark_router_accounting.py`; `python3 scripts/benchmark_ingress_session15.py`. Raw evidence: `docs/axiom/evidence/session15-*`.
