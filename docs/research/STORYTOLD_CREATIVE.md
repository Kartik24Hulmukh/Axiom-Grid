# Independent read-only review: Storytold creative suite → Axiom-Grid

Review date: 2026-10-28 UTC. Decision: **do not merge nine GUI applications or promise “100×.” Prototype one artifact capability behind a separate, explicit authorization boundary; reuse a small format component only after qualification.** The strongest near-term candidates are VectorCraft's headless vector artifact engine, PhotoCraft's standalone PSD parser/writer, and FigCraft's command/plugin architecture. “100×” is an aspiration, not a measured outcome.

## Scope and evidence strength

All nine received bounded root/tree/README/manifest/license/NOTICE screening. PhotoCraft, VectorCraft and FigCraft received selected implementation-level reads; the other six did not receive deep code review. The table below is a screening decision, **not nine audited codebases**. No application, downloaded source, tests, builds, install scripts, release binaries or plugin modules were executed. No Git mutations, credentials or application-source writes were performed. Only research snapshots and this report were written outside source checkouts. Public source was read at immutable commits; the helper uses read-only `git ls-remote` and one recursive tree API request per repository, then pinned raw-file reads. All nine returned nontruncated trees. HEADs were sampled separately, not atomically across the organization.

Root organization metadata is `org-repos.json`, an existing observation rather than a maintainer/release certification. It labels these repositories Apache-2.0, but their sampled workspace manifests and root license files declare **MIT OR Apache-2.0**. Actual files and component exceptions take precedence over the GitHub license label. Release artifacts, commit histories, CI outcomes, contributor capacity, asset completeness and full lockfile/transitive license graphs were not audited. README feature counts, clean-room descriptions, parity percentages and corpus success numbers remain upstream claims.

## Axiom compatibility: current versus proposed

Local current evidence: `model-identity-published/README.md`, `docs/AUTHORIZED_PREVIEW.md`, `docs/PUBLIC_ROADMAP.md`, and `docs/IMPLEMENTATION_VERDICT.md`. These describe an explicit-input, visible-review, manual-copy engineering preview. The authorized preview grants no screen/clipboard/shell/filesystem permissions; file edits and automatic insertion are outside its boundary. The README routes Tauri → authenticated loopback axiom-runtime → Ollama. A creative backend is therefore **a separately approved future artifact service**, not an innocuous addition to the existing preview allowlist. This review does not establish native build or real-model performance.

A proposed architecture, not implemented: explicit user brief and selected assets → schema-validated artifact plan → visible plan/rights review → dedicated job process with narrowly scoped files → command-only headless backend → sanitized artifact preview + manifest → separate explicit export approval. Axum/runtime may broker jobs in a new capability profile after review; Ollama output is untrusted proposed data, never executable code or authority. Keep current manual-copy mode working unchanged. Do not add screen capture, window inspection, pointer/keyboard dispatch or auto-typing. Rendering the selected document to a bounded image is an artifact operation, not permission to capture another app.

## Nine-repository screening decisions

