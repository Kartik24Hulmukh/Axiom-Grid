# Axiom-Grid launch verification — 2026-09-29

**Verdict: NO-GO for general availability or automatic merge.** Engineering preview only. Local branch: `harden/axiom-grid-v1-launch`, cloned from `8f381cf`. These measurements are from this host, not a production deployment or 100 recruited users.

## Baseline and changes

| Gate | Untouched clone | After local remediation |
|---|---|---|
| Focused Python gate | 361 pass / 2 fail (permission oracle, stale fixture fingerprint) | 366 pass / 0 fail (`ci/pre-push.sh`, includes three new security/site tests); 1 dependency deprecation warning |
| Broad `tests/` | 1,157 pass / 13 fail / 8 errors / 9 skip without declared `model2vec` | 1,178 pass / 0 fail / 9 skip after installing the declared `model2vec` dependency and fixing scope/demo copy; skips remain unverified |
| Kernel + pack suites | Not separately measured before changes | 172 pass / 0 fail; one dependency deprecation warning |
| Node overlay | Not measured here before changes | 17/17 pass |
| 30-thread local ASGI stress | 300 requests, 0 crashes; 16 rate-limited 429 masked by a weak oracle; p50 107.36 / p95 1,136.36 / p99 1,496.92 ms | Strict expected-status gate: 300 requests; 100×200, 103×404, 97×422; 0 crashes / 0 mismatches; 115.98 req/s; p50 140.15 / p95 891.04 / p99 1,627.47 ms |
| 100-client loopback TCP audit | Not rerun on untouched clone | **FAIL**: 1,000 health 200; 720 fuzz 400/404/422, p50 338.431 / p95 539.748 / p99 544.031 ms, max 625.406 ms (>200 ms); 200 extraction: 140×200, 60×503; 3,000 requests across 120 scripted personas, p50 645.815 / p95 1,118.615 / p99 1,335.695 ms; RSS 71.15–120.98 MiB; fd 11→11; shutdown 164 ms |

The 503s are explicit bounded-admission shedding, not a process crash, but they **fail the requested zero-5xx gate**. A short run and stable fd endpoints cannot prove zero memory/coroutine/socket leaks over a 24-hour soak. One recovered error scenario had p95 5.744 ms, but the loaded fuzz scenario failed the universal sub-200 ms requirement. The two local stress harnesses exercise different traffic mixes and their percentiles are not interchangeable.

## Five-point premortem and disposition

1. **Worker starvation / saturation:** bounded admission protects liveness but 60/200 extraction requests shed under 100 clients. Define an approved burst and shedding SLO; test capacity across replicas before GA.
2. **Unhandled async errors:** no server exception markers in this bounded run, but repeat under cancellation, process restart, and long soak; zero-in-sample is not a universal proof.
3. **Resource growth:** fd 11→11 and RSS 71.15–120.98 MiB in this run; establish repeated-run/24-hour ceilings and compare snapshots.
4. **Gateway cascading failure / spend:** focused router regressions passed; no live model call was made with an exposed key. Rotate credentials first, then run budget/429/5xx/failover and answer-quality validation with capped spend.
5. **Trust and traction failure:** a tracked live key, false sign-up form, wrong repo links, and GA language undermine confidence. Remove exposed key from HEAD, rotate historical exposure, use honest preview copy and collect real user feedback before claiming human evaluation or traction.

## `repos.md` integration log

Reviewed the attached catalog against the project. Existing OTel/Prometheus probes, structured JSON logs, gitleaks configuration, and bespoke load harnesses cover the immediate scope. Borrowed the gitleaks fail-closed pattern and k6/artillery-style status accounting for the existing stress harness. No new third-party code or unverified-license dependency was vendored. Proposed browser-use/OpenBot/Helicone adapters remain proposals, not shipped integrations.

## Release gating

- Repository owner must revoke/reissue the Melious credential committed in history and the chat-exposed GitHub PAT, audit usage, and use a secret manager. Neither compromised value was used for this run.
- Require a fresh clean-host Python/Rust/Node/browser E2E gate, signed artifacts, and external receipt verification at the release SHA. Rust tooling and live authenticated gateway runs were not available/attempted here.
- Resolve extraction shedding against an approved SLO and loaded fuzz max <200 ms; repeat 100-client TCP tests, 24-hour soak, multi-replica restart, and recruited human usability tests with recorded evidence.
- Do not publish a launch PR, push with exposed credentials, auto-merge or claim production readiness until every gate above is met. Use `LAUNCH-BLOCKERS.md` for the public blocker list.
