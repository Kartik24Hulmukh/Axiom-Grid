# Axiom-Grid Launch Runbook — target 16/17 Sep 2026

## Honest posture (15 Sep 2026)
- Code: `main` (PR #15 merged) + this PR. Focused suite 172/172, Node E2E 17/17, runtime lock pip-audit: 0 CVEs.
- **The "P95 SLO miss" recorded in every prior session is a bench-host artifact, not a server defect.**
  The CI/bench sandbox is cgroup-capped at **2.0 vCPU** (`/sys/fs/cgroup/cpu.max`, 223 throttled periods) while
  `os.cpu_count()` reports 48. Server + 100-thread client share two cores; measured service time is 1.2 ms
  (~800 RPS/core), which is exactly the ~800–1000 RPS ceiling observed at 1, 4 and 8 workers
  (`docs/axiom/evidence/prod-2026-09-15/scaleout_bench*.json`). Closed-loop latency = concurrency / throughput,
  so 100 threads / 800 RPS ≈ 120 ms P50 by Little's law regardless of server code.
- **What this does NOT prove:** real-hardware P95. GATE 1 below is mandatory before public launch.

## Go / No-Go gates (all must be evidenced in the launch ticket)
1. **Offered-rate soak on real hardware**: `python3 bench/scaleout_bench_mp.py --workers 4 --procs 10 --threads 10 --requests 20000`
   from a *separate* host against a 4-vCPU api container (`WEB_CONCURRENCY=4`). Pass: P95 ≤ 120 ms, P99 ≤ 250 ms, 0 5xx, RSS < 85% limit.
2. **Credential rotation (INCIDENT)**: the Melious key and GitHub PAT were pasted into task text, reports and PR bodies.
   Revoke both, issue new ones into the secret manager only, purge from `docs/axiom/evidence/*`, PR #15 body, tickets.
3. **Full-suite green**: `pip install -r requirements-test.txt && pytest -q` (41 collection errors were optional ML extras + `pdfplumber` dup — dup fixed here).
4. **Independent human review** of PR #15 diff and this PR.
5. **Canary**: deploy 1 replica behind `edge` with 5% traffic for 60 min; watch `AxiomP95LatencySLO`, `AxiomErrorBudgetBurn`, `AxiomLoadShedding`.
6. **Rollback rehearsal** executed once in staging (below) and timed (< 5 min).

## Deploy
```
AXIOM_API_KEYS=$(openssl rand -hex 32) AXIOM_VERSION=v1.0.0 \
  docker compose -f deploy/docker-compose.prod.yml up -d --scale api=2
curl -fsS https://<host>/api/health   # public
docker compose exec api python3 -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8765/readyz').read())"
```
`/metrics`, `/readyz`, `/livez` are 404 at the edge by design; scrape them on the internal network only.

## Scale-out
Each api replica: `cpus: 2.0`, `WEB_CONCURRENCY=2`, `memory: 768M` (measured ~100 MiB/worker peak + headroom).
Capacity ≈ 800 RPS × vCPU. For 100x launch traffic (~2k RPS sustained) run `--scale api=2` (4 vCPU) and keep
`AxiomLoadShedding` < 5%. Never raise `WEB_CONCURRENCY` above the container CPU limit.

## Rollback (< 5 min)
1. `docker compose -f deploy/docker-compose.prod.yml up -d --no-deps api` with `AXIOM_VERSION=<previous>`; or
2. Code-level: `git revert -m 1 9b95ff1 && git push` then rebuild. Snapshot SQLite first: `cp data/*.db backups/$(date +%s)/`.
3. Verify `/readyz` 200 on every replica; close the incident with the trace IDs from JSON logs.

## Alerts → action
| Alert | First action |
|---|---|
| AxiomP95LatencySLO / P99 | add replica (`--scale api=+1`); check `axiom_extraction_shed_total` |
| AxiomErrorBudgetBurn | rollback if > 5 min; inspect spans with status ERROR (tail-sampled 100%) |
| AxiomAuthAbuse | rotate leaked key; tighten `limit_req` at edge |
| AxiomLogDrops | raise `AXIOM_LOG_QUEUE_MAX`; ship logs async |
| AxiomMemoryCeiling | lower `WEB_CONCURRENCY` or raise memory limit; check request byte caps |