| Repository | Actual shape and plausible value | Recommendation and main failure mode |
|---|---|---|
| photocraft | Multi-crate raster editor plus CLI, automation engine and standalone PSD/PSB format crate; image/layer artifact work, not just GUI code. | **Prototype** PSD inspection; conditional narrow **integrate** candidate is photocraft-psd only. Full editor deferred: document-model round trips are not equivalent to format-level preservation. |
| vectorcraft | Vector editor with geom/doc/SVG/PDF/engine/render/MCP crates; documented headless CPU backend and structured drawing/export. | **Prototype first** for icons/diagrams/posters to SVG/PNG. Prefer isolated command process over embedding the whole engine; format loss, fonts and ambient access are blockers. |
| filmcraft | Nonlinear editor, media/container/codec crates and typed engine commands; README exposes timeline.place and effects.setParam through control/MCP. | **Defer** integration until there is a concrete video workflow. Time/codec subcrates are candidates, not reviewed reusable dependencies. Decode fidelity, resource cost and codec rights can erase value. |
| lightcraft | Non-destructive photo/develop pipeline, RAW and metadata crates; CLI/MCP and develop.set command advertised. | **Defer** behind PhotoCraft unless RAW development is the actual need. Optional models have distinct licenses and downloads; camera/color accuracy not established. |
| effectcraft | Motion/compositing workspace with time/keyframe/project/expr/Lottie/render/export crates and CLI/MCP. | **Pattern / defer**: typed keyframe/project design may inform artifact plans. Expressions, render fidelity and export cost need a separate deep review; not a drop-in motion service. |
| designcraft | Page-layout app with doc/compose/PDF/IDML/EPUB/PPTX/text-import and headless rendering claims. README explicitly says pre-alpha. | **Defer**; consider later report/page-layout prototype if it beats existing tooling on an actual fixture. Typography, pagination and interchange fidelity are not certified. |
| figcraft | Interface-design document/layout engine, headless MCP, collaboration and bounded WASM plugin API. | **Pattern now / prototype second** for structured mockups and reusable layout. Not a React/Tauri frontend generator or a generic grid engine; doc/layout/engine coupling and host authority matter. |
| cadcraft | CAD workspace with geometry, DXF/DWG and constraints plus CLI/MCP; README explicitly warns unmodeled entities are not kept on save. | **Defer** unless CAD is a user requirement. No destructive originals workflow; unit/constraint precision, entity loss and MPL-2.0 DWG dependency need qualification. |
| soundcraft | DAW workspace with DSP/mix/MIDI/audio I/O/model/engine and native plugin hosts plus automation. | **Defer** whole app; DSP/time may merit later extraction for a defined audio task. Native plugin execution, device permissions, realtime behavior and plugin licenses are major boundaries. |

