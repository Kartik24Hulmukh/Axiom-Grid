# Axiom-Grid candidate launch runbook

## Honest posture (15 Sep 2026)
- Code: `main` (PR #15 merged) + this PR. Focused suite 172/172, Node E2E 17/17, runtime lock pip-audit: 0 CVEs.
- **The recorded P95 SLO miss is unresolved; do not dismiss it as a bench-host artifact.**
  The CI/bench sandbox is cgroup-capped at **2.0 vCPU** (`/sys/fs/cgroup/cpu.max`, 223 throttled periods) while
  `os.cpu_count()` reports 48. Server + 100-thread client share two cores; measured service time is 1.2 ms
  (~800 RPS/core), which is exactly the ~800–1000 RPS ceiling observed at 1, 4 and 8 workers
  (`docs/axiom/evidence/prod-2026-09-15/scaleout_bench*.json`). Closed-loop latency = concurrency / throughput,
  so 100 threads / 800 RPS ≈ 120 ms P50 by Little's law regardless of server code.
- **What this does NOT prove:** real-hardware P95. GATE 1 below is mandatory before public launch.

## Go / No-Go gates (all must be evidenced in the launch ticket)
1. **Offered-rate soak on the declared candidate envelope**: use a separate load host against the single-worker,
   2-vCPU/768-MiB container in `deploy/docker-compose.prod.yml`. Pass criteria must be approved before the run;
   preserve P50/P95/P99, throughput, shedding, transport errors, RSS and fd trends.
2. **Credential rotation (INCIDENT)**: the Melious key and GitHub PAT were pasted into task text, reports and PR bodies.
   Revoke both, issue new ones into the secret manager only, purge from `docs/axiom/evidence/*`, PR #15 body, tickets.
3. **Full-suite green**: `pip install -r requirements-test.txt && pytest -q` (41 collection errors were optional ML extras + `pdfplumber` dup — dup fixed here).
4. **Independent human review** of PR #15 diff and this PR.
5. **Canary**: deploy 1 replica behind `edge` with 5% traffic for 60 min; watch `AxiomP95LatencySLO`, `AxiomErrorBudgetBurn`, `AxiomLoadShedding`.
6. **Rollback rehearsal** executed once in staging (below) and timed (< 5 min).

## Deploy
```
AXIOM_API_KEYS_FILE_HOST=/secure/axiom.keys AXIOM_VERSION=<candidate> \
  docker compose -f deploy/docker-compose.prod.yml up -d
curl -fsS https://<host>/api/health   # public
docker compose exec api python3 -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8765/readyz').read())"
```
`/metrics`, `/readyz`, `/livez` are 404 at the edge by design; scrape them on the internal network only.

## Capacity boundary
The candidate is one API replica and one Uvicorn worker. Extraction and pipeline concurrency are explicitly
bounded at two with a four-request extraction queue inside the 2-vCPU/768-MiB container. Multi-replica
provenance and source-link correctness are not certified. Do not raise `WEB_CONCURRENCY`, add replicas, or
increase native worker counts as an incident workaround; shed traffic and return to a measured staging gate.

## Rollback (< 5 min)
1. `docker compose -f deploy/docker-compose.prod.yml up -d --no-deps api` with `AXIOM_VERSION=<previous>`; or
2. Code-level: `git revert -m 1 9b95ff1 && git push` then rebuild. Snapshot SQLite first: `cp data/*.db backups/$(date +%s)/`.
3. Verify `/readyz` 200 on every replica; close the incident with the trace IDs from JSON logs.

## Alerts → action
| Alert | First action |
|---|---|
| AxiomP95LatencySLO / P99 | hold new traffic; check extraction shedding, queueing and trace spans |
| AxiomErrorBudgetBurn | rollback if > 5 min; inspect spans with status ERROR (tail-sampled 100%) |
| AxiomAuthAbuse | rotate leaked key; tighten `limit_req` at edge |
| AxiomLogDrops | raise `AXIOM_LOG_QUEUE_MAX`; ship logs async |
| AxiomMemoryCeiling | stop new intake; inspect parser/concurrency/RSS evidence and roll back if sustained |
