# Axiom-Grid: gated deployment and rollback runbook

**Release gate: NO-GO.** This runbook is a procedure, not evidence of deployment.
PR #19 is a hardening candidate, not a production certification. Do not merge or
publish a release until all user-defined gates have evidence and owner sign-off.

## 1. Boundary and prerequisites

- Incident owner: rotate/revoke BOTH credentials exposed in the task prompt.
  Supply replacement Melious/API/GitHub credentials through a secret manager.
  Do not paste them into issue bodies, command histories or image build args.
- Product owner: single-tenant, invite-only, text/Markdown memo preview only.
  One tenant per deployment with distinct state volume and key. Multiple API
  keys in one instance DO NOT provide tenant/document ownership isolation.
- Platform owner: stage on a separate host; this session has no Docker or Rust
  toolchain and cannot certify deployed infrastructure. GitHub container CI is
  a smoke gate, not TLS, collector, SBOM, canary or rollback evidence.
- Use immutable source SHA/image digest. No `latest`, no force-push, no rewritten
  benchmark rows. Store raw outputs, command, environment and SHA256 manifest.
- Overlay extraction currently forces `KAIRO_GATEWAY_TEST_MODE=true` and disables
  cloud inference. Its deterministic preview is NOT proof that the separately
  tested Melious router powers the public product end-to-end.

## 2. Reproduce code verification

On a clean supported runner, install the focused workflow dependencies and run:

```sh
python3 -m pytest -q -p no:cacheprovider overlay/tests kernel/tests -W error::ResourceWarning -W error::pytest.PytestUnraisableExceptionWarning
python3 -m ruff check --select E9,F overlay kernel scripts/stress_sec006_gauntlet.py stress_test.py
node --test phantom-overlay/tests/app.test.cjs
python3 scripts/stress_sec006_gauntlet.py
python3 scripts/stress_wave11.py
python3 scripts/bench_v1_prod.py 2000 100 --paths /healthz,/livez,/readyz,/metrics
python3 scripts/bench_extraction_admission.py
python3 -m pytest --collect-only -q --import-mode=importlib
```

The last command currently fails: do not hide missing tests with exclusions or
mark them passing. Full suite requires reconciliation of obsolete `packs.wedge`,
PDF tests requiring prohibited-by-repo-policy `fitz`, optional CPU/model deps,
fixture hashes and shape-readback failures. Importlib removes basename collisions
but is not a fix for these failures. Full GPU/native/E2E requirements need an
explicit supported matrix and actual execution.

## 3. Build and stage exact image

After release blockers close, record the approved SHA and build:

```sh
docker build -f docker/Dockerfile.overlay -t axiom-grid:$AXIOM_VERSION .
docker image inspect axiom-grid:$AXIOM_VERSION
```

Generate an SBOM and vulnerability scan against that exact digest, document each
finding and obtain security disposition. Follow `deploy/docker-compose.prod.yml`
only after validating secret injection, volume ownership (UID/GID 10001), TLS certs,
trusted edge forwarding and non-root/read-only startup. Start ONE tenant on ONE
API instance initially; do not infer safe horizontal scale from the compose file.
Its shared SQLite volume, process-local quotas/breakers and internal-only model
egress require an architecture review before live-model/multi-replica operation.

Verify authenticated extraction of a redacted fixture, anonymous 401, fail-closed
503 with absent keys, traversal 404, malformed input 422, streamed body 413, and
that database/private documents cannot be fetched through public static routes.
Check `/healthz`, `/readyz`, `/metrics` from the appropriate network boundary.
**Readiness caveat:** `/readyz` caches a one-time synthetic extraction; it is not a
continuous DB/gateway/volume check. Implement and test dependency readiness before
using it as a full production traffic gate.

## 4. Telemetry acceptance

- Confirm JSON stdout, matching trace/span IDs, safe route-template attributes,
  W3C parent continuity and no credentials/document text in exported telemetry.
- Exercise both undrained output pipes; serving and shutdown must remain bounded.
  Alert on dropped logs; queue shedding prevents a deadlock, not lossless auditing.
- Verify an actual OTLP span arrives at the collector/backend, Prometheus scrapes,
  and alerts route to a staffed on-call contact. In-memory SDK tests are insufficient.
- Define durable security/audit logging separately; queue shedding is unsuitable
  as the only compliance audit trail.

## 5. Capacity acceptance and canary

Define 1x from measured design-partner traffic (document sizes/types, extraction
mix, upstream token demand), then drive 100x offered arrival rate on a separate
load-generator host. Do not equate 100 threads to 100x product demand. Record:
P50/P95/P99 for successful extraction, explicit shedding, end-to-end model latency,
throughput, unexpected errors, worker queue depth, FD/thread counts, RSS floor/peak
and post-drain recovery. Preserve all replica/worker counts including failing rows.
Test client cancellation, oversized/chunked inputs, provider 429/5xx/timeouts,
half-open recovery, token ceilings and safe refusal. Provider chaos must use a
controlled local fault server; obtain operator quotas before paid upstream load.

Provisional probe gates already in the harness: P95 <=120 ms, P99 <=250 ms,
>=99.99% 2xx. They are not product extraction SLOs. Establish workload-specific
latency and shedding/error targets before the full soak. Run a 60-minute canary
only after prior gates pass; stop for unexpected 5xx, growing memory/queues, privacy
failure or budget overrun. The 768 MiB limit in compose is a configured ceiling,
not a measured full-load certification.

## 6. Rollback rehearsal (not yet performed)

Record the current approved image digest and a consistent SQLite backup before
canary. If abort thresholds trigger: stop admitting new work at the edge, drain
with a bounded timeout, restore the last known-good image/config. Do NOT blindly
restore state if newer writes would be lost; require an approved data recovery
plan and schema compatibility check. Verify readiness, auth and a real extraction.
Record stopwatch time to recovery and data integrity results; target <5 minutes
must be demonstrated, not checked off. Current main is not a production-certified
rollback target merely because focused CI is green.

## 7. Founder acceptance

Five reviewers, ten redacted memos each. Instrument upload-to-first-useful-result,
review time vs existing workflow, correction/refusal rate and week-one repeat use.
Target >=30% median review-time reduction without worse critical-error rate.
Label the product a design-partner preview; no 100x impact/traction guarantee.
