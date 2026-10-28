# Integration decisions: Storytold and the supplied repository shortlist

## Decision

**Do not embed the Craft application suite or attach its general-purpose MCP servers to Axiom's current preview.** Keep the visible, explicit-text-input, review/manual-copy product working. No third-party runtime dependency, plugin, skill, installer or provider was installed or enabled by this review. Bundling remains disabled; production qualification remains false.

The opportunity is **one bounded operation that completes a valuable user task**, not thirteen more application interfaces. For document-heavy users, first investigate selected-input DOCX extraction. For a separately validated diagram workflow, investigate an isolated VectorCraft command backend. These are competing experiments, not simultaneous roadmap commitments. Selected-input DOCX means user-approved file bytes or an expressly selected range, not an assumption that only visible text exists: specify the treatment of comments, tracked deletions, hidden text and embedded content, disclose exclusions and prohibit external-resource fetching. Small PSD/number-format modules are technically interesting but not justified product features without actual demand.

This is a source-based engineering and product recommendation, not a production, legal, parity, security or “100×” certificate. Recent launches and many agents do not establish a moat, revenue, willingness to pay or a billion-dollar valuation.

## Method and evidence strength

Three parallel reviewers split office/document, creative, and infrastructure/security work. The lead inspected reusable-workflow source and two alternatives from the supplied `repos.md`, reconciled recommendations and challenged the strongest immediate-integration case. This is a small multi-perspective review, not hundreds of independent agents or customer simulations.

We resolved immutable public commit snapshots, inspected complete returned file trees, and sampled README/manifest/license/notice files plus selected actual implementations. Word/Grid/Deck/PdfCraft received 12 files each. All nine creative repositories received root-level screening; Photo/Vector/FigCraft received deeper implementation reads. Launcher/provider/shared-library/ArtCraft-X work traced selected trust boundaries, including the launcher's actual craft-libs dependency revision. This is **not an exhaustive audit of those codebases**. Downloaded application source, binaries, dependencies, plugins, models and installation commands were not executed. No upstream test/benchmark/parity result was independently reproduced.

Detailed evidence, limitations, immutable links and sampled-file inventories:

- [Office/document review](research/STORYTOLD_OFFICE.md)
- [Creative review](research/STORYTOLD_CREATIVE.md)
- [Infrastructure/security review](research/STORYTOLD_INFRA.md)
- [Pinned source ledger](research/INTEGRATION_SNAPSHOTS.json)

The source ledger records source observations, not signed release identities. Different repositories were sampled at different instants. Root licensing does not clear all bundled assets, dependencies, models, fonts, codecs or trademarks. Upstream clean-room descriptions are claims, not independently verified legal provenance.

## Repository decisions

“Prototype” means a future, separately authorized experiment outside the shipping preview. “Pattern” means learn the design, not copy code or enable a server. No row below is approved for immediate production integration.

| Candidate | Useful seam | Decision | Main qualification gap |
| --- | --- | --- | --- |
| WordCraft | DOCX byte-input library, text/structure inspection | **Challenger after existing-parser baseline**, only if selected-file demand is demonstrated | Lenient parsing, partial pagination/round trips, large default budgets, document-model dependencies; do not attach write-capable MCP |
| GridCraft | `gridcraft-numfmt` display formatting; import warnings | **Conditional narrow prototype / pattern** | en-US-only interface, core/module coupling, raw-value/date-system preservation; not Excel calculation parity |
| DeckCraft | Cumulative decompression-work budgets and explicit omitted-slide reporting | **Pattern; defer renderer** | Presentation/media stack; rendered-image-backed PDF is not editable/vector parity |
| PdfCraft | Independent read/write roots, refuse-on-uncertain mutation, parser limits | **Pattern; defer full product** | Hostile-file and OCR/model/fidelity limits; path-root checks retain a check/open race |
| PhotoCraft | Small `photocraft-psd` parser/writer with sparse dependencies | **Conditional parser prototype** | Need a real PSD-input task; bound decoded allocations and qualify corpus/features; parser does not composite |
| VectorCraft | Actual CPU/headless command engine and SVG/PNG artifacts | **First creative-workflow experiment**, only if diagrams are the selected wedge | Ambient file authority/default app connection, lossy conversion, fonts, budgets; not the entire GUI |
| FigCraft | Metered no-WASI WASM guests, explicit host calls, structured layout | **Pattern now** | Host callbacks still hold authority; fuel does not bound host effects; not a universal agent sandbox |
| FilmCraft | Timeline/media command architecture | **Defer** | No selected video task; decoder/codec rights, resources and fidelity unqualified |
| LightCraft | RAW/development pipeline | **Defer** | Camera/color correctness and separate optional model/data licenses |
| EffectCraft | Typed keyframe/composition plans | **Pattern / defer** | Expressions, render cost and fidelity not deeply reviewed |
| DesignCraft | Page-layout/report composition | **Defer** | Pre-alpha upstream status; typography, pagination and interchange need task-specific evidence |
| CADCraft | DXF/DWG and geometry | **Defer** | Entity-loss warning, precision/units; MPL-2.0 DWG dependency requires component review |
| SoundCraft | DSP/time and typed engine commands | **Defer** | Audio-device/native-plugin authority, realtime behavior and rights outside current need |
| craft-launcher | Staged installs, missing-checksum refusal, version/asset binding | **Pattern only** | A checksum is not independent release authorization; separate installer trust/signing/rollback boundary needed |
| craft-ai-integrations | Scoped consent, opaque key references, cancellable lifecycle | **Pattern only** | Trusted in-process adapters, duplicate registration semantics, hosted-provider/history scope conflict with preview |
| craft-libs | Possible small utilities | **Review exact crate only when needed** | Fork/API/feature/license closure, duplicated core APIs; not a blanket approved platform |
| artcraftx | Experimental desktop/provider UI | **Do not integrate as supplied** | Full-key credential-list IPC, direct credential TOML persistence, broad renderer HTTPS permissions, unresolved code-license scope |
| craft-common-actions | Release/platform/supply-chain workflow designs | **Pattern only** | License scope unresolved in sampled tree; internal mutable `@main` references; release and attestations are separate flows |
| craft-contrib | Contributor/RFC decision process | **Process reference** | Not a runtime feature or plugin; no code reuse justified |

