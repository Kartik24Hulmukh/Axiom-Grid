# Release intake audit — 15 September 2026

Baseline main: `b2b107e`. PRs #20 and #21 are already merged; baseline main's
four Actions jobs were completed/success when queried. This is not production certification.

## Reproduced defects and changes

* Compressed text PDFs could fall through missing Docling/PyMuPDF into UTF-8
  decoding of binary bytes. Malformed PDFs and missing DOCX parsers could be
  reported as document text. Three new regressions were red before this patch.
* Launch PDF parsing now uses local MIT pdfplumber, with measured page text
  bounds and closed handles. No Docling model loading or AGPL fitz fallback.
  Invalid and image-only PDFs fail explicitly; missing DOCX parser fails closed.
* Binary extraction classification previously decoded container bytes. PDF/DOCX
  classification now uses actual parsed text under the bounded pipeline guard.
  This currently parses binary documents twice; optimize only with provenance
  and regression coverage. Unsupported/malformed binary input returns 422.
* Container dependencies now include the parsers; CI exercises authenticated
  compressed PDF and DOCX extraction on the built read-only, non-root image,
  rather than only synthetic text readiness and fail-closed authentication.
* `make serve` actually serves the overlay; `make run` remains the existing CLI.
  README no longer prescribes an incomplete inherited dependency list or
  advertises XLSX/PPTX intake as supported by this path.
* Local pre-push now includes concurrency and both corpus suites.

## Qualification limits / NO-GO for broad production

`SpendGovernor` is explicitly process-local and estimates tokens; settlement
can exceed reservation. It is NOT a durable fleet-wide monetary limit. The
attached prior final report's guarantee is contradicted by implementation.
`/readyz` caches a successful text probe indefinitely, not PDF/model readiness.
The overlay forces deterministic gateway test mode; it is not live-model E2E.
PDF bounds cover page text; DOCX layout is estimated. No renderer or OCR claim.
No production load generator, signed installer, native platform matrix, staging
credentials, customer evidence or model-provider credentials were provided.
Do not tag a production release or waive these gates on focused CI success.

Rotate exposed GitHub/provider credentials before launch. Do not put replacement
credentials in prompts, URLs, committed files or logs.
