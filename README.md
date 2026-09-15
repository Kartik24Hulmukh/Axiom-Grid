# Axiom-Grid

[![Axiom-Grid focused preview gates](https://github.com/Kartik24Hulmukh/Axiom-Grid/actions/workflows/axiom.yml/badge.svg)](https://github.com/Kartik24Hulmukh/Axiom-Grid/actions/workflows/axiom.yml)

**Local writing. Explicit control.** A focused writing copilot derived from Kairo-Phantom.

> **Engineering preview, not production-ready.** The working slice generates a reviewable suggestion from text you explicitly provide. It does not automatically type into other applications. That feature is gated until target-bound approval and native-platform tests pass.

## What is implemented

- Independent Rust preview runtime (`axiom-runtime`), with no inherited swarm, cloud adapters, plugins, ambient screen capture or injection in its launch path.
- Direct loopback Ollama inference: no proxy use, no redirects, no automatic downloads, no configured cloud fallback.
- Authenticated model-readiness inventory with exact-tag matching and a fail-closed desktop status UI.
- Native IPC bearer authorization; browser-origin and invalid Host requests denied; bounded input/output and one active generation.
- Axiom desktop preview UI with explicit context, literal text rendering and late-result discard.
- Regression coverage for Unicode, session acceptance/cancellation, model identity, CRDT replacement, API security and UI behavior.

## Start here

[Quickstart](QUICKSTART.md) · [Current handoff](docs/axiom/HANDOFF-003.md) · [Fork handoff](docs/axiom/HANDOFF-001.md) · [Launch gates](docs/axiom/LAUNCH-GATES.md)

```sh
cd axiom-runtime
cargo test --locked
cargo clippy --locked --all-targets -- -D warnings
```

An already-installed Ollama model is required for real inference. Local tests use a mock model server, not benchmark evidence.

## Quickstart (cold install, Python sidecar)

A fresh machine to a working overlay in four commands:

```sh
git clone https://github.com/Kartik24Hulmukh/Axiom-Grid.git && cd Axiom-Grid
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.lock -r requirements-test.txt
make run            # hardened overlay API on http://127.0.0.1:8765
```

Required Python dependencies (pinned in `requirements.lock`): `numpy`
(embeddings and similarity search), `fastapi` + `uvicorn` (overlay API),
`pydantic` (strict request schemas), `pdfplumber`/`pypdf` (PDF text and layout),
`python-docx`, `openpyxl`, `python-pptx` (Office readers).

```sh
make test           # 1100+ kernel/overlay regression tests
make run            # start the overlay, then open http://127.0.0.1:8765
```

### Why the sidecar is Python

The launch runtime is Rust, but document intake runs in a Python sidecar on
purpose: the OCR and **layout** engines the product depends on (Docling,
pdfplumber, the Office readers) are **python-native**, and bbox-accurate layout
is what makes every suggestion citable. Rust keeps the UI, IPC and security
boundary; Python keeps OCR/layout. The boundary is a local loopback contract,
so the sidecar can be restarted or sandboxed without touching the runtime.

### Platform support

| Platform | Overlay API + extraction | Desktop preview UI | Ghost-typing / injection |
|---|---|---|---|
| Linux (CI-tested) | Supported | Supported | Not shipped (gated) |
| macOS | Supported, community-tested | Supported | Not shipped (gated) |
| Windows | Supported, community-tested | Supported | Not shipped (gated) |

Ghost-typing into third-party applications stays disabled on every platform
until target-bound approval and per-platform native CI exist. See
`CROSS_PLATFORM_REPORT.md` for the per-platform evidence matrix.

### Concurrency posture (production)

The overlay runs pipelines **concurrently** under a bounded gate
(`AXIOM_PIPELINE_CONCURRENCY`, default `min(32, 4 x cores)`). Shared services
(`ProvenanceLogImpl`, `MemoryStoreImpl`) are thread-safe at class level via
`kernel/core/threadsafe.py`, and SQLite runs in WAL mode with a 5s busy
timeout. No global mutex serializes requests.

## Scope and provenance

Imported from `Kartik24Hulmukh/Kairo-Phantom` at `8975743`. **No upstream changes.** MIT license and source history retained; inherited Rust crate names remain compatible during extraction.

Inherited release workflows and launch documents are archived in `docs/inherited/`. Broad inherited source remains outside the focused executable until dependency-safe pruning is complete. Do not treat inherited reports as Axiom launch evidence. Do not launch the legacy `kairo-phantom` binary as the Axiom product.

No claim of universal app support, certified zero egress, enterprise compliance, specified model speed, product-market fit or “100x” traction has been verified. Signed event logs cannot by themselves prove absence of network egress.

## Production deployment (overlay API)

The hardened FastAPI overlay ships with ops probes and a production container:

```sh
# Containerized one-liner
docker build -t axiom-grid -f docker/Dockerfile.overlay .
docker run --rm -p 8765:8765 axiom-grid

# Ops endpoints
curl localhost:8765/healthz   # liveness
curl localhost:8765/readyz    # real-pipeline readiness (cached, load-safe)
curl localhost:8765/metrics   # runtime counters & latency
```

Hardening posture (all regression-tested in `overlay/tests/test_server.py` and
the 100x/600-request stress gauntlets): SEC-001 sandboxed path resolution,
SEC-002 origin gate, SEC-003 defense-in-depth response headers, SEC-004 bounded
extraction pool + payload-size governor, OPS-001 liveness/readiness/metrics.

## Scope Boundaries (Kairo Phantom contract)

Axiom-Grid ships the Kairo Phantom document-intelligence core. The scope
contract below is enforced by `tests/test_scope_discipline.py` and mirrored in
`CONTRIBUTING.md` and `docs/PUBLIC_ROADMAP.md` — change all three together.

**Kairo DOES**

- READ documents (Word, Excel, PowerPoint, PDF, code, email, design) through the
  extraction pipeline behind admission control and bounded execution.
- SUGGEST grounded answers with page/line-level citations and a provenance
  receipt chain (`opik_trace_id` ↔ `receipts.jsonl`).
- Route model calls through the Melious gateway with per-route circuit
  breakers, reasoning-token budgets and dynamic fallbacks.

**Kairo Does NOT**

- Write, edit, send or execute anything on the user's behalf — the product is
  **READ + SUGGEST ONLY**. Every mutation stays a human decision.
- Answer without evidence. **No source → no answer**: if grounding cannot bind a
  claim to an extracted span, the response is a refusal, never a guess.
- Persist BYO API keys anywhere except the OS keychain abstraction
  (`scripts/keychain_store.py`); config files and logs are scanned for leaks.
