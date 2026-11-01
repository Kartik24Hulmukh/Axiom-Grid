# Axiom Grid Lite — VS Code prototype

A model-free, dependency-free extension for **explicitly requested inline code previews** through an existing local Axiom runtime. It does not implement systemwide typing. This is an unsigned development VSIX, not a Marketplace-verified, signed or production-qualified release.

## What you need

- Desktop VS Code 1.96 or newer on an authorized device; a trusted local workspace and local `file:` editor. Web, SSH/containers/remote, virtual files, multi-cursor and selected-range requests are intentionally unsupported.
- An already running, compatible Axiom runtime on `127.0.0.1:7437`.
- The runtime's Ollama service on `127.0.0.1:11434`, an installed approved model, and independently approved expected model digest. No weights or runtime executable are bundled with this VSIX.
- The runtime's existing **64-hex IPC pairing token**, not a GitHub PAT or model-service key.

If you have none of those prerequisites, installing the VSIX alone does not supply a model or running service. Ask for a runtime build for your actual OS/CPU architecture; do not download the monorepo or a Rust/Node toolchain merely to install this extension. A developer can build the focused runtime using the repository's `axiom-runtime` build instructions, but source builds have separate toolchain/crate downloads.

## Install the small extension

In VS Code: Extensions → `…` → **Install from VSIX…** → select `axiom-grid-lite-0.1.2.vsix`. Review the local/unverified-publisher warning; do not disable OS security policies. Alternatively, with the desktop VS Code CLI already installed:

```sh
code --install-extension "/path/to/axiom-grid-lite-0.1.2.vsix"
```

Use only on a device/workspace you are authorized to use. Do not install in a prohibited assessment or managed environment without approval.

## Pair and use

1. Start your existing runtime with `AXIOM_MODEL` and `AXIOM_MODEL_DIGEST` set to the exact approved installed identity. The runtime performs its own inventory checks before every generation. Do not treat copying the first inventory digest as independent approval.
2. Under supported Unix pairing, the runtime prints its local pairing-file location. Open that file privately on your device and use its existing token. Windows currently needs explicitly provisioned shared-token setup; follow `QUICKSTART.md` and `docs/NATIVE_RECOVERY_POLICY.md`. Do not paste tokens into chat, source, settings, issue reports or command arguments.
3. Command Palette → **Axiom: Set Runtime Token**. Enter that runtime token in the masked input. The extension uses VS Code `SecretStorage`, never a normal setting. Its security depends on the host's implementation; this is not an independently verified cross-platform credential-storage guarantee.
4. Open a local source file. For example, create a disposable JavaScript file containing `function sum(a, b) {` and place the cursor at the end, with no selection.
5. Press **Ctrl+Alt+K** while the local file editor has focus (macOS: Control+Option+K), or use Command Palette → **Axiom: Suggest Code at Cursor**. This explicitly authorizes sending the bounded nearby file text to your local runtime. Do not use it on private material you have not approved for that backend.
6. Review the inline suggestion. Use VS Code's **Accept Inline Suggestion** action (normally Tab) only if you want it inserted. The extension does not save or execute the code. Keyboard mappings/settings can differ; inline suggestions must be enabled in your editor.
7. Use **Axiom: Discard Suggestion** to invalidate Axiom's cached preview/request. A progress notification's Cancel also discards locally. Escape may hide the editor UI but is not a verified backend cancellation mechanism.

Model quality and latency are not established by the disposable example. This prototype uses an instruction prompt with prefix/suffix text, **not native fill-in-the-middle model tokens**. The runtime's current writing-oriented system prompt is unchanged. Do not assume a base FIM model is a drop-in replacement. Use an already approved instruction-following model for initial tests; no new model is selected or silently downloaded.

## `// instruction` workflow (JavaScript/TypeScript)

In a local JavaScript, TypeScript, JSX or TSX file, type a standalone line:

```js
// create a function that returns the sum of two numbers
```

Leave the cursor at the **end of that line**, then press **Ctrl+Alt+K** (macOS: Control+Option+K). The nonblank text after `// ` is sent as your explicit instruction, not merely as code to continue. Review the inline code preview, then accept through VS Code (normally Tab). The comment stays in the document; the preview inserts below it, not inside the comment. This does not edit, save or execute code automatically.

This is a request shortcut **after typing** the instruction, not a background “armed” mode. No keylogger, passive comment scanning or retrospective search for an older `//` line is added. Ordinary non-marker continuation remains available through the same command.

Limits: current marker line at most 1,024 UTF-16 code units, including indentation; at least one space/tab after the two slashes and a nonblank instruction; one cursor at end of line. Bare/malformed markers, `///`, `//!`, `//?`, unsupported languages, unsafe controls and overlong marker lines reject without loading the credential or sending context. The first 1,025 units are inspected to detect a marker without reading an unbounded line. Excessive indentation with only whitespace or a possible split slash delimiter in that probe is conservatively refused. Ordinary long code lines can still use continuation mode.

