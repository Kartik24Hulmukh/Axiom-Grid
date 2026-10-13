# Focused skipped-coverage review

## Outcome and boundary

Starting checkpoint: `e2b9d42`, isolated `council/coverage-v5` worktree. Two of the four original broad-suite skips are now executable local checks: actual LibreOffice formula recomputation and an owned generated PDF AcroForm exercised through the real production PDF engine. The release training asset and cross-platform workflow remain blocked and their original skip guards are unchanged.

Final **focused** run: **21 passed, 2 skipped in 3.55s**, with ResourceWarning and pytest unraisable warnings promoted to errors. This is not a rerun or inferred new total for the prior 1,466-pass broad suite. No models, training, broad suite, load producer, human accessibility evaluation, remote CI or external service was exercised.

## Frozen baseline and disposition

The supplied `broad-final.log` reports `1466 passed, 4 skipped` but does not enumerate skip reasons (it lacks `-rs`). The exact four targets were therefore replayed before editing: **4 skipped in 2.42s**. Baseline source/dependency hashes are in `environment-baseline.json`; the exact reasons are in `baseline.log` under `/data/axiom-fifth/evidence/coverage/`.

| Original target | Original reason | Disposition and proof |
| --- | --- | --- |
| `tests/test_acceptance_gauntlet.py::TestExcelDomain::test_excel_formula_values` | `LibreOffice not available — honest degradation` | **Closed locally.** LibreOffice 26.8.0.3 was already installed. Replaying the swallowed exception proved conversion had succeeded, then `.items()` failed on a function supplied where the oracle requires a dictionary. The original code also expected `.passed` on a boolean. The test now supplies independent arithmetic expectations (300, 600), asserts the boolean oracle, and independently reads actual cached values. Only `LibreOfficeUnavailableError` still skips; conversion failures and assertions propagate. A real wrong expectation (301 vs 300) fails the oracle, and three injected exception-class checks prove assertion/runtime/API errors are not skips. Injected exceptions are guard tests, not converter fault simulations. |
| `tests/test_acceptance_gauntlet.py::TestPDFDomain::test_pdf_form_fill_and_readback` | `PDF form fixture not available in this env — honest degradation` | **Closed with optional isolated dependency.** ReportLab generates an owned two-text-field AcroForm; pikepdf production fill/readback runs on it; independent pypdf reads saved values; original bytes remain unchanged. The existing production `pdf_form_readback` oracle passes the satisfiable request and rejects a partly satisfiable request containing a nonexistent field. No writer/reader is mocked. Without pikepdf, the same original target remains an explicit dependency skip, proven separately. This tests PDF field values, not appearance rendering, flattening, arbitrary external forms, or signatures. |
| `tests/test_writing_dataset.py` (collection-time skip) | `training_data dataset ships as a release asset — see RELEASING.md` | **Blocked, unchanged.** `training_data/kairo_writing_dataset_5k.jsonl` is absent. The referenced `RELEASING.md` is also absent here. No authoritative asset/checksum/location was supplied; no 5,000-row replacement was generated. The original validator also refers to `pytest.fail` without importing pytest on its invalid-JSON path; this dormant issue is documented, not represented as tested release validation. Requires owner-provided actual asset plus provenance/integrity verification. |
| `tests/test_cross_platform_honesty.py::TestCrossPlatformWorkflow::test_cross_platform_workflow_triggers_on_master` | `cross-platform.yml not found` | **Blocked, unchanged.** `.github/workflows/cross-platform.yml` is absent (only `axiom.yml` and `launch-evidence.yml` exist). No dummy/proposed workflow was authored just to satisfy string checks. A real approved workflow and branch-trigger decision are needed; Linux static claim/configuration tests cannot certify Windows UIA, macOS AX permissions/ghost typing, Linux AT-SPI desktop actions, signing or actual multi-platform CI execution. |

## Dependency/tool review

No catalog tool was added: the catalog's browser, load, orchestration and OCR products do not satisfy these narrow oracle contracts. Reused installed LibreOffice, ReportLab, openpyxl and pypdf. The missing pikepdf is already declared in `requirements-test.txt` (`>=9.0.0`); installed only into `/data/axiom-fifth/coverage-venv`, never the shared supplied venv or application source.

