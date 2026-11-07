# Experimental local code preview — validation limits

**Development only; not release-qualified.** This branch pairs VS Code Lite with a focused runtime that supports an explicit `code` mode. Use matching versions: the new extension sends `mode: code`, which older runtimes reject. The development extension version is 0.1.3; do not treat it as a signed or published release. The API's public Rust request struct also changes shape and source-level consumers need review.

Code mode requests an experimental prompt reminding the model to follow explicit validation, boundary and export requirements, plus temperature 0, seed 7, a 1,024-token ceiling and `think: false`. The prompt has not been shown to outperform the previous one. Support for `think: false` varies with the model/backend. If a code response reports a `done_reason` other than `stop`, the runtime rejects it. Missing or null reasons are accepted for backward compatibility and do **not** prove completeness; a backend can misreport as well. Requests omitting mode retain the previous writing prompt and decoding settings. Suggestions still require user review and acceptance; they are not compiled, tested or executed automatically.

## Observed exploratory desktop tests

On Linux x86-64, 2 vCPUs, approximately 4.2 GiB RAM, no GPU, VS Code 1.145.0 and local Ollama 0.40.13, with a disposable profile:

- Qwen3.5 2B Q8, a multimodal model, could not load for the previously seen `parseDuration` task; the container recorded an OOM kill and no preview was produced.
- Qwen3 1.7B for the same task produced no preview within the runtime's 90-second request deadline.
- Qwen3 1.7B on a separately predeclared color-validator task showed a preview in 15.7 seconds; no edit occurred before acceptance and Tab inserted it. The accepted JavaScript failed at module load (`ReferenceError`), so none of the ten functional cases ran. A preview is not a correct solution.

A later single exploratory run installed the updated 0.1.3 VSIX in a fresh Linux VS Code 1.145.2 profile and used Qwen2.5-Coder 1.5B Q4_K_M on the same resource class. For a separately predeclared port-validation task, a cold-model preview appeared in 19.6 seconds; no edit occurred before acceptance, and Tab inserted the code. The generated function passed 11 of 15 fixed cases, incorrectly accepting whitespace, a plus sign and a decimal point. The initial automation read an empty file during the save and marked its insertion check false; the screenshot and stable file checked after the app closed show insertion. The original harness result is preserved alongside that follow-up, not overwritten.

A subsequent exploratory comparison used Qwen2.5-Coder 1.5B with the same extension client and runtime decoding settings on two predeclared tasks: canonical IPv4 validation and HTTP method normalization. The old and experimental system prompts each passed all 15 fixed cases on each task; the IPv4 outputs were identical. These two ties do not establish an improvement or rule out regressions elsewhere. The cases were not sent to the model.

With the experimental runtime prompt, the already-built 0.1.3 VSIX was installed in a fresh VS Code 1.145.2 profile. On a separately predeclared byte-size formatting task, the warm model produced a preview in 12.2 seconds; no edit occurred before Tab acceptance, and the accepted JavaScript passed all 12 fixed cases after review. The fixed checks do not exhaust the specification. The save-wait race identified in the prior trial was corrected in the test harness before this run.

These are single exploratory attempts, including warm-model runs, not held-out benchmarks or generalized latency measurements. The tasks were selected after previous failures. Desktop tests used basic password storage and temporary tokens in isolated disposable profiles; they are not a production credential-storage assessment. Reported model identity checks are not byte attestation. `scripts/preview-evaluation` provides a separate collection and explicitly review-gated manual scoring aid; its scorer executes code and is not a sandbox.

## Open release gates

Correctness across fresh representative tasks, reliable startup and completion on actual target devices, useful diagnostics, signed and supportable installation, cross-platform and integration qualification, supply-chain and security review, and real customer validation all remain open. Reported model identity is not backend or model-byte attestation. No production, frontier-quality or traction claim follows from these tests.
