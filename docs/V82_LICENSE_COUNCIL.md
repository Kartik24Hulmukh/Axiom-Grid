# Axiom-Grid V8.2 isolated license/dependency review

## Frozen handoff

- Base: `27e9f8e0854b9d8b00ac64162d686d2fb7b791d5`.
- Worktree: `/data/axiom-v82-licenses` (created locally because the requested path did not exist).
- Branch: `harden/axiom-v82-licenses`.
- Atomic commit 1: `71db6f2c3e27529c55ef5f881d40036a0ddffd37` — `fix(licenses): exclude blocked default dependencies and guard manifests`.
- Atomic commit 2 (parent-requested final narrow cycle): `d6bf1b156b7e3f3ee2a78d9ac90f7d7c1878bb0d` — `test(licenses): verify missing EbookLib degradation and document profile gate`.
- Repository clean at final handoff. Implementation frozen after TWO implementation/narrow cycles. The second was explicitly requested by parent for missing-EbookLib behavior/profile evidence. No further implementation cycles remain.
- Parent owns integration/cherry-pick, fullsuite, CI, distribution review and PR. No remote mutation performed.

## Review and findings

Reviewed `repos.md`, `THIRD_PARTY_NOTICES.md`, root requirements text files and `requirements.lock`, sidecar requirements, container/PDF-domain manifests, actual parser imports, installer references (read-only), old license tests/skips and path-specific git history before edits.

1. `kairo-sidecar/requirements.txt` unconditionally required `PyMuPDF>=1.23.0` despite the stated exclusion policy. Both platform installers reference this manifest. Removing only this requirement fixes that direct default-install contradiction; it does not disable surviving fitz paths.
2. `requirements-test.txt` required LGPL EbookLib, and `install.sh` installs that manifest in its default path. The catalog's permissive-only framing was therefore not just a catalog wording issue. EbookLib was moved, not deleted, to the explicit legal-review-only `requirements-legacy-epub.txt` opt-in. No installer file or installer documentation was changed.
3. pikepdf and Hypothesis are MPL-2.0 file-level copyleft, not permissive. The policy/catalog framing now acknowledges that distinction while retaining supported PDF dependencies. `deny.toml` governs Rust; it is not a Python dependency/distribution audit.
4. Blanket MIT compatibility, repository-wide PyMuPDF absence, and automatic subprocess/lazy-import legal exemption statements in the scoped notices/catalog were corrected. No legal clearance is asserted.
5. Local metadata was read without importing packages or downloading anything: existing Pillow 12.3.0 declares MIT-CMU; existing pypdfium2 5.13.0 declares BSD-3-Clause, Apache-2.0 and dependency licenses; Hypothesis declares MPL-2.0. Catalog entries distinguish version-specific Pillow notices and Python bindings/PDFium bundled notices. These observations are not a full upstream or transitive license audit.

## Exact committed scope

- `kairo-sidecar/requirements.txt`: remove banned default PyMuPDF requirement; comments explain unsupported residual fitz paths.
- `requirements-test.txt`: separate LGPL EbookLib opt-in; correct PDF-stack framing.
- `requirements-legacy-epub.txt`: new isolated real EbookLib dependency with legal-review-only warnings; not included by default manifests.
- `requirements.lock`: correct historical preinstalled PyMuPDF inventory wording; clarify that it is not an exhaustive resolved lock. No active requirements altered.
- `repos.md`: correct policy/catalog framing and legacy path status.
- `THIRD_PARTY_NOTICES.md`: scoped PDF/EPUB license/status corrections and removal of blanket clearance statements.
- `tests/test_default_dependency_policy.py`: new offline static guard and negative regression fixtures.
- `tests/test_legacy_epub_dependency_boundary.py`: parent-requested focused real-exporter missing-import negative tests; no engine substitution.

No pre-existing test or skip changed. No parser/engine, pipeline, model, provider, server, kernel, installer, installer documentation, CI, runtime container manifest or supported PDF-domain manifest changed. No source transplant, dependency installation/download, workloads, server/model execution, provider calls, credentials/secrets, or remote mutation. Cycle 2 exercised only the existing local exporter on tiny temporary text in an isolated subprocess, with EbookLib import deliberately rejected as parent requested.

## Narrow validation

Commands run in the isolated worktree:

