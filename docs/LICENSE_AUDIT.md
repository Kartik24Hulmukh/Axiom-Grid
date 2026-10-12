# License Audit — Kairo-Phantom

**Status:** Historical inventory, not current release clearance. V8.2 corrections below supersede the EPUB/default-dependency claims. This document is not an exhaustive resolved/transitive distribution audit.

**Date:** 2026-07-08  
**Auditor:** Autonomous engineering agent (GLM-5.2)  
**License:** MIT (see [LICENSE](../LICENSE))

## 1. Project License

Kairo-Phantom is distributed under the **MIT License**.  
Copyright (c) 2026 Kairo Phantom Contributors.

## 2. Clean-Room Provenance

All shipped source files trace their provenance via:
- `# PROVENANCE: original` — clean-room original work
- `# PROVENANCE: ADR-<n>` — clean-room work per Architecture Decision Record
- `# PROVENANCE: vendored <pkg>@<ver> (MIT)` — vendored from MIT-licensed upstream

CI enforcement: `ci/cleanroom_provenance.yml` checks every file under `src/` 
for a provenance header and verifies referenced ADRs exist.

## 3. Dependency License Audit

### Rust Dependencies (via Cargo.toml workspace)

| Component | License | Compatible with MIT? |
|:---|:---|:---|
| Tokio | MIT | ✅ Yes |
| Serde | MIT / Apache-2.0 | ✅ Yes |
| serde_json | MIT / Apache-2.0 | ✅ Yes |
| anyhow | MIT / Apache-2.0 | ✅ Yes |
| tracing | MIT | ✅ Yes |
| tracing-subscriber | MIT | ✅ Yes |

### Python Dependencies (via requirements-test.txt)

| Component | License | Compatible with MIT? |
|:---|:---|:---|
| pytest | MIT | ✅ Yes |
| hypothesis | MPL-2.0 | ✅ Yes (MPL-2.0 is MIT-compatible for separate works) |
| pdfplumber | MIT | ✅ Yes |
| model2vec | MIT | ✅ Yes |
| python-docx | MIT | ✅ Yes |
| openpyxl | MIT | ✅ Yes |
| python-pptx | MIT / BSD-3-Clause | ✅ Yes |
| cryptography | Apache-2.0 / BSD-3-Clause | ✅ Yes |
| beautifulsoup4 | MIT | ✅ Yes |
| pydantic | MIT | ✅ Yes |
| fastapi | MIT | ✅ Yes |
| duckdb | MIT | ✅ Yes |
| imagehash | MIT | ✅ Yes |
| Pillow | Version-specific; installed 12.3.0 declares MIT-CMU | Review exact distributed notices |
| EbookLib | LGPL; review exact selected version | Review-only optional KPX EPUB profile; see below |
| odfpy | Apache-2.0 | ✅ Yes |
| striprtf | MIT | ✅ Yes |
| mammoth | BSD-2-Clause | ✅ Yes |
| litellm | MIT | ✅ Yes |
| sqlite-vec | MIT | ✅ Yes |
| headroom-ai | MIT | ✅ Yes |

### V8.2 correction: EbookLib and actual KPX export behavior

The earlier AGPL label and assertion that shipped code never imports EbookLib were incorrect. `kairo-sidecar/sidecar/exporters/kami_kpx.py` imports the real EbookLib dependency during KPX EPUB export. EbookLib is LGPL, not AGPL; exact version and distribution obligations require owner review.

EbookLib is no longer in the default `requirements-test.txt` chain. `requirements-legacy-epub.txt` is a separate legal-review-only opt-in, not legal approval or a default feature guarantee. Without EbookLib, direct KPX EPUB export raises `ModuleNotFoundError`; `export_all` records a failed EPUB result despite returning top-level `ok: true`. Other real export files can succeed. Callers must inspect every requested format result. No replacement EPUB engine, UI fix or clean-host availability is claimed.

PyMuPDF was also removed from the default sidecar requirements, but surviving `fitz` import-time probes and legacy parser/oracle paths remain unsupported/open under the default policy. Already-installed packages can still be discovered. The direct-manifest guard does not audit installed/resolved/transitive dependencies. pikepdf and Hypothesis are MPL-2.0, not permissive; retaining them is not a legal clearance decision.

## 4. No-License / Paper Code Audit

Searched for any code copied from:
- No-license repositories (GitHub repos without a LICENSE file)
- Academic paper reference implementations
- AGPL/GPL-licensed code snippets

**Result:** No code copied from no-license or paper-code sources was found. 
All source files carry `PROVENANCE: original` headers. The cleanroom provenance 
CI gate enforces this on every push.

## 5. Forbidden License Check

The following licenses are **forbidden** in shipped production code:
- AGPL-3.0 (copyleft, network-use trigger)
- GPL-3.0 (copyleft)
- GPL-2.0 (copyleft)
- SSPL (Server Side Public License)
- BUSL (Business Source License)
- CC-BY-NC (Non-Commercial)
- Unlicensed (no license file)

**Current release assessment:** Unresolved. Direct-default exclusions are guarded, but legacy imports, optional distribution profiles, resolved/transitive licenses and bundled notices still require review. No repository-wide absence or legal clearance is asserted.

## 6. CI Enforcement

| Gate | Workflow | Status |
|:---|:---|:---|
| Clean-room provenance headers | `ci/cleanroom_provenance.yml` | ✅ Active |
| cargo-deny advisories + licenses | `.github/workflows/supply_chain.yml` | ✅ Active |
| Secret scan (gitleaks + custom) | `.github/workflows/supply_chain.yml` | ✅ Active |
| SBOM generation (CycloneDX) | `.github/workflows/supply_chain.yml` | ✅ Active |

## 7. Current conclusion

- The historical clean-room, workflow and compatibility statements above are not a fresh attestation of every source file, license or CI gate.
- Default requirements no longer declare PyMuPDF or EbookLib; automated guards check direct local manifest closure only.
- Clean-default KPX EPUB export is unavailable; surviving legacy fitz paths and broader distribution/license obligations remain open.
- Owner legal/distribution-profile decisions, exact artifacts and resolved/transitive notices are required before release. V8.2 does not supply legal clearance.
