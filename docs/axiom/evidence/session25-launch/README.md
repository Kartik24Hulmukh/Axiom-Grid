# Session 25 re-verification (2026-09-16) — candidate 1ef1a67 on harden/axiom-grid-v1-launch

Independent re-run of the fail-closed launch audit on a fresh host. Scope: real loopback TCP, authenticated,
isolated temp state, 120 seeded synthetic clients, 300 abandoned raw sockets, no external model calls.

## Gates
| Gate | Result |
|---|---|
| Focused suite (overlay/tests, test_launch_tcp_audit, test_concurrency) | 204 passed, 16.98 s |
| PR #32 CI (GitGuardian, legacy-resource-lifecycle, overlay-container, focused-runtime, focused-overlay) | 5/5 success |
| /healthz /livez /readyz /metrics | all 200 |
| Unhandled exception markers in server log | 0 (2,593 structured JSON lines, no tracebacks) |
| FD base -> after | 11 -> 11 (growth 0) |
| RSS floor / ceiling | 96.86 MiB / 161.59 MiB |
| Lifespan shutdown | 0.264 s, complete |
| Transport errors / 5xx (excluding admission shedding) | 0 |
| Post-load recovery P50/P95/P99 | 1.834 / 3.985 / 4.776 ms (<200 ms PASS) |
| Extraction queue, 100 clients x 200 requests, workers=8 depth=64 | 125 x 200, 75 x 503 Retry-After -> **GATE FAILS** |

## Latency
| Scenario | N | C | P50 | P95 | P99 | RPS |
|---|---:|---:|---:|---:|---:|---:|
| health | 200 | 1 | 0.994 | 2.036 | 2.380 | 818.4 |
| health | 1000 | 100 | 107.426 | 170.752 | 174.277 | 837.1 |
| fuzz (610x422/90x400/20x404) | 720 | 100 | 183.149 | 248.002 | 251.649 | 513.6 |
| extraction queue | 200 | 100 | 228.481 | 406.464 | 419.399 | 358.2 |
| synthetic 120 clients | 3000 | 120 | 117.246 | 1553.901 | 1999.747 | 291.7 |
| recovery | 120 | 1 | 1.834 | 3.985 | 4.776 | 417.2 |

## Disposition
The 503s are OPS-004 bounded admission (BoundedSemaphore workers+queue) returning fast with Retry-After.
This is correct backpressure, not a crash. Enlarging AXIOM_EXTRACTION_QUEUE_DEPTH to hide it would be a
cosmetic workaround and is deliberately NOT done. Capacity/SLO for extraction under 100-client burst must be
set by product before this gate can be declared green. repos.md remains absent from ZIP and repo; no catalog
integration is claimed. Decision: PR #32 stays open; not auto-merged.