- `python tests/test_default_dependency_policy.py -v`: **9 tests passed** (stdlib-only).
- `/data/axiom-minvenv/bin/python -m pytest tests/test_default_dependency_policy.py -q`: **9 passed, 44 subtests passed**, 0.25 seconds.
- `git diff --check`: passed.
- Independent regression proof using `git show 27e9f8e:<manifest>` in temporary files: new guard correctly rejected the baseline sidecar requirement for `pymupdf` and baseline test manifest for `ebooklib`.
- Exact changed/untracked path-set assertion before commit: matched the seven scoped files only.
- `git status --short` after commit: clean.

Logs:
- `/data/axiom-v82-license-guard-cycle1.log`
- `/data/axiom-v82-license-pytest.log`

The new guard examines 19 current default/root/domain/MCP/container manifest roots and follows local `-r`/`--requirement` and `-c`/`--constraint` closures. It checks case-normalized distribution names, extras, markers (even platform-conditional requirements), named direct URLs, inline comments, continuations, known PyMuPDF wrappers/companion packages, and the segregated EbookLib manifest. Negative fixtures verify that comments about lazy/optional use do not excuse an active requirement and that cycles, missing includes, outside-root paths, remote includes, unnamed URLs/editables, unsupported flags and unfinished continuations fail closed. It also asserts that real pdfplumber remains declared for overlay intake and real pdfplumber/pikepdf/pypdfium2/pypdf remain declared in the test and PDF-domain stacks.

This guard does not resolve dependencies, read URL payloads, verify package authenticity, audit transitive licenses, establish arbitrary-package legal acceptability, inspect all future installer commands, or prevent an already installed PyMuPDF from being invoked. Its passing result is only direct-manifest policy evidence, not release clearance.

## Wider-product blockers remain OPEN

**Optional fitz implementations were retained and are not declared closed.** Examples under `kairo-sidecar/`:

- `sidecar/parsers/pdf_parser.py`
- `sidecar/parsers/pdf_extraction_engine.py`
- `sidecar/parsers/mineru_parser.py`
- `sidecar/parsers/markitdown_bridge.py`
- `sidecar/oracles.py`
- `sidecar/multi_doc_context.py`

In particular, `mineru_parser.py` and `oracles.py` have module-import-time try/except probes, not solely call-time imports. Already installed PyMuPDF can still be found and used. Some legacy code and tests claim lazy importing preserves a licensing boundary; those out-of-scope source assertions remain an integration/legal-review issue. Other desktop/legacy references and wider distributions need their own reviewed audit.

- Legacy PDF paths are unsupported/blocked under the default policy until reviewed remediation or explicit reviewed policy/licensing decisions. No replacement parser or mock engine was supplied.
- Supported `kernel/sidecar/ingestor.py` real pdfplumber intake and `kairo/pdf/engine.py`/PDF-domain real pikepdf functionality are untouched. The narrow lane did not rerun real-engine or fullsuite tests, so no runtime parity claim is made.
- Existing hard PyMuPDF expectations remain, including `kairo-sidecar/tests/test_sprint5_hardening.py`'s explicit `import fitz` assertion and historical requirement comments. This lane did not modify, skip or weaken them. Parent must record resulting missing-dependency failures honestly; they are not fixed by static guards.
- Legacy KPX EPUB export and real EbookLib tests remain. Default installation intentionally no longer provisions EbookLib; tests/calls requiring it may fail without a separately reviewed opt-in. No skip or mocked export was introduced. No approval to install/distribute it is granted by the opt-in manifest.
- Existing skips such as the PyMuPDF policy skips in `kairo-sidecar/test_domain4_pdf.py` and oracle tests are unchanged. Fullsuite belongs to parent.
- The existing sidecar manifest is not asserted to be a complete dependency inventory; platform-specific missing dependencies and resolved/transitive distributions still need parent validation.

## Revision budget

Path-specific history was checked for the manifest/docs edits and the new guard path before implementation. The guard path had no prior history. There were no failing narrow test modules and no changes to old failing test modules; the new guard received one source revision in one atomic commit. No iterative failure-fixing loop or module revision-cap override was used. Initial repository path discovery errors were tooling/setup errors, not module failures or source revisions.

## Parent integration

Cherry-pick `71db6f2c3e27529c55ef5f881d40036a0ddffd37` and then `d6bf1b156b7e3f3ee2a78d9ac90f7d7c1878bb0d` locally when ready. Review the new LGPL opt-in separation against the parent-owned installer-documentation lane; do not re-add it to a default requirements chain merely to make legacy tests green. Run parent-owned fullsuite/CI and publish an honest residual fitz/EPUB distribution blocker statement. No fullsuite success, product-wide absence of AGPL, or legal clearance is claimed here.