Root evidence for each row:
- **photocraft**: [^https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/README.md] [^https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/Cargo.toml] [^https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/NOTICE]
- **vectorcraft**: [^https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/README.md] [^https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/Cargo.toml] [^https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/NOTICE]
- **filmcraft**: [^https://github.com/storytold/filmcraft/blob/8d925e9df32d8755f22bd2635e400a6b3e93f69c/README.md] [^https://github.com/storytold/filmcraft/blob/8d925e9df32d8755f22bd2635e400a6b3e93f69c/Cargo.toml] [^https://github.com/storytold/filmcraft/blob/8d925e9df32d8755f22bd2635e400a6b3e93f69c/NOTICE]
- **lightcraft**: [^https://github.com/storytold/lightcraft/blob/77c0a6adfa7db6e4f79b80843c0c578e5f16dee1/README.md] [^https://github.com/storytold/lightcraft/blob/77c0a6adfa7db6e4f79b80843c0c578e5f16dee1/Cargo.toml] [^https://github.com/storytold/lightcraft/blob/77c0a6adfa7db6e4f79b80843c0c578e5f16dee1/NOTICE]
- **effectcraft**: [^https://github.com/storytold/effectcraft/blob/c99684e28e2242d81c3c3b960b88eb84fddd190c/README.md] [^https://github.com/storytold/effectcraft/blob/c99684e28e2242d81c3c3b960b88eb84fddd190c/Cargo.toml] [^https://github.com/storytold/effectcraft/blob/c99684e28e2242d81c3c3b960b88eb84fddd190c/NOTICE]
- **designcraft**: [^https://github.com/storytold/designcraft/blob/3a1edcd76dc30a2219624ce1d30f27adc61df083/README.md] [^https://github.com/storytold/designcraft/blob/3a1edcd76dc30a2219624ce1d30f27adc61df083/Cargo.toml] [^https://github.com/storytold/designcraft/blob/3a1edcd76dc30a2219624ce1d30f27adc61df083/NOTICE]
- **figcraft**: [^https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/README.md] [^https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/Cargo.toml] [^https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/NOTICE]
- **cadcraft**: [^https://github.com/storytold/cadcraft/blob/336243e0afb3019feee58d0d4fc0d218f25530e7/README.md] [^https://github.com/storytold/cadcraft/blob/336243e0afb3019feee58d0d4fc0d218f25530e7/Cargo.toml] [^https://github.com/storytold/cadcraft/blob/336243e0afb3019feee58d0d4fc0d218f25530e7/NOTICE]
- **soundcraft**: [^https://github.com/storytold/soundcraft/blob/8ca6939981a1cf5d4b0f39cbcd2b0c6a3dedadb0/README.md] [^https://github.com/storytold/soundcraft/blob/8ca6939981a1cf5d4b0f39cbcd2b0c6a3dedadb0/Cargo.toml] [^https://github.com/storytold/soundcraft/blob/8ca6939981a1cf5d4b0f39cbcd2b0c6a3dedadb0/NOTICE]

## Deeper candidate 1 — VectorCraft: artifact engine, not UI automation

**Concrete surface.** `vectorcraft-mcp` depends on engine/render/svg/format/tools/doc rather than the egui UI crate. `Headless` owns an engine `Session`, CPU `Renderer`, view state and optional automation roots; this is actual headless implementation, not just a README promise. Its host commands include `file.open`, `file.save`, `file.export` and `file.exportForScreens`; absent a destination, supported exports can return base64 bytes. The server implements MCP tool discovery/calls and initialization. Use discovery to freeze an adapter-specific allowlist, not blanket access to every current/future command. [^https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/crates/mcp/Cargo.toml] [^https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/crates/mcp/src/headless.rs] [^https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/crates/mcp/src/server.rs]

**Proposed prototype.** User-provided brief → approved finite JSON drawing plan → deterministic shapes/text command sequence → inspect document → bounded PNG review plus SVG artifact. Start with a diagram/icon workflow, not “Illustrator replacement.” Deny UI tools, arbitrary run_command passthrough, plugins, scripts, updater, network, linked-file traversal and arbitrary export destinations. This recommendation does not launch or register a server.

**Important default trap.** `mcp` with no mode attempts a running app before falling back to headless. Without roots, the headless struct comments explicitly say “anywhere.” Root flags imply headless; mixing them with `--connect` is rejected. Specify a dedicated input root and empty job output root; never give the home/project root. Upstream docs acknowledge path-check/open symlink races against other local software. Roots are defense in depth, not an OS sandbox. App-owned preferences/recovery folders are also outside that documented confinement. Prefer stdin/stdout transport and an OS-isolated process, with explicit fonts and no credential inheritance. [^https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/docs/mcp.md] [^https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/crates/mcp/src/headless.rs]

**Module versus framework.** `vectorcraft-svg` offers actual import/export and warning/report APIs, but it is coupled to doc, effects, brush, text, color and geometry, plus craft-docpath/usvg/image. It is not a tiny generic SVG library. Its own API documentation details irreversible structure changes (outlined strokes, some groups, rasterized gradients), ignored filters and text/import approximations. Preserve the original input and display conversion warnings; do not equate visual output with editable, lossless round trips. [^https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/crates/svg/Cargo.toml] [^https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/crates/svg/src/lib.rs]

## Deeper candidate 2 — PhotoCraft: a truly narrow PSD component

`photocraft-psd` is the clearest general-purpose reusable module sampled: default features empty; ordinary dependencies only thiserror and flate2, with optional serde. Public exports include `PsdFile`, `PsdBuilder`, `LayerSpec`, `PixelData`, `RowDecoder` and format models. `PsdFile::from_bytes` / `to_bytes` form a format-level parse/write surface, and the crate retains unknown blocks/channel encodings. `PsdBuilder` requires the caller to provide the merged composite: **the crate does not composite**. This can support isolated metadata/layer inspection or controlled export without embedding the editor. Source inherits workspace Rust 1.95/edition 2024 requirements; standalone publish/build compatibility was not checked. [^https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/crates/psd/Cargo.toml] [^https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/crates/psd/src/lib.rs] [^https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/crates/psd/src/file.rs] [^https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/Cargo.toml]

Do not promote its “never panics” or byte-stable comments to a verified security/fidelity guarantee. Corpus test code exists and is feature-gated on `corpus`; it needs separately obtained fixtures. No tests were run. Format-level byte stability for an unmodified parsed file does not imply preservation through PhotoCraft's higher-level document/editor model; the README itself distinguishes those claims. Bound compressed input, dimensions, decoded allocation, nesting and CPU in a separate parser process; qualify unknown blocks, malformed files, PSB, 16/32-bit, color modes and decompression bombs with user-approved fixtures before deployment. [^https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/crates/psd/tests/it/corpus.rs] [^https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/README.md] [^https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/crates/psd/src/lib.rs]

The full `photocraft-automation` crate is a much larger engine/IO/render/format integration with rmcp/Tokio/cap-std, not merely an RPC shim. MCP has command discovery, command_run, command_batch, doc_inspect and bounded document previews. Upstream explicitly says batches are **not atomic**, earlier successes persist, and undo does not undo disk writes. Reply-budget failure can mean the current operation completed: do not blindly retry. The sampled TCP security implementation has authentication-first handling, generated 256-bit token, bounded frames, 16 connections and authentication deadline; these are useful design evidence, not a completed transport audit. Prefer headless stdio and scoped roots rather than live bridge mode. [^https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/crates/automation/Cargo.toml] [^https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/docs/mcp.md] [^https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/crates/automation/src/security.rs]

## Deeper candidate 3 — FigCraft: constrained extension pattern

The most portable idea is a metered, no-WASI WASM plugin host. Sampled implementation exports `Host`, `Limits`, `run`, `check_module` and `Instance`, with explicit imported host functions and `figcraft_run` entry point. It uses wasmi (no JIT), fuel, module/memory/message/call/log budgets; defaults include 64 MiB guest memory and 16 MiB module/message limits. No ambient filesystem/network/clock/randomness is provided inside the guest. **This is an application-specific ABI, not a certified generic agent sandbox.** The Host callback still decides what commands, data, settings and save offers are authorized. CPU fuel cannot bound arbitrary expensive host work, OS output effects, or host-side logging/retention by itself. [^https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/crates/plugin/Cargo.toml] [^https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/crates/plugin/src/lib.rs] [^https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/crates/plugin/src/sandbox.rs]

Plugin docs describe manifest permissions, command narrowing, one undo step and rollback of document/selection/page on failed callbacks. Those guarantees live in the engine: the plugin crate itself says so. Persistent settings, already-forwarded logs and exported files must be treated separately from in-memory rollback. A save_file host function offers bytes for a user-selected destination; it is not permission to give a plugin arbitrary paths. Axiom should copy the **capability manifest + bounded host calls + staged effects** pattern, not reuse `Host::call` as a route to shell, clipboard, network or the entire runtime. [^https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/docs/plugins.md] [^https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/crates/plugin/src/lib.rs] [^https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/crates/plugin/src/sandbox.rs]

`figcraft-layout` is genuine layout code with `layout_page`, `layout_frame`, `apply_constraints` and injected `Measure` text metrics. It avoids a font dependency directly, but depends on figcraft-doc and geom; it is not a universal replacement for browser CSS, Tauri layout or Axiom's “Grid.” NoMeasure preserves text sizes rather than providing real font layout. MCP server implementation supports a headless session, so a later selected-document mockup prototype need not use screen capture or typing. Full collaboration/server/auth architecture was not audited and should not be pulled in with the prototype. [^https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/crates/layout/Cargo.toml] [^https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/crates/layout/src/lib.rs] [^https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/crates/mcp/src/server.rs]

## Licensing and supply-chain gate

- All nine sampled root pairs are MIT and Apache-2.0; retain the chosen license, copyright and applicable notices. This is permission evidence for owned code, not proof every asset or dependency shares those terms. Every sampled NOTICE excludes ArtCraft brand/name/logo trademarks from the source license: omit branding from Axiom unless separately authorized.
- Fonts and dependency-embedded assets retain separate terms (OFL, Ubuntu Font Licence, MIT, and others). Root indexes are useful provenance leads, not completeness certificates. Review the exact packaged output and every selected feature; avoid copying showcase artwork or fonts gratuitously.
- **LightCraft exception:** NOTICE says segment code is Apache-2.0 only, separately downloaded SAM 3 weights use a non-OSI Meta SAM license, optional RawNIND weights GPL-3.0, and GeoNames downloads CC-BY-4.0. Do not bundle or silently download them; code and model rights are distinct.
- **CADCraft exception:** NOTICE identifies acadrust DWG library as MPL-2.0, used as a separate library. This is not a blanket prohibition, nor a reason to label all CADCraft GPL; review exact file-level/source-distribution obligations before shipping a DWG route.
- **Media/plugin exception:** codec patent exposure, user media/music rights and third-party native plugin terms are not settled by FilmCraft/SoundCraft's root license or “pure Rust” claims. Native plugin hosts expand executable authority and are out of the proposed first prototype.
- Workspace manifests pin shared craft-libs and patched egui revisions. This improves reproducibility but creates shared upstream concentration and fork maintenance risk; pin every selected dependency and audit its own license/security/support story. Lockfile present is not a completed SBOM or vulnerability scan. Most sampled workspaces require Rust 1.95; SoundCraft declares 1.90. No Axiom toolchain compatibility build was attempted.

Specific exception evidence: [^https://github.com/storytold/lightcraft/blob/77c0a6adfa7db6e4f79b80843c0c578e5f16dee1/NOTICE] [^https://github.com/storytold/cadcraft/blob/336243e0afb3019feee58d0d4fc0d218f25530e7/NOTICE] [^https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/NOTICE] [^https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/ASSETS.md] [^https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/Cargo.toml] [^https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/NOTICE] [^https://github.com/storytold/soundcraft/blob/8ca6939981a1cf5d4b0f39cbcd2b0c6a3dedadb0/NOTICE] [^https://github.com/storytold/soundcraft/blob/8ca6939981a1cf5d4b0f39cbcd2b0c6a3dedadb0/Cargo.toml]

## Integration pre-mortem and qualification gates

| Failure after an enthusiastic integration | Prevention / go-no-go evidence |
|---|---|
| Preview becomes a silent filesystem/app-control agent | New explicit artifact capability profile; current preview unchanged; no UI/screen/input tools or arbitrary command bridge. Security review before enabling effects. |
| Model follows malicious layer names/metadata into dangerous commands | Document text is untrusted data; deterministic schema validator and operation allowlist; no tool catalogs or plugin output treated as instructions. |
| Wrong app instance, ambient file authority or lost replies causes destructive edits | Explicit headless mode; per-job roots and OS isolation; fresh copy/output directory; durable job/result manifest; inspect uncertain outcomes, never auto-replay a write. |
| Claimed parity hides lossy edits | Golden corpus per intended workflow; originals immutable; warnings mandatory; independent render/export/round-trip comparison. No proprietary-app parity marketing. |
| Fonts/color/units differ between machines | Pin approved fonts/profiles, output size, locale and render configuration; define semantic and pixel tolerances, not only “file exists.” |
| Images/codecs/plugin host exhaust memory or block cancellation | Per-process memory/CPU/deadline/input/output budgets, worker kill/reap, no GPU/native plugins initially; verify cancel effects and cleanup, not just acknowledgment. |
| All nine applications multiply maintenance but add little value | One command adapter and one workflow first; requalify pinned upgrades; defer overlap. Do not embed nine egui UIs into Tauri. |
| Redistributed binary contains unapproved brand/model/font/dependency material | Feature-specific SBOM, asset manifest and legal review; no auto-updaters/downloaders; review packaged artifact rather than source label alone. |

**First authorized experiment (future work, not run):** choose one repeated diagram/icon task with explicit input; compare current Axiom manual workflow against VectorCraft command-only output. Measure end-to-end time including human correction, task success, editability, export fidelity, peak memory, cold/warm latency, failure/cancel behavior and rights-cleared packaging. Define acceptable thresholds from the actual device/user before execution. Admit a PSD read-only spike only if layered raster inputs are genuinely needed. FigCraft follows only if mockup/layout demand emerges. No numerical speedup or customer value is established here.

**Bottom line:** strongest leverage is reusable artifact operations and capability-safe command architecture, not wholesale app integration. Conditional integrate candidate: photocraft-psd after parser/rights/toolchain gates. Prototype first: VectorCraft isolated headless artifact backend. Pattern: FigCraft bounded plugins and command/layout interfaces. Defer remaining full GUIs and domain engines until actual demand and qualification justify them.

## Immutable snapshot ledger and exact read inventory

All root READMEs, Cargo.toml, LICENSE-MIT, LICENSE-APACHE and NOTICE were fetched; root asset indexes were read where present. Missing bare LICENSE is not a missing-license conclusion. Deep-source selection below is explicit; unsampled files in complete trees are not implicitly reviewed. SHA is the observed main-branch commit used for every permalink, not a release tag or signature verification.

| Repository | Commit | Tree entries | Cached files sampled |
|---|---|---:|---:|
| photocraft | `8988161e90b97608cfe8b8970d0692491fb2ed04` | 3035 | 16 |
| vectorcraft | `56804f6d7e961a7d6bfb8e3d46c168b15e1feee2` | 2594 | 15 |
| filmcraft | `8d925e9df32d8755f22bd2635e400a6b3e93f69c` | 1833 | 6 |
| lightcraft | `77c0a6adfa7db6e4f79b80843c0c578e5f16dee1` | 1477 | 5 |
| effectcraft | `c99684e28e2242d81c3c3b960b88eb84fddd190c` | 1538 | 6 |
| designcraft | `3a1edcd76dc30a2219624ce1d30f27adc61df083` | 1015 | 6 |
| figcraft | `2af5e232d5dd86321e4671655de60f9ae031c53a` | 1443 | 16 |
| cadcraft | `336243e0afb3019feee58d0d4fc0d218f25530e7` | 1117 | 6 |
| soundcraft | `8ca6939981a1cf5d4b0f39cbcd2b0c6a3dedadb0` | 735 | 6 |

### photocraft

- [ATTRIBUTION.md](https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/ATTRIBUTION.md)
- [Cargo.toml](https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/Cargo.toml)
- [LICENSE-APACHE](https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/LICENSE-APACHE)
- [LICENSE-MIT](https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/LICENSE-MIT)
- [NOTICE](https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/NOTICE)
- [README.md](https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/README.md)
- [crates/automation/Cargo.toml](https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/crates/automation/Cargo.toml)
- [crates/automation/src/headless.rs](https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/crates/automation/src/headless.rs)
- [crates/automation/src/security.rs](https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/crates/automation/src/security.rs)
- [crates/automation/src/server.rs](https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/crates/automation/src/server.rs)
- [crates/psd/Cargo.toml](https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/crates/psd/Cargo.toml)
- [crates/psd/src/file.rs](https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/crates/psd/src/file.rs)
- [crates/psd/src/lib.rs](https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/crates/psd/src/lib.rs)
- [crates/psd/tests/it/corpus.rs](https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/crates/psd/tests/it/corpus.rs)
- [docs/control-protocol.md](https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/docs/control-protocol.md)
- [docs/mcp.md](https://github.com/storytold/photocraft/blob/8988161e90b97608cfe8b8970d0692491fb2ed04/docs/mcp.md)

### vectorcraft

- [ASSETS.md](https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/ASSETS.md)
- [Cargo.toml](https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/Cargo.toml)
- [LICENSE-APACHE](https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/LICENSE-APACHE)
- [LICENSE-MIT](https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/LICENSE-MIT)
- [NOTICE](https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/NOTICE)
- [README.md](https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/README.md)
- [crates/engine/Cargo.toml](https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/crates/engine/Cargo.toml)
- [crates/mcp/Cargo.toml](https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/crates/mcp/Cargo.toml)
- [crates/mcp/src/headless.rs](https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/crates/mcp/src/headless.rs)
- [crates/mcp/src/server.rs](https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/crates/mcp/src/server.rs)
- [crates/mcp/src/tools/definitions.rs](https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/crates/mcp/src/tools/definitions.rs)
- [crates/svg/Cargo.toml](https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/crates/svg/Cargo.toml)
- [crates/svg/src/lib.rs](https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/crates/svg/src/lib.rs)
- [docs/control-protocol.md](https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/docs/control-protocol.md)
- [docs/mcp.md](https://github.com/storytold/vectorcraft/blob/56804f6d7e961a7d6bfb8e3d46c168b15e1feee2/docs/mcp.md)

### filmcraft

- [ATTRIBUTION.md](https://github.com/storytold/filmcraft/blob/8d925e9df32d8755f22bd2635e400a6b3e93f69c/ATTRIBUTION.md)
- [Cargo.toml](https://github.com/storytold/filmcraft/blob/8d925e9df32d8755f22bd2635e400a6b3e93f69c/Cargo.toml)
- [LICENSE-APACHE](https://github.com/storytold/filmcraft/blob/8d925e9df32d8755f22bd2635e400a6b3e93f69c/LICENSE-APACHE)
- [LICENSE-MIT](https://github.com/storytold/filmcraft/blob/8d925e9df32d8755f22bd2635e400a6b3e93f69c/LICENSE-MIT)
- [NOTICE](https://github.com/storytold/filmcraft/blob/8d925e9df32d8755f22bd2635e400a6b3e93f69c/NOTICE)
- [README.md](https://github.com/storytold/filmcraft/blob/8d925e9df32d8755f22bd2635e400a6b3e93f69c/README.md)

### lightcraft

- [Cargo.toml](https://github.com/storytold/lightcraft/blob/77c0a6adfa7db6e4f79b80843c0c578e5f16dee1/Cargo.toml)
- [LICENSE-APACHE](https://github.com/storytold/lightcraft/blob/77c0a6adfa7db6e4f79b80843c0c578e5f16dee1/LICENSE-APACHE)
- [LICENSE-MIT](https://github.com/storytold/lightcraft/blob/77c0a6adfa7db6e4f79b80843c0c578e5f16dee1/LICENSE-MIT)
- [NOTICE](https://github.com/storytold/lightcraft/blob/77c0a6adfa7db6e4f79b80843c0c578e5f16dee1/NOTICE)
- [README.md](https://github.com/storytold/lightcraft/blob/77c0a6adfa7db6e4f79b80843c0c578e5f16dee1/README.md)

### effectcraft

- [ATTRIBUTION.md](https://github.com/storytold/effectcraft/blob/c99684e28e2242d81c3c3b960b88eb84fddd190c/ATTRIBUTION.md)
- [Cargo.toml](https://github.com/storytold/effectcraft/blob/c99684e28e2242d81c3c3b960b88eb84fddd190c/Cargo.toml)
- [LICENSE-APACHE](https://github.com/storytold/effectcraft/blob/c99684e28e2242d81c3c3b960b88eb84fddd190c/LICENSE-APACHE)
- [LICENSE-MIT](https://github.com/storytold/effectcraft/blob/c99684e28e2242d81c3c3b960b88eb84fddd190c/LICENSE-MIT)
- [NOTICE](https://github.com/storytold/effectcraft/blob/c99684e28e2242d81c3c3b960b88eb84fddd190c/NOTICE)
- [README.md](https://github.com/storytold/effectcraft/blob/c99684e28e2242d81c3c3b960b88eb84fddd190c/README.md)

### designcraft

- [ASSETS.md](https://github.com/storytold/designcraft/blob/3a1edcd76dc30a2219624ce1d30f27adc61df083/ASSETS.md)
- [Cargo.toml](https://github.com/storytold/designcraft/blob/3a1edcd76dc30a2219624ce1d30f27adc61df083/Cargo.toml)
- [LICENSE-APACHE](https://github.com/storytold/designcraft/blob/3a1edcd76dc30a2219624ce1d30f27adc61df083/LICENSE-APACHE)
- [LICENSE-MIT](https://github.com/storytold/designcraft/blob/3a1edcd76dc30a2219624ce1d30f27adc61df083/LICENSE-MIT)
- [NOTICE](https://github.com/storytold/designcraft/blob/3a1edcd76dc30a2219624ce1d30f27adc61df083/NOTICE)
- [README.md](https://github.com/storytold/designcraft/blob/3a1edcd76dc30a2219624ce1d30f27adc61df083/README.md)

### figcraft

- [ATTRIBUTION.md](https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/ATTRIBUTION.md)
- [Cargo.toml](https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/Cargo.toml)
- [LICENSE-APACHE](https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/LICENSE-APACHE)
- [LICENSE-MIT](https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/LICENSE-MIT)
- [NOTICE](https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/NOTICE)
- [README.md](https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/README.md)
- [crates/format/src/lib.rs](https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/crates/format/src/lib.rs)
- [crates/layout/Cargo.toml](https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/crates/layout/Cargo.toml)
- [crates/layout/src/lib.rs](https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/crates/layout/src/lib.rs)
- [crates/mcp/src/server.rs](https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/crates/mcp/src/server.rs)
- [crates/plugin/Cargo.toml](https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/crates/plugin/Cargo.toml)
- [crates/plugin/src/lib.rs](https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/crates/plugin/src/lib.rs)
- [crates/plugin/src/manifest.rs](https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/crates/plugin/src/manifest.rs)
- [crates/plugin/src/sandbox.rs](https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/crates/plugin/src/sandbox.rs)
- [docs/mcp.md](https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/docs/mcp.md)
- [docs/plugins.md](https://github.com/storytold/figcraft/blob/2af5e232d5dd86321e4671655de60f9ae031c53a/docs/plugins.md)

### cadcraft

- [ATTRIBUTION.md](https://github.com/storytold/cadcraft/blob/336243e0afb3019feee58d0d4fc0d218f25530e7/ATTRIBUTION.md)
- [Cargo.toml](https://github.com/storytold/cadcraft/blob/336243e0afb3019feee58d0d4fc0d218f25530e7/Cargo.toml)
- [LICENSE-APACHE](https://github.com/storytold/cadcraft/blob/336243e0afb3019feee58d0d4fc0d218f25530e7/LICENSE-APACHE)
- [LICENSE-MIT](https://github.com/storytold/cadcraft/blob/336243e0afb3019feee58d0d4fc0d218f25530e7/LICENSE-MIT)
- [NOTICE](https://github.com/storytold/cadcraft/blob/336243e0afb3019feee58d0d4fc0d218f25530e7/NOTICE)
- [README.md](https://github.com/storytold/cadcraft/blob/336243e0afb3019feee58d0d4fc0d218f25530e7/README.md)

### soundcraft

- [ATTRIBUTION.md](https://github.com/storytold/soundcraft/blob/8ca6939981a1cf5d4b0f39cbcd2b0c6a3dedadb0/ATTRIBUTION.md)
- [Cargo.toml](https://github.com/storytold/soundcraft/blob/8ca6939981a1cf5d4b0f39cbcd2b0c6a3dedadb0/Cargo.toml)
- [LICENSE-APACHE](https://github.com/storytold/soundcraft/blob/8ca6939981a1cf5d4b0f39cbcd2b0c6a3dedadb0/LICENSE-APACHE)
- [LICENSE-MIT](https://github.com/storytold/soundcraft/blob/8ca6939981a1cf5d4b0f39cbcd2b0c6a3dedadb0/LICENSE-MIT)
- [NOTICE](https://github.com/storytold/soundcraft/blob/8ca6939981a1cf5d4b0f39cbcd2b0c6a3dedadb0/NOTICE)
- [README.md](https://github.com/storytold/soundcraft/blob/8ca6939981a1cf5d4b0f39cbcd2b0c6a3dedadb0/README.md)

