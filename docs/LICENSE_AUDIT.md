# License and provenance review — qualification remains open

This document corrects the historical July 2026 audit. It is **not legal advice,
license clearance, or a complete dependency/distribution audit**. The repository's
root license does not determine every dependency's or model's license.

## Confirmed source-tree facts

- `ci/cleanroom_provenance.yml` is outside GitHub's active workflow directory.
- `.github/workflows/supply_chain.yml`, claimed active by the older document,
  is absent at the reviewed base `47a0543cc50557e143e5d3b3f306a6329d870ac7`.
- The active `.github/workflows/axiom.yml` runs focused engineering gates; it
  does not establish a complete license, provenance, advisory, or signing audit.
- `kairo-sidecar/sidecar/exporters/kami_kpx.py` imports `ebooklib` inside
  `export_epub`. The earlier categorical statement that it exists only in
  test/development import paths was incorrect. This source-tree fact does **not**
  prove that exporter ships in the authorized preview or establish a violation.
- The legacy `scripts/ci/sbom_gate.py` inventory uses heuristics and hard-coded
  entries. It is not a complete resolved/versioned distribution inventory. Its
  retired CLI and unapproved ephemeral signing path now refuse success.

## Required before distribution approval

1. Identify the exact build, platform, bundled files, enabled features, resolved
   direct/transitive dependencies, model weights, tokenizer and other assets.
2. Verify each artifact's upstream license, version, source and redistribution
   conditions; collect required notices, source offers and attribution as applicable.
3. Review actual packaging/import reachability, including optional EPUB export.
   Isolate/remove incompatible components or obtain appropriate rights as needed;
   do not infer compatibility merely from a package name or root MIT license.
4. Review vendored/copied code provenance with verifiable records. No complete
   clean-room provenance claim is made here.
5. Produce a complete inventory and advisory review bound to that build. If
   signing is required, use an approved persistent verification identity and verify
   the output independently; a checksum or ephemeral key is not signer approval.
6. Obtain qualified legal review for copyleft/commercial/model-license questions.

Installer bundling remains disabled. See [AUTHORIZED_PREVIEW.md](AUTHORIZED_PREVIEW.md)
and [RELEASE_QUALIFICATION.md](RELEASE_QUALIFICATION.md). Earlier blanket claims of
“no violations” and active supply-chain enforcement are superseded, not evidence
that a current distribution has been cleared.
