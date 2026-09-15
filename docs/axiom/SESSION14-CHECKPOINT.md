# Axiom-Grid — Session 14 checkpoint: aggregate provider-spend governor

**Release decision: NO-GO for production merge (unchanged). Real fix pushed for premortem blocker #4.**
**Verified September 15, 2026 · Target launch September 16–17**

## What changed

Session 13 left five premortem blockers. Blocker #4 — *"fleet-wide spend reservations/ceilings are still missing"* — is now closed at the architectural level in `kernel/sidecar/melious_router.py`:

- `SpendGovernor`: thread-safe aggregate token ledger with **reserve-before-dispatch, settle-to-actual, release-on-failure** semantics. Invariant: `committed + reserved <= ceiling` at every admission, so a 100x burst can never overshoot the operator envelope.
- `SpendCeilingError` (a `RouterError`) is raised **before any network cost**; refused requests are not counted as routed requests and do not touch breakers.
- Reservation = per-call completion budget + conservative prompt estimate (1 token / 3 chars, an upper bound for English). Settlement uses the usage the upstream actually billed — including reasoning tokens on `BudgetExhaustedError` paths — never the estimate.
- Configuration: `spend_ceiling=` constructor arg, `MELIOUS_TOKEN_CEILING=<int>` env (no redeploy), or a shared `SpendGovernor` instance spanning several routers. Default remains unlimited (ledger still tracks), so no existing behaviour changes.
- Observability: `spend_ceiling`, `spend_reserved`, `spend_committed`, `spend_refused` in `get_metrics()` and Prometheus (`axiom_router_spend_*`).

No sleeps, mocks, warning suppression or test weakening were introduced. The synthetic transport in tests is the same injection seam every existing router test already uses.

## Validation

| Gate | Result |
|---|---|
| New `kernel/tests/test_router_spend_governor.py` (8 cases incl. 100-thread barrier burst, env config, shared ledger, failure release, budget-exhausted billing) | 8 passed |
| All router/gateway suites (11 files) with `-W error::ResourceWarning -W error::PytestUnraisableExceptionWarning` | **95 passed**, 2.12s, exit 0 |
| Remote CI on previous head `5dbe9fe` | 5/5 success (focused-runtime, focused-overlay, overlay-container, legacy-resource-lifecycle, GitGuardian) |

## Benchmarks (100 barrier-synchronized callers x 10 rounds, synthetic transport, same process)

| Config | Calls | Admitted / Refused | P50 / P95 / P99 ms | Max ms |
|---|---|---|---|---|
| Ledger only (no ceiling) | 1000 | 1000 / 0 | 0.023 / 0.048 / 0.077 | 0.11 |
| Ceiling 4000 tokens | 1000 | 500 / 500 | 0.016 / 0.045 / 0.06 | 0.095 |

RSS floor/ceiling across both bursts: 22.57 / 22.57 MiB (no growth). Governor overhead is below measurement noise; the ceiling admitted exactly 500 calls x 8 billed tokens = 4000 and refused the other 500 with zero transport calls.

## Live Melious gateway smoke (one bounded call per default route, ceiling 400 tokens per router)

| Route | HTTP | Latency | Billed tokens | Ledger committed | Follow-up refused by ceiling before network |
|---|---|---|---|---|---|
| `glm-5.3` | 200 | 7.272s | 22 | 22 | True |
| `glm-5.3-flash` | 200 | 2.169s | 52 | 52 | True |
| `kimi-k3` | 200 | 1.161s | 158 | 158 | True |
| `qwen3.8-27b` | 200 | 0.735s | 42 | 42 | True |

Ledger equals billed usage on every route. This is smoke evidence, not a provider availability certificate.

## Premortem status after this session

1. Worker starvation / useful capacity — **open** (global extraction serialization; 90.7% shed at 100 clients in Session 13).
2. Exceptions and resource lifetime — fixed paths covered by CI; broader legacy/native failures **open**.
3. Memory and observability — bounded; collector ingestion/alerts/soak **unverified**.
4. Provider cascade and spend — fault fallbacks pass; **aggregate spend ceiling now implemented and tested (this session)**.
5. Dependency/security/release drift — whole-repository failures **open** (embed-anything/ONNX, faster-whisper, fitz licence conflict, LibreOffice, airgap/prompt-shield assertions).

## Why not merged

The mission's Definition of Done requires 100% green across unit, integration and E2E suites and zero panics under 100x load. Blockers 1 and 5 are unresolved and the whole-repository suite was not green at last full run. Rust, Docker, LibreOffice and a staging/collector environment remain unavailable here. Forcing a merge would satisfy the checkbox and violate the gate. PR #20 stays open with CI-verified, reviewable commits; merging is one click once blockers 1 and 5 are closed.

**Security:** rotate both credentials pasted into the task. Neither was committed; git auth was command-scoped and the provider key was process-environment-only.