## Final cycle 2: actual missing-EbookLib behavior and owner decision

Parent requested focused missing-import evidence after the original handoff. Inspected
actual tracked EbookLib imports and export callers read-only, then added three tests
against the unchanged real `KPXExporter` in an isolated Python subprocess. Only
`ebooklib` imports are rejected with `ModuleNotFoundError`, regardless of whether the
host has the library preinstalled. Exporter methods, content scanning and other export
implementations are real; no replacement engine or EPUB mock was introduced. All
outputs are tiny temporary files removed on completion. No server/model/CI run occurred.

Observed and asserted:

1. Loading `KPXExporter` itself succeeds without EbookLib; the dependency is imported
   when `export_epub` is called after content scanning.
2. Calling `export_epub` with benign text raises **ModuleNotFoundError** with name
   `ebooklib`, not the RuntimeError implied by that source module's introductory prose.
   It writes no EPUB or other artifact. No graceful "feature unavailable" UI or typed
   capability error was added; clean-default callers encounter that exception.
3. `export_all` catches the exception and stores exactly
   `FAILED: No module named 'ebooklib'` for EPUB while returning **top-level `ok: true`**.
   HTML, Markdown, LaTeX and JSON files are still genuinely written. No EPUB is written.
   Thus the aggregate success flag cannot attest five-format success; callers/owners
   must inspect per-format results, and source-level UI/error-honesty remediation
   remains outside this lane.
4. PDF/DOCX/text launch ingestion is unchanged and does not support EPUB intake.
   Tracked Python code search identified EbookLib use in the legacy KPX exporter,
   not an EbookLib launch-ingestion implementation. Scoped docs/optional manifest now
   say KPX export rather than claiming observed EbookLib intake support.
5. Separate `kami_handlers.py`/Quarkdown EPUB paths exist, including a legacy fallback
   that writes a stub header if compilation fails. Those engines are untouched,
   untested here, and are NOT asserted as supported replacements or feature parity.

Final validation:
- `python tests/test_legacy_epub_dependency_boundary.py -v`: **3 passed**.
- `/data/axiom-minvenv/bin/python -m pytest tests/test_default_dependency_policy.py tests/test_legacy_epub_dependency_boundary.py -q`: **12 passed, 44 subtests passed**, 0.31 seconds.
- Log: `/data/axiom-v82-license-epub-cycle2.log`.
- `git diff --check`: passed; worktree clean after atomic second commit.
- The original guard module was not revised in cycle 2; the new boundary module has
  one source revision and no failed narrow tests. No old test module/skips changed.
  The five-source-revisions-per-failing-module cap was not approached.

### Required owner legal/distribution-profile decision — NOT supplied by this lane

Direct default removal changes clean-install KPX EPUB availability. A broad suite pass
on a host with preinstalled EbookLib proves neither default clean-host EPUB availability
nor legal clearance. This narrow missing-import test establishes local failure behavior,
not a fully resolved clean-host installation or end-to-end UI outcome. Owner must choose:

- Keep legacy KPX EPUB unavailable/unsupported in the default profile and review how
  capability gating, UI errors and aggregate status should represent that degradation;
  or
- Explicitly review/authorize a separate LGPL-enabled optional distribution profile,
  including version-specific EbookLib obligations, attribution/distribution and tests.

No LGPL profile is approved here, and a separate requirements file is not approval.
Likewise retaining pikepdf/MPL does not invent an MPL or general Python-policy approval.
The static guard inspects only names declared by default manifests and their local
`-r`/`-c` include/constraint closure. It does NOT inspect installed packages or the
resolver/transitive closure. Docling dependencies, system LGPL/MPL libraries and other
license obligations may remain; no such closure was resolved, downloaded or cleared.
These limitations are now explicit in both scoped notices/catalog.

### Additional out-of-scope stale policy source for parent

Read-only inspection found `docs/LICENSE_AUDIT.md` labels EbookLib AGPL and claims it
is not in production imports. That contradicts the LGPL catalog and the actual KPX
runtime import. It was NOT edited because this lane is limited to the assigned exact
notices/catalog/manifests/new tests. Parent should reconcile that document in an owned
policy-doc pass; do not treat it as authoritative clearance. CI and `ci/pre-push.sh`
remain parent-owned and untouched.
