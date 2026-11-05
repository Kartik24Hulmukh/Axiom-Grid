# Experimental local code preview — validation limits

**Development only; not release-qualified.** This branch pairs VS Code Lite with a focused runtime that supports an explicit `code` mode. Use matching versions: the new extension sends `mode: code`, which older runtimes reject. The development extension version is 0.1.3; do not treat it as a signed or published release. The API's public Rust request struct also changes shape and source-level consumers need review.

Code mode requests a neutral prompt, temperature 0, seed 7, a 1,024-token ceiling and `think: false`. Support for the latter varies with the model/backend. If a code response reports a `done_reason` other than `stop`, the runtime rejects it. Missing or null reasons are accepted for backward compatibility and do **not** prove completeness; a backend can misreport as well. Requests omitting mode retain the previous writing prompt and decoding settings. Suggestions still require user review and acceptance; they are not compiled, tested or executed automatically.

## Observed exploratory desktop tests

On Linux x86-64, 2 vCPUs, approximately 4.2 GiB RAM, no GPU, VS Code 1.145.0 and local Ollama 0.40.13, with a disposable profile:

- Qwen3.5 2B Q8, a multimodal model, could not load for the previously seen `parseDuration` task; the container recorded an OOM kill and no preview was produced.
- Qwen3 1.7B for the same task produced no preview within the runtime's 90-second request deadline.
- Qwen3 1.7B on a separately predeclared color-validator task showed a preview in 15.7 seconds; no edit occurred before acceptance and Tab inserted it. The accepted JavaScript failed at module load (`ReferenceError`), so none of the ten functional cases ran. A preview is not a correct solution.

These are single exploratory attempts, including a warm-model shorter-task run, not held-out benchmarks or generalized latency measurements. The UI test installed the 0.1.2-labeled build before a metadata-only bump to 0.1.3; the 0.1.3 VSIX has not itself been installed in the GUI. The test used basic password storage and a temporary token in an isolated disposable profile; it is not a production credential-storage assessment.

## Open release gates

Correctness across fresh representative tasks, reliable startup and completion on actual target devices, useful diagnostics, signed and supportable installation, cross-platform and integration qualification, supply-chain and security review, and real customer validation all remain open. Reported model identity is not backend or model-byte attestation. No production, frontier-quality or traction claim follows from these tests.
