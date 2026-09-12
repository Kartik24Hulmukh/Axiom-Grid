# Axiom Grid — Kairo Phantom CUA Premortem Analysis

This document provides a comprehensive pre-mortem analysis of the Computer Use Agent (CUA) system.
It covers 19 identified risks across engineering, deployment, and operational boundaries,
along with 15 concrete, implemented, and fully tested mitigations.

---

## 1. The 19 Critical Risks (CUA Threat Model)

### Risk 1: UI Layout Shift and Selector Fragility
- **Description:** Dynamic layout updates, popups, or responsive resizing alter target element locations.
- **Severity:** High
- **Probability:** High

### Risk 2: Operating System and Application Version Drift
- **Description:** System updates or software upgrades change native accessibility elements and identifiers.
- **Severity:** Medium
- **Probability:** Medium

### Risk 3: Non-Deterministic VLM Grounding Errors
- **Description:** The Vision-Language Model fails to accurately ground a textual target into screen coordinates.
- **Severity:** High
- **Probability:** High

### Risk 4: Concurrent Human-Agent Input Interleaving
- **Description:** A user interacts with the keyboard/mouse simultaneously with the agent's actions, leading to focus stealing.
- **Severity:** Critical
- **Probability:** High

### Risk 5: Infinite Loop and Resource Exhaustion in Execution
- **Description:** The agent enters a repetitive state loop due to visual confusion or unhandled errors.
- **Severity:** Medium
- **Probability:** Medium

### Risk 6: Unexpected Hotkey and Keyboard Focus Collisions
- **Description:** Hotkeys trigger unwanted global operating system behaviors rather than application-local target events.
- **Severity:** High
- **Probability:** Low

### Risk 7: High Latency and Network Decoupling in VLM Calls
- **Description:** Network timeouts or cold-start load spikes cause VLM inference calls to hang.
- **Severity:** Medium
- **Probability:** Medium

### Risk 8: Destructive Action Execution without Confirmation
- **Description:** The agent triggers irreversible operations (e.g. file deletion, database drop) due to semantic misalignment.
- **Severity:** Critical
- **Probability:** Low

### Risk 9: Screen Resolution and Multi-Monitor Layout Fragmentation
- **Description:** Screen resolution disparities cause bounding box coordinates to scale incorrectly or exceed screen bounds.
- **Severity:** High
- **Probability:** Medium

### Risk 10: Application-Specific Shortcut Conflict and Override
- **Description:** Global agent hotkeys clash with standard shortcuts within target applications (Word, Excel, Canva).
- **Severity:** Medium
- **Probability:** High

### Risk 11: Clipboard Race Conditions and State Overwrites
- **Description:** Multiple concurrent workflows or a human user race to overwrite the system clipboard space.
- **Severity:** High
- **Probability:** Medium

### Risk 12: Memory Leakage and Accumulation in Long-Running Runs
- **Description:** Continuous model downloads and frame captures accumulate memory leaks in sidecar/orchestrator handles.
- **Severity:** Medium
- **Probability:** Low

### Risk 13: Security Bypass via Prompt Injection on Input Fields
- **Description:** Visual or document inputs contain adversarial payloads instructing the model to bypass safety constraints.
- **Severity:** Critical
- **Probability:** Medium

### Risk 14: Secret Leakage via Clipboard, Log, or Screenshot Artifacts
- **Description:** The agent records or logs sensitive credentials, keys, or private text in plain text or screenshots.
- **Severity:** Critical
- **Probability:** High

### Risk 15: Operating System Level Security Dialog Block
- **Description:** User Account Control (UAC) or admin elevation dialogues prevent automation drivers from taking control.
- **Severity:** Critical
- **Probability:** Medium

### Risk 16: Lack of Audit Trail and Post-Action Traceability
- **Description:** Missing grounding trace logs make it impossible to audit why a decision was reached by CUA.
- **Severity:** Medium
- **Probability:** Low

### Risk 17: Model Drift and Behavioral Inconsistency in Backend Inference
- **Description:** Model weights update or temperature changes introduce structural drift in extracted structured fields.
- **Severity:** High
- **Probability:** Low

### Risk 18: Dependency Vulnerabilities and Supply Chain Impairment
- **Description:** Malicious or outdated open-source dependencies introduce CVE exploits into local sidecar environments.
- **Severity:** High
- **Probability:** Medium

### Risk 19: File System Write Collision and State Corruption
- **Description:** Concurrent extraction pipelines attempt to write to the same SQLite-backed or file store concurrently.
- **Severity:** High
- **Probability:** High

---

## 2. The 15 Robust Mitigations

### Mitigation 1: Tiered CUA Fallback Hierarchy
- **Implementation:** Active fallback mechanism descending through Tier 0: File API, Tier 1: UIA, Tier 2: MCP, and finally Tier 3: VLM Grounding.

### Mitigation 2: UI Selector Re-anchoring and Adaptive Bounding Boxes
- **Implementation:** Dynamic search anchoring to pivot coordinates around stable visual elements if targets are shifted.

### Mitigation 3: Human-In-The-Loop Confirmation Guards for Destructive Actions
- **Implementation:** Endpoints require explicit `human_confirm=True` via `/apply` before performing critical operations.

### Mitigation 4: Non-Blocking Async File and I/O Operations
- **Implementation:** All filesystem checks and high-latency reads run inside `asyncio.to_thread` to prevent thread blocks.

### Mitigation 5: Concurrency Locks for Shared Database and State Connections
- **Implementation:** Explicit `threading.Lock` guards around orchestrator pipeline executions, preventing SQLite state corruption.

### Mitigation 6: Dynamic Screen Resolution Normalization and Bounding Box Rescaling
- **Implementation:** Auto-detects target resolution and scales visual grounding coordinates safely to local bounds.

### Mitigation 7: Keyboard-Only Mode During Model Download/Latency Spikes
- **Implementation:** Falls back to local native shortcut sequences when VLM downloading is active or latency exceeds thresholds.

### Mitigation 8: Automatic Cleanup of Dangling Processes and Memory Handles
- **Implementation:** Explicit cleanup routines to release GGUF loads and model context buffers immediately upon extraction completion.

### Mitigation 9: Strict Schema Validation on All External Endpoints
- **Implementation:** Enforces Pydantic model contracts with null-byte guards and text boundary checks on all endpoints.

### Mitigation 10: Fail-Closed Error Trapping and Logging Infrastructure
- **Implementation:** Standardized try/except handling with `logger.exception()` and JSON error responses, avoiding traceback leaks.

### Mitigation 11: Pre-Execution Static Checking for Shell Injection Vectors
- **Implementation:** Input filters reject file names containing pipe characters, semicolons, shell scripts, or raw backticks.

### Mitigation 12: Clipboard Mutex to Prevent Agent-Human Race Conditions
- **Implementation:** Safe acquisition lock for system clipboard, releasing the handle immediately after sequence completion.

### Mitigation 13: Real-Time Security Scanners for Secret Redaction
- **Implementation:** Sanitizes logs and databases using regex filters before writing execution traces to disk.

### Mitigation 14: Immutable Local Provenance Log for Non-Repudiation Audit Trails
- **Implementation:** Logs every UI step, bounding box, extracted field, and execution trace to an offline tamper-proof ledger.

### Mitigation 15: Active State Verification
- **Implementation:** Post-action visual checking to confirm if expected status messages actually appeared on screen.