Pinned optional wheel: **pikepdf 10.16.0**, CPython 3.13 / Linux x86_64 manylinux, SHA-256 `e716fa800b4213a385084923ca75001fd107eed8ad29ea60ce4a3ad7c9a960b1`. Public PyPI digest matched downloaded bytes before installation; metadata declared MPL-2.0. The wheel's actual MPL-2.0 license and bundled-library notice mapping were inspected before committing the integration. qpdf runtime reports 12.4.2 (Apache-2.0); libjpeg-turbo notices include IJG/BSD/Zlib; the GPL/GCC-exception notice files are mapped to musllinux runtime bundles, not the selected manylinux wheel. PDF/A data notices also include CC-BY-4.0, MIT and Zlib. This is an unmodified test dependency, not a legal opinion or a redistributed runtime guarantee. LibreOffice's installed license is MPL-2.0 with third-party notices; installed executable/license hashes were recorded, not attested against an upstream signed release.

Environment: Python 3.13.14, Linux x86_64 glibc 2.34; pytest 9.1.1, openpyxl 3.1.5, ReportLab 5.0.1, pypdf 6.19.0, Pillow 12.3.0, lxml 6.1.3, packaging 26.3. Exact import paths/versions are in `environment-final.json`.

## Replay

From repository root, use the supplied interpreter with the optional dependency overlay (the separate venv itself has no pytest):

```bash
PY=/data/axiom-third/venv/bin/python
DEP=/data/axiom-fifth/coverage-venv
# For a fresh isolated overlay, run these two setup commands explicitly:
"$PY" -m venv --system-site-packages "$DEP"
"$DEP/bin/python" -m pip install --no-deps --only-binary=:all: --require-hashes \
  -r tests/support/coverage-pikepdf-linux-cp313.lock

soffice --version
PYTHONPATH="$DEP/lib/python3.13/site-packages:$PWD" "$PY" -c \
  'import pikepdf, reportlab, pypdf, openpyxl; print(pikepdf.__version__, pikepdf.__libqpdf_version__)'
PYTHONPATH="$DEP/lib/python3.13/site-packages:$PWD" "$PY" -m pytest -q -rs \
  -W error::ResourceWarning -W error::pytest.PytestUnraisableExceptionWarning \
  tests/test_coverage_skip_guards.py \
  tests/test_acceptance_gauntlet.py::TestExcelDomain \
  tests/test_acceptance_gauntlet.py::TestPDFDomain \
  tests/test_writing_dataset.py tests/test_cross_platform_honesty.py
```

The lock is intentionally wheel/platform-specific; the broader original dependency requirements are not rewritten. The host must already provide Pillow/lxml/packaging; `--no-deps` deliberately prevents uncontrolled dependency upgrades. The optional setup downloads one public wheel, not credentials or training data. An offline replay can install the retained verified wheel with `--no-deps --no-index` instead.

To verify missing dependency honesty, omit the overlay and run the four original targets with the supplied interpreter: result **1 passed, 3 skipped in 1.15s** (Excel passes; PDF explicitly requires pikepdf; the two external blockers remain).

## Evidence, cycles and scope discipline

Evidence directory: `/data/axiom-fifth/evidence/coverage/`:
- `baseline.log`, `environment-baseline.json`, `excel-original-exception.log` freeze reasons, source/tool hashes and the swallowed API error.
- `cycle1-path-corrected.log`: 4 passed, 2 skipped on the narrow edited targets plus PDF negative oracle.
- `final-focused.log`: 21 passed, 2 skipped, strict resource warning settings.
- `without-pikepdf.log`: no optional overlay, dependency skip retained.
- `pikepdf-pypi.json`, verified wheel, installation log, extracted licenses/notices, `environment-final.json` retain dependency provenance.
- Retained harness mistakes: `baseline-selector-error.log` used nonexistent shortened class names (no tests ran); `cycle1.log` used the separate dependency venv directly (no pytest). Neither is a test pass. Initial new-module lint found unsorted standard-library imports; fixed by import-only edit, with no runtime change.

One source-changing cycle for acceptance this session. Conservatively counting all earlier committed edits, including initial creation (`f977b31`, `642a3de`, `b2b107e`), this is its fourth historical source revision, not a reset to zero. New guard module: initial implementation plus import-only lint fix, two cycles. Cross-platform and training modules: zero changes this session; original skips retained. No further remediation iterations are planned. Small final replay follows the import-only fix.

Only acceptance tests, the new focused guard module, optional test lock and this review changed. No server/admission/store/gateway/frontend/native load producer, CI workflow or `ci/pre-push.sh` changed. No credentials, remote mutations, pushes or installations into the shared test venv.

Manual accessibility opportunity is **outside scope and unexecuted**: previous checkpoint reports serious color-contrast incomplete nodes and pending keyboard/screen-reader/human checks. Record those boundaries; do not convert axe incompletes or this coverage work into an accessibility pass.
