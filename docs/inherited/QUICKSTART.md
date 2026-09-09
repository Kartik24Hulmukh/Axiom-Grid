# Kairo Phantom v2.2 — Quick Start

## 3-Step Install

```bash
# 1. Clone
git clone https://github.com/KairoPhantom/Kairo-Phantom.git
cd Kairo-Phantom

# 2. Install dependencies
pip install -r requirements.lock

# 3. Verify
python -m bench.blind_bench  # should show 100% grounded, BLIND GATES: GREEN
```

## 5-Step Integration for Document Managers

### 1. Start the API server

```bash
python -m overlay.server  # starts FastAPI on :7438
```

### 2. Extract fields from a document

```bash
curl -X POST http://localhost:7438/api/extract-document \
  -H "Content-Type: application/json" \
  -d '{"file": "path/to/invoice.pdf"}'
```

Response includes every field with `value`, `grounded`, `bbox`, `cascade`, `confidence`, and `source_link`.

### 3. Ask a question

```bash
curl -X POST http://localhost:7438/api/ask-document \
  -H "Content-Type: application/json" \
  -d '{"file": "path/to/contract.pdf", "question": "What is the effective date?"}'
```

Returns the answer with bbox, or a refusal if no grounded answer exists.

### 4. View the grounding trace dashboard

Open `http://localhost:7438/dashboard` in your browser. See live cascade decisions, confidence per layer, and stats.

### 5. Query the knowledge graph

```bash
curl -X POST http://localhost:7438/api/graph/query \
  -H "Content-Type: application/json" \
  -d '{"keyword": "Delaware"}'
```

Returns all entities matching "Delaware" with bbox provenance across documents.

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/extract-document` | POST | Extract fields with grounding metadata |
| `/api/ask-document` | POST | Q&A with bbox or refusal |
| `/api/source/{doc_id}` | GET | Render page with bbox highlight |
| `/api/figures/{doc_id}` | GET | Get figures from a document |
| `/api/graph/query` | POST | Query the knowledge graph |
| `/api/graph` | GET | Get full graph for visualization |
| `/api/traces` | GET | Get recent grounding traces |
| `/api/traces/stats` | GET | Get aggregate trace statistics |
| `/api/eval/report` | GET | Get eval report with alerts |
| `/api/compression/stats` | GET | Get compression statistics |
| `/dashboard` | GET | Live grounding trace dashboard |

## Document Packs

| Pack | Fields | Use Case |
|---|---|---|
| Invoice | vendor_name, invoice_number, dates, amounts, line_items | AP automation |
| Contract | parties, dates, governing_law, obligations | Contract analysis |
| Paper | title, authors, abstract, methods, figures | Research extraction |
| Generic | summary, key_claims, entities, topics | Any document |

## Configuration

```bash
# Air-gap mode (default — zero network)
export KAIRO_GATEWAY_TEST_MODE=true

# With local LLM (Ollama)
ollama pull llama3.2
# Tier 1 uses localhost:4000 (LiteLLM proxy)

# With cloud reasoner (opt-in, breaks air-gap)
export OPENAI_API_KEY=sk-...
# Tier 3 uses OpenAI API
```

## Reproducing the blind benchmark

```bash
sha256sum -c bench/corpus/blind/v1/CHECKSUMS.sha256  # verify corpus integrity
python -m bench.blind_bench --output bench/REPORT_blind.json
```

The blind bench runs on 120 real documents (30 per pack, tier-balanced). No GPU required — the cascade is deterministic Python.