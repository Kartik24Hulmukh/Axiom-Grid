# Axiom-Grid

**Current checkpoint: [v5 local security, coverage and unresolved launch gates](docs/V5_HARDENING_CHECKPOINT.md).** Strict576, broad1,543/two skips, browser43; suites overlap. Full short100-client workloads have no observed5xx/transports, but errors still exceed200ms, and a separate clean credential workflow failed on two transports before a functional diagnostic replay. This is not production readiness, human adoption or traction.

[![Axiom-Grid focused preview gates](https://github.com/Kartik24Hulmukh/Axiom-Grid/actions/workflows/axiom.yml/badge.svg)](https://github.com/Kartik24Hulmukh/Axiom-Grid/actions/workflows/axiom.yml)

**Signed, verifiable observations for agents that touch documents.** Axiom-Grid is an engineering preview: offline document extraction, provenance inspection, a separate legal-redline CLI, and signed agent-event export with pinned-key verification.

## What works and what is gated

- **Receipt export:** caller-supplied OpenBot audit events or Opik/Helicone trace JSON → bounded Ed25519-signed linear hash chain → offline verification. These are export adapters, not live every-action instrumentation.
- **Document preview:** real local extraction, provenance inspection, correction recording, and safe text rendering. The overlay does not perform desktop writes; Accept fails closed until a native writer and independent read-back exist.
- **Separate legal-redline CLI:** `python -m kairo.cli redline ...` writes new local output artifacts; `python -m kairo.cli verify ...` checks that workflow's existing manifests. It is distinct from agent receipt export.
- **Trust boundary:** signatures verify observations and integrity, not the truth/completeness of agent execution or an OS-wide zero-egress guarantee. Citation checking and runtime-scoped egress reports are separate checks.
- **Open spec:** [implemented experimental format](specs/OPEN_RECEIPTS_V0_1.md), [adapters and limits](docs/RECEIPT_ADAPTERS.md). No Merkle-tree or ecosystem-adoption claim.

## Status — engineering preview (historical run: 2026-09-29)

| Gate | Result |
|---|---|
| Historical Python suite | **1,182 passed / 0 failed / 5 skipped** on prior environment; not a full current release gate |
| Kernel suite | **161 passed / 0 failed** |
| Router hardening cluster | **65 passed / 0 failed** (spend governor, failover, capacity) |
| Scripted 100-persona torture | Historical **EXIT 0** — 3,700 requests, 0×5xx; synthetic clients, **not 100 recruited humans** |
| Melious gateway live | Historical 200 responses for four models; keys must be rotated before retesting |
| CI (main) | Historical report only; verify current head and all release gates |

Historical results do not establish production readiness. See [LAUNCH-BLOCKERS.md](LAUNCH-BLOCKERS.md) and [the fresh verification](LAUNCH_VERIFICATION-2026-09-29.md) before deploying.

## Quickstart

```bash
git clone https://github.com/Kartik24Hulmukh/Axiom-Grid.git && cd Axiom-Grid
python3 -m venv .venv && source .venv/bin/activate
pip install -r docker/requirements-runtime.txt   # numpy, pdfplumber, python-docx, and the extraction/OCR stack
make serve          # local overlay API on http://127.0.0.1:8765
```

`make run DOC=... Q="..."` is the grounded-Q&A CLI.

For the focused regression suite: `pip install pytest pytest-asyncio hypothesis httpx ruff psutil` then `make pre-push`.

### Why a Python sidecar

Document intake and the overlay API use Python-native libraries including pdfplumber, python-docx and numpy. The Rust receipt runtime is a separate lane; it does not witness every Python pipeline action. Binary document parsing can run in a resource-limited subprocess. These boundaries do not certify deployment-level network isolation or end-to-end security.

## Receipt verification — runnable today

```bash
# Runtime requirements plus cryptography (already declared in requirements-test.txt)
pip install cryptography
python scripts/axiom_receipts.py verify examples/receipts/sample.json \
  --public-key examples/receipts/sample-public.pem \
  --checkpoint examples/receipts/sample-checkpoint.json
```

The sample is synthetic and ships only an ephemeral signer's public key. See
[export instructions](docs/RECEIPT_ADAPTERS.md) for owner-provisioned keys and
real captured events. No automatic `receipts.jsonl` or unshipped `axiom receipts`
command is promised; not every existing pipeline emits the new receipt format.

## Concurrency posture (preview)

The overlay runs pipelines under bounded admission and native-worker capacity
(`AXIOM_PIPELINE_CONCURRENCY`, default `min(32, 4 x cores)`). Evidence lookup and
review CAS use a separate bounded lane rather than queueing behind parsing.
Shared stores still serialize critical sections and SQLite transactions.
Completion owns the native permit even after cancellation; no throughput or
zero-leak certification follows from this architecture.

The owned-upload preview currently allowlists `.txt`, `.md`, `.pdf`, `.docx` and
`.pptx`; parser dependencies remain required. It is not every engine format on
every operating system, an IAM system, or a native desktop writer.

## Scope

Axiom-Grid's engine **reads** documents (Word, Excel, PowerPoint, PDF, code, email, design) through an extraction pipeline behind admission control and bounded execution, and **suggests** grounded answers with source citations. Receipt export is a separate explicit workflow. It does **not** mutate documents or execute remote writes. Scope is enforced by `tests/test_scope_discipline.py`.

## Scope Boundaries and Platform support

**Axiom-Grid DOES:** READ + SUGGEST ONLY in this engineering preview. It reads
local documents and offers cited suggestions. Explicit receipt export emits verifiable observations.
**Axiom-Grid Does NOT:** ghost-type into live apps or change source documents
through the overlay. No source → no answer: unsupported responses must be refused.
The separate legal-redline CLI produces a new tracked-changes output file,
not an in-place edit of the source. Live computer use and cross-platform desktop
support are experimental, not verified production features.

The runtime includes Python for document parsing, OCR/layout tooling and native
libraries; it is not Rust-only. The overlay install uses
`docker/requirements-runtime.txt` (including numpy, pdfplumber, and python-docx).
Optional model-backed E2E retrieval requires model2vec and its local model;
install test dependencies separately. Verify Linux, macOS, and Windows on the
intended host; a passing Linux focused gate does not certify other platforms.

## OpenBot integration & verifiable benchmark

- **OpenBot receipt adapter** (`integrations/openbot/adapter.py`): every OpenBot agent action emits an Ed25519-signed, chain-linked receipt per the Open Agent Receipt Specification. `python -m integrations.openbot.adapter --emit && --verify`.
- **Verifiable Agent-Action Benchmark** (`bench/verifiable_benchmark.py`): runs real agent tasks (extraction + signing), emits P50/P95/P99 + citation coverage scorecard wrapped in a signed receipt chain. `python bench/verifiable_benchmark.py --tasks 3`.

## License

MIT. AI-generated code and docs are permitted and encouraged.
