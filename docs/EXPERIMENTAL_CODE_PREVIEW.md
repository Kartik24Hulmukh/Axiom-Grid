# Experimental local code preview — validation limits

**Development only; not release-qualified.** This branch pairs VS Code Lite with a focused runtime that supports an explicit `code` mode. Use matching versions: the new extension sends `mode: code`, which older runtimes reject. The development extension version is 0.1.3; do not treat it as a signed or published release. The API's public Rust request struct also changes shape and source-level consumers need review.

Code mode requests a neutral prompt, temperature 0, seed 7, a 1,024-token ceiling and `think: false`. Support for the latter varies with the model/backend. If a code response reports a `done_reason` other than `stop`, the runtime rejects it. Missing or null reasons are accepted for backward compatibility and do **not** prove completeness; a backend can misreport as well. Requests omitting mode retain the previous writing prompt and decoding settings. Suggestions still require user review and acceptance; they are not compiled, tested or executed automatically.

## Observed exploratory desktop tests

On Linux x86-64, 2 vCPUs, approximately 4.2 GiB RAM, no GPU, VS Code 1.145.0 and local Ollama 0.40.13, with a disposable profile:

- Qwen3.5 2B Q8, a multimodal model, could not load for the previously seen `parseDuration` task; the container recorded an OOM kill and no preview was produced.
- Qwen3 1.7B for the same task produced no preview within the runtime's 90-second request deadline.
- Qwen3 1.7B on a separately predeclared color-validator task showed a preview in 15.7 seconds; no edit occurred before acceptance and Tab inserted it. The accepted JavaScript failed at module load (`ReferenceError`), so none of the ten functional cases ran. A preview is not a correct solution.

A later single exploratory run installed the updated 0.1.3 VSIX in a fresh Linux VS Code 1.145.2 profile and used Qwen2.5-Coder 1.5B Q4_K_M on the same resource class. For a separately predeclared port-validation task, a cold-model preview appeared in 19.6 seconds; no edit occurred before acceptance, and Tab inserted the code. The generated function passed 11 of 15 fixed cases, incorrectly accepting whitespace, a plus sign and a decimal point. The initial automation read an empty file during the save and marked its insertion check false; the screenshot and stable file checked after the app closed show insertion. The original harness result is preserved alongside that follow-up, not overwritten.

These are single exploratory attempts, including one warm-model shorter-task run, not held-out benchmarks or generalized latency measurements. The earlier UI test installed the 0.1.2-labeled build; the later run installed the modified 0.1.3 VSIX. Both used basic password storage and temporary tokens in isolated disposable profiles; neither is a production credential-storage assessment. Reported model identity checks are not byte attestation.

## Open release gates

Correctness across fresh representative tasks, reliable startup and completion on actual target devices, useful diagnostics, signed and supportable installation, cross-platform and integration qualification, supply-chain and security review, and real customer validation all remain open. Reported model identity is not backend or model-byte attestation. No production, frontier-quality or traction claim follows from these tests.
