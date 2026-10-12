# repos.md - Axiom-Grid open-source tooling catalog (Session 27, 2026-09-16)

Historical capability/tooling catalog, not a current bill of materials or legal clearance.
The default policy excludes AGPL/GPL components such as PyMuPDF and LGPL EbookLib.
The supported PDF stack includes permissive libraries and MPL-2.0 file-level copyleft
(e.g. pikepdf); MPL-2.0 is **not** a permissive license. `deny.toml` governs Rust only,
not Python dependencies or distribution. Direct-manifest guards inspect only declared requirements and local `-r`/`-c` closure,
not installed packages or resolver/transitive closure. Docling, system libraries and
other dependencies may still involve LGPL/MPL or other obligations; none is cleared
by this guard. Binary/model licenses and all runtime imports are also outside it.

Legacy fitz-based sidecar/desktop paths remain **unsupported and blocked for release**
under this policy even after PyMuPDF is removed from default requirements. Some modules
probe fitz at import time inside try/except; other paths import it at call time. Removing
a requirement does not disable those paths in an environment that already has PyMuPDF.
Lazy imports and subprocess boundaries do not establish license clearance. Any future
use requires explicit legal/policy review; there is no default PyMuPDF opt-in manifest.

Legacy KPX EPUB export uses real EbookLib (LGPL-3.0). Its dependency lives only in
`requirements-legacy-epub.txt`, an opt-in manifest requiring legal/policy review before
use or distribution. Existing functionality and tests are retained, not cleared for the
default install. Without EbookLib, `KPXExporter.export_epub` raises
`ModuleNotFoundError` and writes no EPUB; `export_all` records an EPUB `FAILED:` result
but still returns top-level `ok: true` while other exports continue. Thus aggregate
success is not EPUB success, and a broad pass with preinstalled EbookLib cannot attest
clean-default-host EPUB availability. The launch ingestor supports PDF/DOCX/text, not
EPUB. Owners must choose and review a legal/distribution profile: keep this legacy
feature unsupported by default, or explicitly review an optional LGPL-enabled profile;
neither choice nor license approval is supplied here.

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
| HypothesisWorks/hypothesis | MPL-2.0 (file-level copyleft) | property/fuzz vectors for ingress payloads |
| giampaolo/psutil | BSD-3 | RSS floor/ceiling + FD-leak accounting in torture harness |
| hynek/structlog | MIT/APL2 | structured JSON stdout logging reference |
| open-telemetry/opentelemetry-python | APL-2 | distributed tracing spans + traceparent propagation |
| open-telemetry/opentelemetry-python-contrib | APL-2 | FastAPI instrumentation |
| BerriAI/litellm | MIT | reference for multi-model gateway routing/failover |
| pdfminer/pdfplumber | MIT | PDF text+coords read-back oracle; /readyz pdf_parser check |
| py-pdf/pypdf | BSD-3 | PDF merge/split/metadata |
| pypdfium2/pypdfium2 | Apache-2.0 OR BSD-3-Clause (bindings); BSD-3-Clause + third-party notices (PDFium) | PDF render/raster; check version-specific bundled notices |
| pikepdf/pikepdf | MPL-2.0 (file-level copyleft) | supported PDF redaction/forms/encryption dependency; not permissive |
| MatthiasValvekens/pyHanko | MIT | PAdES sign+verify oracle |
| tehmoon/reportlab (reportlab) | BSD-3 | fixture generation |
| python-openxml/python-docx | MIT | DOCX create/edit/read-back; /readyz docx_parser check |
| openpyxl/openpyxl | MIT | XLSX oracle |
| scanny/python-pptx | MIT | PPTX oracle |
| ebooklib/ebooklib | LGPL-3.0 (copyleft; not permissive) | legacy KPX EPUB export; legal-review-only opt-in, unavailable without dependency |
| mikedell/mammoth (mammoth) | BSD-2 | DOCX->text cascade |
| jimmycallin/striprtf | MIT | RTF strip |
| odfpy/odfpy | APL-2 | ODF intake |
| duckdb/duckdb | MIT | data/analytics SQL oracle |
| numpy/numpy | BSD-3 | numeric verification baselines |
| python-pillow/Pillow | MIT-CMU / historical HPND (version-specific) | image hashing/render diffs; verify installed-version notices |
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
- Historical lane check only: no AGPL imports were added in that session. This does **not** establish repository-wide PyMuPDF absence: legacy sidecar/desktop fitz paths remain a blocked wider-product issue.
