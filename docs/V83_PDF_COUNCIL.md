# V8.3 PDF fail-closed candidate — final frozen handoff

## Outcome and exact commit

Validated and committed **only the exhausted-final-fallback guard** plus an isolated real-profile harness.

- Base: `31277e8b1a4ae0ef529101e67ea63e52340d17c2`.
- Commit: `66de325fb6bdd81a79a305f2efb96790e4f5fbd8`.
- Branch: `harden/axiom-v83-pdf`.
- Isolated worktree: `/data/axiom-v83-pdf`; clean after commit.
- Shared `/data/axiom-integration` remains clean at base `31277e8`.
- Scope: exactly TWO tracked files: engine + NEW `tests/profile/pdf_absent_engine_guard.py` (78 lines). No old tests/skips, dispatchers, masters, requirements, docs, installers, servers, or diagnostics changed.
- Engine source history is now **5/5; FROZEN**. One source revision and ONE implementation/narrow-validation cycle consumed. No second cycle, retries, renamed runtime wrapper, or budget reset. The new file is a test-only caller of the original engine, not a replacement parser or runtime layer.

## Preflight (performed before engine edit)

Both existing interpreters `/data/axiom-minvenv/bin/python` and `/data/axiom-venv/bin/python` were inspected with `-I`, standard-library `importlib.metadata.version` and top-level `importlib.util.find_spec`:

| Module | Distribution checked | Both provisioned profiles |
| --- | --- | --- |
| `fitz` | `PyMuPDF` | Distribution absent; spec None |
| `opendataloader` | `opendataloader` | Distribution absent; spec None |
| `olmocr` | `olmocr` | Distribution absent; spec None |
| `surya` | `surya-ocr` | Distribution absent; spec None |
| `pdfplumber` | `pdfplumber` | 0.11.10; actual installed package spec |

No optional modules were imported in preflight. The selected execution interpreter was **axiom-minvenv**, unchanged for baseline and validation. The harness also rejects installed `PyMuPDFb` or `opendataloader-pdf` distributions, and rechecks actual module discoverability after adding repository import paths. Wrong profiles hard-fail before production imports; they never skip or monkeypatch engine availability.

Static source safety inspection: engine module imports only stdlib (`pdf_extraction_engine.py:13–24`); sidecar package initializer is a comment. Missing optional roots make constructor probes false; language/word estimation and fitz fallbacks perform genuine failed imports. Surya exits before any model loader when absent. No installed model-capable optional engine can be reached in this profile. This is concrete source/profile evidence, not syscall-level egress instrumentation. No network blocker/import interceptor was installed or used to manufacture an absent profile.

## Retained baseline — real defect, not dropped

Command before engine edit, from isolated worktree:

```
/data/axiom-minvenv/bin/python -I tests/profile/pdf_absent_engine_guard.py
```

Full original output retained at `/data/axiom-v83-pdf-baseline.log`; exit **1**; **3 tests ran: 2 failed, 1 passed**.

- Owned `fixtures/pdf/s01_born_digital_report.pdf`: real engine returned `text=''`, `tier=None`, `confidence=0.1`, warning “All extraction tiers failed; raw fallback used.” Failure: `RuntimeError not raised`.
- Owned `fixtures/pdf/s03_scanned_contract.pdf`: identical false-success result; same missing RuntimeError failure.
- Separate supported real `kairo.pdf.engine.extract_text_with_coords` via pdfplumber passed on the born-digital fixture: **768 extracted characters, 104 measured word boxes**.

These are frozen baseline regression failures. The harness itself was not revised between baseline and validation. No fabricated parser output, availability flag substitution, mocks, import interception, installer, models, services, named-pipe handler, provider, or remote call was used.

## Exact production change

`kairo-sidecar/sidecar/parsers/pdf_extraction_engine.py:241–246` now obtains the unchanged real final fallback, then rejects empty/whitespace content before constructing any fallback result:

```python
fallback_text = self._fallback_extract(file_path)
if not fallback_text.strip():
    raise RuntimeError(
        "Legacy PDF extraction unavailable or failed: no extraction tier produced text."
    )
```

Four lines added. Nonempty fallback behavior, routing, engine probes, thresholds, and supported independent PDF engine are unchanged. Error wording does not instruct installing prohibited fitz and does not falsely distinguish missing dependency from an otherwise failed extraction.

## ONE narrow cycle — successful and now frozen

Same interpreter and unmodified harness command above. Full output `/data/axiom-v83-pdf-cycle1.log`.

- **3 tests passed**, no skips; exit **0**.
- Born-digital and scanned fixtures each raised the required descriptive RuntimeError from the actual original engine with actual absent optional engines.
- Supported independent pdfplumber positive remained **768 characters / 104 measured boxes**, with nonempty text, valid box ordering/nonnegative pages, and no optional-engine module imported.
- Syntax parsing/compilation (without module execution) passed for the engine and harness.
- `git diff --check` passed.
- Empty-string behavior was exercised at runtime. Whitespace rejection was verified structurally in source (`if not fallback_text.strip()`), **not by injecting whitespace parser output**. No fake successful parser or dependency restoration was used for a positive legacy fallback case.

No lint, full suite, pikepdf form/redaction suite, benchmark, load test, services, server transport, model, provider, remote CI, merge, publication, push, or downloads were run. Commit uses an explicitly scoped automation identity, not the user's Git identity.

## Consumer evidence and unresolved scope

Static-only propagation: unchanged `sidecar/main.py:584–603,665–678,680–701` calls `engine.extract()` for extract/table/summarize inside the shared try; `:1250–1252` converts raised exceptions to `ok:false`. Named-pipe responses were **not executed**, and this is not end-to-end API certification.

The earlier `/data/axiom-v83-pdf-audit.md` remains the wider source audit. This candidate does NOT fix:

- `sidecar/main.py:97–105,235–245`: import-only `domain_4_pdf` capability reporting; main is already capped at five history revisions.
- `sidecar/masters/other_masters.py:670–699`: high-confidence default context / catch-and-return / “PyMuPDF” fallback label; capped at five revisions. After this exception change the master can still hide the failure.
- Missing-file metadata-only result (`pdf_extraction_engine.py:164–169`), wrong successful tier attribution, placeholder OCR text, or already-installed fitz use.
- Figure helper's absent-fitz empty-list result and overlay's success-shaped zero figures.
- License/profile decisions, dual-reader oracle availability, remaining legacy router/Docling/MinerU behavior, supported pikepdf parity, or release-wide launch gates.

The inherited license lane remains frozen 2/2. Reserved installer/docs/diagnostics/server budgets remain untouched; diagnostics5/5 and server4/helper1 accounting is not reset. Parent owns independent review, broad gates, integration and publication. **Do not edit/retest this engine again within its exhausted 5/5 budget.**
