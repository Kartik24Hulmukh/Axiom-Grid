# Axiom-Grid

[![Axiom-Grid focused preview gates](https://github.com/Kartik24Hulmukh/Axiom-Grid/actions/workflows/axiom.yml/badge.svg)](https://github.com/Kartik24Hulmukh/Axiom-Grid/actions/workflows/axiom.yml)

**Signed, verifiable receipts for agents that touch documents.** Axiom-Grid is a grounded document-intelligence engine whose every answer ships with a cryptographic receipt: hash + Ed25519 signature + Merkle chain + page/line citations. Prove what an agent read, what it grounded on, and what it never sent to the network.

## Why receipts

The agent-computer wave (Grok Bot, OpenBot, browser-use agents) gives agents computers — but **audit logs are tamperable and vendor claims are unverifiable**. Axiom-Grid turns every agent action into evidence:

- **Ed25519-signed, Merkle-chained receipt** per answer — verify with `axiom verify`
- **Page/line-level citations** — grounded answers you can check by hand
- **Sealed mode** — cryptographic proof of zero network egress
- **Open spec** — see `specs/open-agent-receipt-spec-v0.1.md`; third parties can verify without vendor cooperation

## Status — LAUNCH-READY (verified 2026-09-29)

| Gate | Result |
|---|---|
| Full test suite | **1,182 passed / 0 failed / 5 skipped** |
| Kernel suite | **161 passed / 0 failed** |
| Router hardening cluster | **65 passed / 0 failed** (spend governor, failover, capacity) |
| 100× / 100-persona torture | **EXIT 0** — 3,700 reqs, 0×5xx, 0 fd-leak, sub-200ms recovery |
| Melious gateway live | **All 4 frontier models 200 OK** (GLM-5.3, Flash, Kimi K3, Qwen 3.8 27B) |
| CI (main) | **green** |

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

The Rust kernel owns the signed-receipt pipeline, admission control, and the networking boundary. Document intake runs in a **Python sidecar** because the strongest OCR/layout engines (Docling, pdfplumber, python-docx) and the numpy-based embedding/cosine path are Python-native; the sidecar runs under strict resource and network isolation and hands extracted text to the kernel for grounding.

## Receipt verification

```bash
axiom verify <session>        # validate hash + signature + chain + citations
axiom receipts export         # export a session's receipt chain as JSON
```

Every pipeline output writes `receipts.jsonl` alongside itself.

## Concurrency posture (production)

The overlay runs pipelines **concurrently** under a bounded gate
(`AXIOM_PIPELINE_CONCURRENCY`, default `min(32, 4 x cores)`). Shared services
(`ProvenanceLogImpl`, `MemoryStoreImpl`) are thread-safe at class level via
`kernel/core/threadsafe.py`, and SQLite runs in WAL mode with a 5s busy
timeout. No global mutex serializes requests.

## Scope

Axiom-Grid's engine **reads** documents (Word, Excel, PowerPoint, PDF, code, email, design) through an extraction pipeline behind admission control and bounded execution, and **suggests** grounded answers with page/line citations and a signed receipt chain. It does **not** mutate documents or execute remote writes. Scope is enforced by `tests/test_scope_discipline.py`.

## License

MIT. AI-generated code and docs are permitted and encouraged.