Primary implementation evidence for the highest-interest seams:

- WordCraft [DOCX API](https://github.com/storytold/wordcraft/blob/aadb077e072b7de05f724e359d8db82e151f125c/crates/docx/src/lib.rs).
- GridCraft [number-format API](https://github.com/storytold/gridcraft/blob/146161b4b450a56e5e59a083ba0478582d1e602b/crates/numfmt/src/lib.rs).
- PhotoCraft [PSD manifest](https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/crates/psd/Cargo.toml).
- VectorCraft [headless implementation](https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/crates/mcp/src/headless.rs).
- FigCraft [plugin boundary](https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/crates/plugin/src/sandbox.rs).
- ArtCraft-X [credential payload](https://github.com/storytold/artcraftx/blob/c6b5d338303251d8bcb93ec6806b412f95127936/crates/artcraftx/src/commands/credentials/credential_payload.rs) and [renderer capability](https://github.com/storytold/artcraftx/blob/c6b5d338303251d8bcb93ec6806b412f95127936/crates/artcraftx/capabilities/default.json).

## What the licensing review actually found

The inspected Craft app roots generally carry **MIT OR Apache-2.0**, not merely the Apache-only label shown by organization metadata. Preserve the selected grant and required notices. ArtCraft names/logos/branding are excluded; WordCraft's separate brand license is restricted, not an open-source source-code grant. Do not copy branding or imply affiliation.

Examples that block a blanket “everything is permissive” statement:

- PdfCraft OCR source identifies separately licensed model assets and a limited recognition alphabet. No multilingual/OCR execution was qualified.
- LightCraft's NOTICE distinguishes non-OSI SAM weights, optional GPL-3.0 RawNIND weights and CC-BY-4.0 GeoNames data.
- CADCraft identifies an MPL-2.0 DWG library. This triggers exact component/distribution review, not a blanket prohibition or claim that the whole suite is GPL.
- craft-libs attribution identifies feature-dependent embedded assets, including GPL-2.0-or-later Slovak hyphenation patterns. Determine the actual enabled feature closure.
- ArtCraft-X frontend MIT metadata and vendored licenses do not establish a repository-wide grant for all original Rust code/assets. Its scope remains unresolved.

Most sampled Craft workspaces declare Rust 1.95 (some 1.90), use shared Git-pinned libraries and patched GUI dependencies. Axiom's existing runtime CI uses its own toolchain and dependency graph. Shared use of Rust is not binary/API compatibility; a lockfile or root manifest is not a build-specific SBOM or legal clearance.

## Two alternatives actually inspected from repos.md

### OfficeCLI — more direct office operations, but not safe-by-default authority

Pinned to `89905744ed6dbb87fb6807a0d9fda6ed3da1c18d`. Actual Apache-2.0 license; selected source reads include project manifest, entrypoint, skill installer and plugin process/registry. It targets .NET 10 with self-contained single-file publication and Open XML SDK. It may be a more direct CLI experiment for document operations than embedding a new GUI. “Single binary” does not mean no dependency, plugin or operational trust cost.

Its plugin driver executes native processes with inherited process environment unless deliberately constrained. The source explicitly uses an **idle** watchdog rather than a wall-clock deadline, and collects diagnostics; continuous plugin output can extend execution. Registry discovery and skill installation are broader authority than an allowlisted read-only operation. Do not run its curl-pipe installers, auto-install skills, permit arbitrary plugins, expose raw XML writes, or mutate an original document in the current product. A future comparison must pin the binary/build, disable plugin discovery and installation paths, isolate environment/files/network, enforce independent wall/output/resource budgets and use copies with visible diffs.

Evidence: [manifest](https://github.com/iOfficeAI/OfficeCLI/blob/89905744ed6dbb87fb6807a0d9fda6ed3da1c18d/src/officecli/officecli.csproj), [plugin driver](https://github.com/iOfficeAI/OfficeCLI/blob/89905744ed6dbb87fb6807a0d9fda6ed3da1c18d/src/officecli/Core/Plugins/PluginProcess.cs), [registry](https://github.com/iOfficeAI/OfficeCLI/blob/89905744ed6dbb87fb6807a0d9fda6ed3da1c18d/src/officecli/Core/Plugins/PluginRegistry.cs), [skill installer](https://github.com/iOfficeAI/OfficeCLI/blob/89905744ed6dbb87fb6807a0d9fda6ed3da1c18d/src/officecli/Core/SkillInstaller.cs).

**Decision:** comparison candidate only if file operations become an approved workflow. No current dependency.

### OpenDataLoader PDF — parser comparison, not an offline/OCR shortcut

Pinned to `94a17ec03c7e902706a92a0bd4e8918e979c4967`. Actual Apache-2.0 root license plus a substantial third-party inventory. README distinguishes local parsing, hybrid AI/OCR, and enterprise PDF/UA export. Its performance/accuracy rankings are upstream claims not reproduced here.

The Python wrapper runs a bundled JAR through Java; README requires Java 11+ and Python 3.11+. The sampled runner has no explicit wall timeout and accumulates output; JVM option environment variables and temporary-directory handling are part of the deployment boundary. Optional hybrid extras pull a materially larger Docling/OCR stack. A Python package with no base Python dependencies is not a zero-runtime-cost parser. Any future adapter needs a stripped environment, approved JRE/JAR/assets, kill/reap and output/memory budgets, semantic citation checks and explicit no-hybrid/no-network configuration followed by observed network-denied testing.

Evidence: [runner](https://github.com/opendataloader-project/opendataloader-pdf/blob/94a17ec03c7e902706a92a0bd4e8918e979c4967/python/opendataloader-pdf/src/opendataloader_pdf/runner.py), [Python manifest](https://github.com/opendataloader-project/opendataloader-pdf/blob/94a17ec03c7e902706a92a0bd4e8918e979c4967/python/opendataloader-pdf/pyproject.toml), [third-party inventory](https://github.com/opendataloader-project/opendataloader-pdf/blob/94a17ec03c7e902706a92a0bd4e8918e979c4967/THIRD_PARTY/THIRD_PARTY_LICENSES.md).

**Decision:** isolated extraction challenger only if a representative PDF corpus shows Axiom's current parser is the bottleneck. No parser replacement, JVM or hybrid server installed.

The rest of repos.md remains a discovery backlog, not an audited or approved dependency graph. Existing [tooling decisions](TOOLING_DECISIONS.md) retain Playwright as a possible test layer and llama.cpp as a future target-device backend comparison. Arena/MiroFish-style agent simulations are not independent user validation; no such framework was executed here.

## Release workflow lesson

At craft-common-actions `fa5ef18780cf5e7d5d3b8de068de56cffc83cac5`, sampled [release.yml](https://github.com/storytold/craft-common-actions/blob/fa5ef18780cf5e7d5d3b8de068de56cffc83cac5/.github/workflows/release.yml) does **not** invoke [supply-chain.yml](https://github.com/storytold/craft-common-actions/blob/fa5ef18780cf5e7d5d3b8de068de56cffc83cac5/.github/workflows/supply-chain.yml). The latter is a separate opt-in SBOM/attestation workflow with explicit permissions. The release workflow has signing-secret guards, but a missing macOS verification script takes a warning path. Several internal helpers are referenced at mutable `@main` despite other actions being SHA-pinned.

Borrow the separation of build, signing, install/uninstall and attestations; do not import it as a complete proof. Future Axiom release authorization must fail when required verification is unavailable, pin all nested workflow dependencies, validate artifact identity and provenance, and test upgrade/rollback/uninstall on supported devices. A checksum proves neither signer authority nor runtime safety. No release workflow was changed or activated by this research.

## Council: strongest opposing cases and resolution

1. **Integration advocate:** structured headless tools could move Axiom from text suggestions to finished documents/diagrams. Resolution: valid opportunity, but only with a named repeated task, narrow command schema and measured correction cost. A general MCP connection grants far more than needed.
2. **Security/reliability challenge:** file/parser/plugin/updater/provider authority can silently transform a small preview into a privileged agent. Resolution: no direct suite/launcher/provider integration; dedicated capability and isolated job boundary before any experiment.
3. **Founder challenge:** delaying every feature can also prevent learning. Resolution: obtain a target-device report now, qualify one real workflow, and time-box one challenger experiment. Do not spend another cycle collecting repositories without a user task.
4. **Maintenance challenge:** shared Rust/egui code looks reusable but can import toolchain/fork/license churn. Resolution: smallest seam wins only after a reproducible dependency closure and named maintenance owner; a separate process may be preferable to linking.

## Premortem and stronger alternative

| Failure in six weeks | Better response now | Required evidence / stop rule |
| --- | --- | --- |
| Many impressive integrations, no repeat users | One user segment and one frequent task; preserve simple current flow | Consenting users repeat the task without founder prompting; otherwise do not expand scope |
| Silent DOCX/PSD/SVG data loss | Read-only import first; originals immutable; warnings and visible output review | Independent reference corpus, no unexplained omissions or semantic changes |
| Prompt injection turns document metadata into commands | Treat all parsed content and model output as untrusted data | Fixed operation schema/allowlist; injected instructions cannot grant tools, paths or destinations |
| Plugin emits forever or parser exhausts memory | Dedicated job process with independent wall/CPU/memory/input/output limits | Actual timeout/cancel/kill/reap and cleanup tests, not an HTTP acknowledgment |
| “Local” still sends data outward | No automatic cloud fallback; approved assets and backend configuration | Cold disconnected startup and observed egress tests on the selected device; report limitations |
| Matching model reports are mistaken for attestation | Preserve independently configured identity plus response checks | Reported-only language; artifact/backend custody and network controls remain separate |
| Library introduces restricted brand/model/font rights | Exact feature/build inventory and removal of unapproved assets/marks | No redistribution while required grants/notices are missing |
| Updater replaces a good binary with a malicious but correctly hashed one | Separate release-authorization root and version/rollback policy | Platform-specific signer/provenance/rollback tests before enabling updates |
| Profile collector is marketed as a qualification pass | Measurements and unknowns only; no readiness thresholds | Always production_qualified=false, real-model/native/offline not tested |

## Next work, in order

1. **Identify the target device and task.** Run the opt-in [device profile collector](DEVICE_QUALIFICATION.md) on the intended authorized device, inspect the JSON before sharing, and separately supply GPU details if needed. It does not probe inference or certify hardware. Choose exact approved model/backend versions and rights independently; do not derive trust from inventory output.
2. **Qualify the existing foreground experience.** Build and observe the actual window, authentication/pairing, Unicode/manual-copy, missing assets, cancellation, quit, retention and backend behavior on that profile. Existing CI/mocks are necessary regression evidence, not this observation.
3. **Run a consent-based task pilot.** Proposed, not completed: five users in one segment, ten representative tasks each, including ambiguous/error cases. Compare against their current workflow; include setup, correction and recovery time. Record task success, harmful/wrong suggestions, abandonment, repeat use, support cost and willingness to pay. Set the acceptance thresholds with users before observing outcomes.
4. **Choose at most one challenger.** If users spend time moving source documents into text, first evaluate the monorepo's existing isolated document-service parser under the newly approved capability and intended corpus. WordCraft is a challenger only if that baseline has a measured gap; selected file access must not be added implicitly to the current text-only preview. If the repeated task is diagram creation, compare VectorCraft command-only output with forced headless mode, no connection to a running GUI, dedicated job roots and OS isolation; commands alone are not confinement. If neither is the bottleneck, integrate neither. Keep OfficeCLI/PDF/PSD/numfmt challengers behind the corresponding actual need.
5. **Promote only qualified properties.** Any future adapter must have explicit input/effect approval, immutable originals, no ambient credentials/network, independently bounded worker lifecycle, loss warnings, exact dependency/asset rights, pinned reproducible build, target-platform checks and rollback. No automatic typing/capture, broad MCP passthrough or silent installation.

A good next milestone is **one independently observed valuable task on one supported device with honest failure behavior**, not “all possible integrations.” That is a bounded learning milestone; production release still needs the separate gates in [RELEASE_QUALIFICATION.md](RELEASE_QUALIFICATION.md).