Recognition is **textual, not lexical**: a line beginning with `// ` inside a multiline template string is still treated as an explicit instruction when you invoke the command. Do not invoke it there unless that is your intention. It does not prove the line is a JavaScript comment.

Only the current marker line is removed from the source-prefix portion of the request; earlier comments remain bounded source context. The client prefixes the document's LF/CRLF and the comment indentation to the **first generated line only**; internal output, line breaks and indentation remain unchanged. The entire composed candidate must fit 4,096 Unicode scalars or it is rejected, never truncated. This is not whole-block formatting or syntax validation. Edit, cursor move, focus change, cancellation and pairing changes retain the same stale-result suppression.

The Kairo-Phantom slash-instruction UX informed this narrow feature. Its global hooks, automatic injection, mutable model pulls and legacy installers were not imported. Existing local runtime/model prerequisites still apply.

## Exact boundaries

- No inference on activation, typing, passive provider calls or file changes. Only the explicit Axiom command starts a request.
- Transmits source context from at most 6,000 UTF-16 units before and 2,000 after the cursor, with boundary-surrogate trimming. An additional local-only initial-line probe reads at most 1,025 units for mode detection; this is a separate read bound and is not automatically added to transmitted context. No workspace indexing, filename transmission or other-app capture. This can still include secrets from an active source file: inspect the context you authorize.
- The complete wrapped prompt must fit 16,000 Unicode scalars. The client accepts at most 4,096 output scalars; any composed comment candidate must also fit 4,096 scalars and rejects disallowed controls/bidi formatting. These are input/display bounds, **not backend compute caps**; the existing runtime can request 2,048 generated tokens and take up to its deadline.
- Fresh authenticated readiness per explicit request, including consistency of the reported selected inventory; then the runtime independently performs fresh identity preflight. This is reported consistency, not model/backend attestation.
- No configurable network host, proxy, redirect or cloud fallback. Uses numeric IPv4 loopback HTTP with the pairing token. This does not prove that the backend, VS Code or other extensions cannot use the network.
- Edit, cursor/selection change, active-editor change or credential change invalidates the candidate. Results are bound to URI, version and cursor. A cached candidate may redisplay at the same unchanged snapshot without another request; an accepted edit changes version and invalidates it.
- One local pending request. Local abort disconnects HTTP; it does not call the runtime's shared global `/cancel`, stop backend inference, prove erasure, or guarantee immediate runtime capacity. A subsequent request may legitimately receive busy/unavailable.
- Built-in `editor.action.inlineSuggest.trigger` and `hide` are editor-wide and may also affect other providers. For an attributable trial, use a disposable file and manage other inline providers explicitly. This extension does not silently disable them.
- Literal string completion and a zero-width insertion range only: no snippets, attached commands, shell/terminal, clipboard, automatic file edits, automatic acceptance or saving.

## Recovery and uninstall

Errors are static codes; raw runtime bodies, OS errors, file paths and token values are not shown by this extension. Confirm the runtime/model is running and approved, verify pairing, then explicitly request again. No automatic retry/download occurs. Do not guess that 503 means a particular backend or identity cause.

**Axiom: Forget Runtime Token** removes this extension's stored credential; it does not revoke the runtime token or remove other retained copies. Disable/uninstall the extension through VS Code. Backend logs, model state, editor undo buffers and other software retention are separate.

## Validation status

The release handoff records actual test/package results. Node mocks, state tests, VSIX ZIP/XML checks and HTTP mocks are not actual VS Code-host installation, native OS or real-model coding evidence. No minimum-RAM, latency, universal OS compatibility, frontier-quality or production claim is made.

No runtime binary, model weights, training tools, Python document services, Storytold applications, telemetry SDK or npm runtime dependencies are included.

## One-command setup: exact current status

With desktop VS Code and the already configured runtime/model prerequisites, client installation is one command:

```sh
code --install-extension "/path/to/axiom-grid-lite-0.1.2.vsix"
```

Then pair once using the masked command above and use Ctrl+Alt+K in a local editor. Tab acceptance remains explicit. The shortcut is editor-scoped, not a global OS hotkey; custom keyboard mappings, AltGr layouts, OS shortcuts and extensions may conflict. Use VS Code Keyboard Shortcuts to resolve a conflict without disabling OS security restrictions.

**This does not automatically provision the runtime, Ollama or weights.** At this implementation checkpoint, the repository’s public releases have no binary assets. Do not invent a curl-to-shell installer or substitute inventory-derived model identity for independent model approval. A complete installer needs tested per-OS/CPU runtime binaries, release authorization, backend/model provisioning with a disclosed download size, secure pairing and real target-device validation. Those gates remain open. Windows/macOS/Linux are different targets; one command cannot guarantee native support on every device.

No model is silently selected or downloaded by this extension. Runtime/model storage and memory requirements are separate from the small VSIX.
