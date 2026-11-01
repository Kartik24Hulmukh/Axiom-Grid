# Development runtime bundles — a distribution gate, not an installer

The optional VS Code client is small, but requires a focused runtime executable,
backend, approved installed model and private pairing. This workflow addresses
only the **runtime binary + VSIX** part. It does not close the full setup gate.

## What the workflow does

`runtime-bundles.yml` checks the exact pull-request head or main commit, then uses
Linux, Windows and macOS hosted runners. It records the actual Rust host target
rather than assuming every macOS runner has the same CPU architecture. Only the
four explicitly supported Rust triples are admitted. This is not coverage of
every OS, CPU, distribution, desktop environment or minimum hardware profile.

Each runner performs formatting, focused runtime tests, Clippy, mocked extension
tests and packager tests before compiling a locked release runtime. Native tests
execute product code and may run test servers; they are not approved service
deployment, real-model inference or clean-device qualification.

**Binary artifact publication is disabled on all events, including manual
dispatch.** Successful runs report archive size and SHA-256 checksum only. No
boolean acknowledgment can replace a completed redistribution review.
Configured jobs are not evidence that they ran or passed: see the exact run.
No release is created and no signing, updater or installation authority is added.
Workflow repository permissions are read-only; no release credentials or elevated
repository permissions are granted. This is not a containment boundary for hostile
build scripts: compiling pull-request code can execute dependency/build scripts
with the ordinary hosted runner's privileges and network access.

The ZIP is a fixed, bounded allowlist:

- the focused `axiom-grid` executable (`.exe` on Windows);
- the model-free Axiom Grid Lite VSIX;
- the project's `LICENSE` and existing `THIRD_PARTY_NOTICES.md`;
- generated setup/limitations text and a hash/size manifest.

Binary-format/architecture checks prevent obvious mislabeling, not malicious
binary substitution or proof of execution. The supplied source revision is a
declared build input, not an attestation. Hashes are checksums, not signatures or
independent release authorization. Deterministic ZIP metadata does not establish
bit-reproducible Rust binaries. Existing notices are not a completed transitive
dependency/license or Windows runtime redistribution review.

## What a recipient still needs

Use only a bundle from a reviewed source/run on an authorized device. Extract
into a private directory; ZIP extractors and OSes differ in executable-mode
handling. Verify the declared checksums for accidental corruption, but do not
mistake that for publisher authentication or supply-chain clearance.

Desktop VS Code, a compatible separately provisioned Ollama backend and approved
installed model are still required. Set `AXIOM_MODEL` and independently approved
`AXIOM_MODEL_DIGEST` before starting the focused runtime. Never derive the expected
digest from the first untrusted inventory response. No model is downloaded or
selected by the bundle.

Unix pairing remains subject to its protected-file rules. Windows still requires
an explicitly provisioned token; the bundle does not implement protected Windows
pairing. Never publish tokens in issues, chat, manifests or process arguments.
See [model identity](MODEL_IDENTITY_POLICY.md) and
[the extension's setup instructions](../extensions/vscode-lite/README.md).

The extension-only installation command remains:

```sh
code --install-extension "./axiom-grid-lite-0.1.2.vsix"
```

That is **not** a one-command runtime/backend/model installer. Once existing
prerequisites are running and paired, a JavaScript/TypeScript `// instruction`
followed by Ctrl+Alt+K requests a preview; editor acceptance remains explicit.

## Still-open release gates

1. Complete a concrete redistribution review record for the exact revision,
   target and dependency/features, including required license texts and permitted
   distribution scope. Keep binary uploads disabled until that record is verified.
   Review native dependencies, signing/notarization and distribution requirements.
2. Provision a deliberately chosen model/backend pack with pinned provenance,
   disclosed download/storage size and explicit online setup approval. Never
   silently install multi-gigabyte weights or use cloud fallback.
3. Complete private automatic pairing, startup/recovery and removal on clean,
   real target devices without Rust, Node or Python development toolchains.
4. Observe actual VS Code installation, Ctrl+Alt+K, useful model output, explicit
   acceptance, stale-output suppression, controlled failure/recovery and quit.
5. Test disconnected cold startup with prepositioned assets and resource/latency
   measurements. Platform CI builds do not prove offline inference.
6. Obtain real task/user validation before claiming value, repeat use or traction.

Production qualification remains false. No frontier-quality, universal-device,
native-window, backend-stop, minimum-RAM or “100×” result follows from these bundles.
## Platform deployment limits

The matrix does not establish a Linux glibc baseline or shared-library availability,
Windows CRT availability, or a minimum macOS deployment target. Dynamic dependency
resolution, signing/notarization and clean-device launch remain unverified. A native
build on one runner is not a compatibility guarantee for older or other devices.
