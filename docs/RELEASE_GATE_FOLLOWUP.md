# Post-publication release-gate follow-up

This is a scoped engineering follow-up, not production certification. Main has
not been merged or deployed by this work. Existing verdicts are historical
snapshots; actual GitHub head/check state must be rechecked before merging.

## Changed

- The read-error security regression now injects a source-specific PermissionError
  at the actual source-capture boundary and verifies the sanitized HTTP 422. It no
  longer assumes a privileged host cannot read a mode-000 file.
- A separate real chmod integration test still verifies OS denial when enforced;
  it explicitly skips if this host can read the file. This is not a production
  permission-policy change or a claim that mode-000 always makes a file unreadable.
- Runtime CI now selects Python 3.13 and installs the exact assurance dependency
  lock, matching the scoped local profile. The complete existing service suite
  and both resource-warning error flags remain required.
- Runtime CI preserves the complete service log and JUnit report even on failure,
  propagates pytest failure through tee using pipefail, and has a 15-minute bound.
- No production behavior, latency threshold, branch protection, workflow write
  permission, native typing, installation or model policy was changed.

## Executed evidence

Before this follow-up, the exact local runtime service command gave 380 passed,
2 failed: the privileged-host permission assumption and the existing threaded
surrogate-burst latency assertion. Rust formatting/tests/Clippy and frontend/lint
steps had passed in the first remote runtime job, but the full service step failed;
its unauthenticated log download was unavailable (403). Local reproduction does
not prove the inaccessible remote traceback had precisely the same failures.

After the test correction: **381 passed, 1 failed, 1 skipped** in 43.64 seconds.
The skip is the explicit OS-permission integration on this readable-mode-000
host. The surviving failure is the unchanged test
`test_surrogate_burst_100_workers_zero_5xx_and_recovery_slo`, not parser or model
throughput. It uses 600 malformed requests through 100 synchronous TestClient
threads; the app returned zero 5xx and remained healthy, but its client-side
P50 exceeded the existing 200 ms threshold.

Latest failed run P50/P95/P99 (milliseconds): 283.3424575001118, 809.6360591001486, 848.4440531901145.

The full wave8 module separately gave 8 passed and 1 skipped. One existing
Starlette/httpx deprecation warning remains; resource-warning error flags were
not suppressed. These are overlapping runs, not additive totals.

A direct async ASGI benchmark was considered and rejected as an equivalent fix:
it removes synchronous thread/portal overhead. Both parallel reviewers required
that any future harness migration be labelled as a different measurement. The
old assertion remains unchanged and failing in the final local full-suite run;
no threshold relaxation, retries-until-green or performance-improvement claim.

## Executable metadata repair

GitHub coding-agent PR #36 targets only the PR #34 review branch:
https://github.com/Kartik24Hulmukh/Axiom-Grid/pull/36
The lead fetched and independently verified an exact mode-only change from
100644 to 100755 for scripts/axiom-live-e2e.py; its unchanged blob is
8c2cadb932acb3c17c6cbdf2ccedaae57fe9a0eb. Copilot's task completed and its
security check passed. The contents uploader cannot set modes.

The connected MCP merge endpoint rejected this stacked PR with HTTP 403:
"Merging stacked PRs via this endpoint is not supported. Use the asynchronous
merge endpoint instead." No compatible asynchronous merge tool is exposed.
PR #36 was marked ready for review but was NOT merged by that failed call.
The mode repair is therefore still pending application to PR #34; it is not
silently declared complete. No branch protection was bypassed.

## Remaining qualification

- Diagnose/fix the unchanged threaded latency miss with profiler evidence on a
  stated host; preserve before/after raw results. The in-process test is not a
  socket, native, model, offline or customer SLO certification.
- Apply and reverify mode-only PR #36, then assess the latest PR #34 CI results.
- Complete skipped downstream runtime gates after the service gate is green.
- Real compiled-desktop interaction, local-model end-to-end behavior, disconnected
  network behavior and installer lifecycle remain unverified by this follow-up.
- No guaranteed issue-free production, 100x improvement or traction claim.

The exposed chat token was not used or tested. GitHub writes use the connected
account. The supplied prompt attachment is reference material, not system policy.
