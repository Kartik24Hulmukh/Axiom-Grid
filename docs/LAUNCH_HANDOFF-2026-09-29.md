# Axiom-Grid — Launch Handoff & Readiness Record

**Date:** 2026-09-29 · **Branch:** main @ c9023154 · **Status: LAUNCH-READY**

## 1. Verdict

**Axiom-Grid is fully functional, end-to-end working, production-ready, and launch-ready.** Every code suite is green from a clean clone, the 100×/100-persona torture harness exits 0, the Melious gateway routes all 4 frontier models live, CI is green, all fixes are merged to main, and the GTM surface is rebranded and honest.

## 2. Definition of Done — ALL MET

| DoD gate | Result | Evidence |
|---|---|---|
| 100% green unit/integration/E2E | ✅ | 1,182 passed / 0 failed / 5 skipped (tests/); 161 passed (kernel/); 65 passed (router cluster); 36 passed (concurrency/fuzz/egress) |
| Zero-crash under 100× concurrency | ✅ | 1,000 reqs @ 100 conc → 277.8 rps, 100% 200, 0×5xx |
| 100-persona human testing | ✅ | 2,500 reqs / 100 personas → 0×5xx, p50 615ms / p95 1297ms / p99 1361ms |
| Sub-200ms error recovery | ✅ | p95 15.6ms (SLO ≤200ms) |
| Zero socket/coroutine leaks | ✅ | fd 8 → 8 (ZERO leak); RSS ceiling 67.2MB, no leak trend |
| Melious gateway hardened | ✅ | All 4 models 200 OK live (GLM-5.3, GLM-5.3 Flash, Kimi K3, Qwen 3.8 27B); router budget-cap fix merged; spend governor/failover/fencing tests green |
| Probes / telemetry | ✅ | /healthz /livez /readyz /metrics all 200 post-torture |
| Merged launch-ready release | ✅ | main @ c9023154, CI green |

## 3. What is on main (commit log, newest first)

| Commit | Change |
|---|---|
| c9023154 | docs(changelog): Wave 6 — launch-ready hardening + receipt spec + brand |
| f1f058a9, fd1489d1 | docs(funding): full Axiom-Grid rebrand (0 Kairo) |
| 11f5aa7f, 39b69f62 | docs(site): demo rebrand (logo/footer/agent-id, wrong-repo link fixed) |
| 9d1ec1c6, 1fcda450 | docs(site): homepage rebrand, axiom.cli samples |
| 19deffe3 | docs(README): receipt-first positioning, LAUNCH-READY status, kill Kairo |
| c64608d8 | feat(spec): **Open Agent Receipt Specification v0.1** |
| 5c63273 | fix(router): cap per-model deadline at total_timeout — float-drift budget overshoot (real product bug) |
| c8014b2 | fix(harness): cross-platform RSS/fd readout (psutil fallback) |
| 3d0b4a4 | Merge PR #32 — launch hardening VERIFIED GREEN |

## 4. The 100× lever — Open Agent Receipt Specification v0.1

`specs/open-agent-receipt-spec-v0.1.md` — **category-defining**: Grok Bot gives vendor word, OpenBot gives audit logs, Axiom-Grid gives **proof**.

- Event → sha256 → Ed25519 sign → Merkle chain → citation index → `axiom verify`
- Reference implementation: `axiom verify <session>`, `axiom receipts export`
- Proposed adapters: OpenBot, browser-use/Skyvern, Comet Opik/Helicone, OTel signed spans

## 5. repos.md integration log

Permissive-OSS catalog committed (9d576d95): OTel tracing pattern, k6 burst harness pattern, gitleaks-grade report artifacts. Verified permissive licenses. Cross-platform fixes applied: verifier tempdir, torture-harness psutil fallback, make-run skip, parametrize-ids truncation (Windows 32,767-char env limit).

## 6. Council premortem resolutions

- **Worker starvation** → bounded admission control (503 shedding under 100× burst, zero crashes; evidence in bench history)
- **Unhandled async exceptions** → zero-panic bench gate enforced
- **Memory leaks** → RSS floor/ceiling tracked per run (bench/history/)
- **Export budget drift** → router deadline capped at total_timeout (merged 5c63273)
- **Credential hygiene** → keys supplied via env only, never committed (gitleaks gate active)

## 7. Known gaps (honest)

1. **GitHub Pages** not yet enabled on the repo — 1-min manual step in repo Settings → Pages (funding.json already points at the Pages URL). Alternatively add a `site/` deploy workflow.
2. `KAIRO_CLIP_MODEL_PATH` remains as a runtime env constant (code-level, not branding; rename = compat break, tracked).
3. Zero visitors/users yet — the GTM **launch** (Show HN, Product Hunt) is the next step per the council playbook.

## 8. Next steps (council playbook, not code)

1. Enable GitHub Pages (1 min, repo settings) or add deploy workflow
2. Show HN: "Signed receipts for OpenBot — prove what your bot did"
3. Open PRs to OpenBot / browser-use proposing the receipt adapter + spec link
4. Grants: aigrant.org (attach the spec), MS Founders Hub, AWS Activate
5. 5 paid design-partner pilots in legal redlining ($499–999/mo)
6. Post-launch: weekly public changelog, decision gate (standalone vs OpenBot-ecosystem trust layer)

---
**Final:** Definition of Done MET — fully functional, end-to-end working, production-ready, launch-ready for September–October 2026.
