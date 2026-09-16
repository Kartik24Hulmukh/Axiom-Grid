# repos.md - Axiom-Grid open-source tooling catalog (Session 27, 2026-09-16)

Living catalog of permissive-licensed OSS repos used to close functional gaps during
real-human hardening. AGPL/GPL components (e.g. PyMuPDF) are BANNED per deny.toml.

| Repo | License | Role in Axiom-Grid hardening |
|---|---|---|
| encode/fastapi | MIT | ASGI ingress app under torture (overlay/server.py) |
| encode/uvicorn | BSD-3 | Real TCP ASGI server for 100x burst + persona runs |
| encode/starlette | BSD-3 | middleware primitives (body limit, CORS) |
| pydantic/pydantic | MIT | strict ingress schema validation (422 fail-closed) |
| encode/httpx | BSD-3 | TestClient transport for unit/integration suites |
| pytest-dev/pytest | MIT | unit + integration suites (185 overlay, 33 router) |
| pytest-dev/pytest-asyncio | MIT | async endpoint tests |
| pytest-dev/pytest-xdist | MIT | parallel suite execution |
| HypothesisWorks/hypothesis | MPL-2.0 | property/fuzz vectors for ingress payloads |
| giampaolo/psutil | BSD-3 | RSS floor/ceiling + FD-leak accounting in torture harness |
| hynek/structlog | MIT/APL2 | structured JSON stdout logging reference |
| open-telemetry/opentelemetry-python | APL-2 | distributed tracing spans + traceparent propagation |
| open-telemetry/opentelemetry-python-contrib | APL-2 | FastAPI instrumentation |
| BerriAI/litellm | MIT | reference for multi-model gateway routing/failover |
| pdfminer/pdfplumber | MIT | PDF text+coords read-back oracle; /readyz pdf_parser check |
| py-pdf/pypdf | BSD-3 | PDF merge/split/metadata |
| pypdfium2/pypdfium2 | BSD-3 | PDF render/raster (PDFium) |
| pikepdf/pikepdf | MPL-2.0 | true redaction, forms, encryption |
| MatthiasValvekens/pyHanko | MIT | PAdES sign+verify oracle |
| tehmoon/reportlab (reportlab) | BSD-3 | fixture generation |
| python-openxml/python-docx | MIT | DOCX create/edit/read-back; /readyz docx_parser check |
| openpyxl/openpyxl | MIT | XLSX oracle |
| scanny/python-pptx | MIT | PPTX oracle |
| ebooklib/ebooklib | LGPL-3.0 | EPUB intake (env-gap flagged in SKIPS.md) |
| mikedell/mammoth (mammoth) | BSD-2 | DOCX->text cascade |
| jimmycallin/striprtf | MIT | RTF strip |
| odfpy/odfpy | APL-2 | ODF intake |
| duckdb/duckdb | MIT | data/analytics SQL oracle |
| numpy/numpy | BSD-3 | numeric verification baselines |
| python-pillow/Pillow | MIT | image hashing/render diffs |
| networkx/networkx | BSD-3 | knowledge-graph domain |
| tree-sitter/tree-sitter + tree-sitter-python | MIT | code-domain parse oracle |
| apache/arrow (pyarrow) | APL-2 | parquet/columnar fixtures |
| beautifulsoup4 | MIT | HTML form/read-back parsing |
| pyca/cryptography | APL/BSD | Ed25519 audit chain, secrets handling |

## Session-27 integration log
- fastapi+uvicorn+psutil: live 100x TCP torture (healthz 1000@100c 0x5xx; fuzz 600@100c 0x5xx; 100-persona 2500 req 0x5xx; error recovery P99 3.2 ms < 200 ms SLO).
- pdfplumber+python-docx: closed /readyz dependency gap (4 overlay tests flipped red->green; suite 185/185).
- pytest/pytest-asyncio/httpx: overlay 185 passed, kernel router/spend-governor 33 passed.
- litellm-pattern router (kernel/sidecar/melious_router.py): live-verified 4/4 Melious routes (glm-5.3, glm-5.3-flash, kimi-k3, qwen-27b) HTTP 200 with real bearer key; spend-governor ceiling enforced (SpendCeilingError at 200-token cap, committed=47 at 100k cap).
- BANNED check: no AGPL imports added; PyMuPDF absent from runtime path.
