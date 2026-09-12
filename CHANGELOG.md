## Wave 5 - 13 Sep 2026 - AI-002 measured generalization + CI gates

- **AI-002 (NEW):** `packs/memo/adversarial_gen.py` uses a frontier model (Melious OpenAI-compatible gateway, GLM-5.3) at BUILD TIME ONLY to rewrite the 5 wedge fixtures into 15 adversarial surface forms (label-synonym, date/format, OCR-noise attacks) whose semantic ground truth is invariant by construction. Zero runtime egress; KAIRO_AIR_GAP untouched at serve time.
- **Measured, not assumed:** the rule-based ClassifiedMemoPack scored **F1 0.607** on those adversarial forms (clean 0.981) - a launch-blocking generalization collapse (originating_org 0.000, entities 0.356, subject 0.400, dates 0.467).
- **Fixed:** pack v2 header parser - synonym alias table + fuzzy label resolution, wrapped-line continuation, multi-format date normaliser (DDMMMYY, YYYYMMDD, ISO, US, DTG), lettered/bulleted portion marks and entity bullets, org trailing-place and qty-suffix cleanup, entity de-duplication.
- **Result:** adversarial F1 **0.607 -> 0.977**, clean wedge F1 **0.981 -> 0.996**, overlay suite 30/30, SEC-006 live gauntlet PASS (1,093 rps, p99 67 ms, 0 transport errors).
- **CI:** adversarial generalization gate and the SEC-006 auth gauntlet are now required checks in `.github/workflows/axiom.yml`.

## Unreleased — 2026-09-12 — Production Hardening Wave 4

### Security
- **SEC-006** Bearer / API-key authentication for the network API surface (`AXIOM_API_KEYS`, `AXIOM_REQUIRE_AUTH`). Constant-time digest comparison, `401 + WWW-Authenticate`, fail-closed `503` on misconfiguration, probes/landing page exempt.
- **SEC-005 tiering** Authenticated tenants get an isolated per-key quota (`AXIOM_RATE_LIMIT_PER_MIN_AUTH`, default 3000/min); anonymous traffic and brute-force attempts share the per-IP bucket.
- Docker image now defaults to `AXIOM_REQUIRE_AUTH=1` (fails closed until keys are injected at runtime).

### Testing
- 7 new tests in `overlay/tests/test_server.py` (30/30 passing).
- `scripts/stress_sec006_gauntlet.py`: live-socket 100x gauntlet (2000 req / 100 threads, ~1000 req/s, 0 transport errors, all invariants held).

# Changelog — Kairo Phantom

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## Unreleased

- Fixed rustfmt findings in the readiness API tests so the focused CI gate (fmt, test, clippy, node tests, release build) is green on main.
- Added user cancellation propagation: the overlay Cancel button now invokes a new `cancel_materialize` Tauri command that aborts the in-flight bridge request; dropping the local HTTP request lets the runtime drop its in-flight Ollama request. Cancel with no pending work stays local.
- Added frontend tests for cancel propagation (9 tests total).

## [0.3.0] — 2026-05-13 🎉 Production Release

### Highlights
- **Memory Intelligence Score: 0.9872** — verified by the live `memory_benchmark` suite over 30 sessions. Converges to perfect recall after a single correction.
- **39-scenario E2E Gauntlet** passes across Word, Outlook, PowerPoint, Excel, VSCode, and Browser contexts.
- **Zero-warning strict Clippy** — `cargo clippy --all-targets -- -D warnings` exits clean.

### Added
- **MemMachine v2** — production-grade SQLite-backed memory engine with five architectural upgrades:
  - **GroundTruthStore** — raw episode preservation; eliminates LLM summary drift.
  - **PRIME Meta-Operations** — merge/split/generalize preference policies; self-improving learning.
  - **Alaya Cognitive Decay** — Ebbinghaus forgetting curves in SQLite; prunes noise, preserves signal.
  - **Multi-Granularity Routing** — entropy-based `context_key` selection for sub-app precision.
  - **PAHF Dual-Channel Feedback** — format + tone + length signal decomposition; 3× faster preference learning.
- **WASM Plugin Sandbox** — Wasmtime-based sandbox with Ed25519 signature verification and capability bounding.
- **SPIFFE Identity** — cryptographically signed agent identity for all inter-agent calls.
- **ToolGate** — explicit allowlist enforcement for all file access and tool calls.
- **Sentinel Sanitizer** — prompt injection detection and PII redaction on all AI output.
- **Waza 8-Agent Swarm** — specialized agents: Corporate Strategist, Creative Writer, Developer, Academic Researcher, Medical Reviewer, Legal Writer, Marketing Copywriter, Executive Communicator.
- **MCP Server (`kairo-mcp`)** — integrates with Claude Code, Cursor, and Goose.
- **Deep Document Understanding** — Zip+XML extraction for `.docx`, `.pptx`, `.xlsx`.
- **Plugin System** — TOML-based agent definitions; community-installable via `kairo agent install <url>`.

### Changed
- Default provider is now `ollama` (offline-first). Zero API keys required for full functionality.
- Refactored `ContextEngine` and `SwarmOrchestrator` to trait-based registries for extensibility.
- Improved Win32 ghost-typing speed and reliability under chaos conditions.

### Fixed
- Zero clippy warnings under `--all-targets -- -D warnings`.
- Thread-safe `MemMachine` using `Mutex<Connection>` for concurrent chaos sessions.
- All `manual_strip_prefix`, `sort_by_key`, and doc comment lint violations resolved.

---

## [0.2.0] — 2026-04-15

- Core ghost-typing loop in Rust.
- Initial UIAutomation (UIA) support for Windows.
- Basic Ollama integration with streaming SSE.
- `GhostSession` state machine with cancellation token.

## [0.1.0] — 2026-03-01

- Project inception.
- Proof-of-concept Alt+M hotkey interception on Windows.
