# Observed CPU API qualification experiments

## Decision

**A real-model API path is now observed working; the product is not production qualified.**
The actual runtime at `8af356a796ef3a3bc29be6921d74f60e4ea17072` was built with
locked dependencies and official checksum-verified Rust1.98.1 tools, then connected
to a privately provisioned Ollama0.40.13 CPU backend. No inference response was
mocked. No application dependency, installer, automatic download, insertion or
capture capability was added.

Use this as a concrete next qualification baseline, not as a default-model
endorsement or minimum hardware certification. The next recommended qualification step is
an actual supported desktop window and permitted workflow on a named user device.

## Environment and model selection

The observed agent sandbox was Linux x86_64,2 logical/affinity-visible CPUs
(reported Intel Xeon2.90GHz), with a4GiB observed cgroup memory.max and no GPU
detected in the checked device paths. CPU inference was observed separately in
the runner/loaded-model evidence. These are not specifications of the user's
college or personal machine. Host-visible RAM, shared cgroup usage, reclaimable
cache, installed RAM and guaranteed usable headroom are different quantities.

For the execution experiment, small Qwen2.5 Instruct quantizations were selected
instead. They are **not claimed to be frontier-equivalent**:

| Artifact | Pinned reported-identity expectation |
|---|---|
| `qwen2.5:0.5b` | `a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67` |
| `qwen2.5:1.5b` | `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b` |

Primary model cards:
https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct
https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct

The Ollama archive was pinned from official v0.40.13 release metadata:
https://github.com/ollama/ollama/releases/tag/v0.40.13

Archive SHA256:
`c9490e0f520be21271d969e6703f012268b1d39f8b70dd58854e5bfef7a75bb6`.
Model manifests were retrieved from the publisher registry and hashed **before**
checking live inventory; every referenced blob's size and SHA256 was verified.
This is publisher-HTTPS/checksum provenance, not a signed release authorization,
weights attestation, complete license clearance or trust-on-first-live-inventory.
The artifacts remain outside the product repository. No paid API/GPU was used.

## Chosen application and actual task

Application: Axiom-Grid's explicit-context writing-preview runtime.
Task: draft an honest collaborator update for the actual PR46 work.
The exact prompt/rubric was recorded before either selected-task generation;
see [the evidence record](evidence/CPU_API_EXPERIMENTS.json). Exact raw reports,
predeclared prompt and historical harness bytes are publicly retrievable through
its `raw_evidence` links. A separate evidence ZIP is also supplied to the requester;
it contains no backend/model/toolchain binaries, private homes or pairing files.

Required facts: PR46 merged; pairing/HTTP diagnostics improved; all required CI
passed; production qualification **not complete**; target-device trial is next.
No invented dates, customers, availability, certification or performance claims;
message only and at most100words.

### Sole0.5B answer — reject

HTTP200 did not mean usefulness. Its54-word answer omitted PR46,CI success and the
critical production limitation, and added unsupported monitoring/performance
claims. The unchanged20-prompt API smoke sweep passed mechanically, but that
cannot rescue this selected-task semantic failure. Do not approve this model for
fact-preserving project updates on the basis of its API pass.

### Sole1.5B answer — accepted for this rubric only

> PR46 merged; pairing and HTTP recovery diagnostics improved; all required CI checks passed; production qualification not complete; next step: target-device trial.

The21-word answer retained every specified fact without additions. A separate
assistant reviewer accepted it under the frozen rubric. This is not human/customer
validation, a polished-copy preference study or general model-quality proof.

Only one selected answer was produced per model; neither was repaired. The0.5B
selected task was warm after its smoke sweep. The1.5B answer was the first model
load in an isolated run, with potentially warm filesystem cache. Both loaded
reports show2048-token context. Settings/profiles and timing conditions must not
be represented as a model-size-only causal or latency comparison.

## Preserve the entire verdict ledger

| Experiment | Recorded verdict |
|---|---|
|0.5B original20-prompt probe | Mechanical pass: auth/input/schema/generation/cancel acknowledgement/recovery |
|0.5B selected answer | **Semantic fail**, including missing production limitation |
|1.5B isolated run1 | **Overall mechanical fail** after selected answer: process-observation harness missed runner |
|Sole1.5B selected answer in run1 | Semantic pass under the predeclared rubric |
|1.5B isolated run2 |18 mechanical checks pass and unchanged20-prompt probe pass; selected task **not repeated** |

Initial preparation also omitted SONAME symlinks when extracting regular files
from the verified backend archive. An early GPU-discovery helper exited127.
Required relative library links were restored from that same verified archive;
subsequent helper and actual inference worked. Preserve this preparation issue;
do not present it as a continuing runtime/model defect or erase the warning.

Run1's harness read only the leader task's child list, missing a runner launched
by another thread. Run2 traversed every task directory, deduplicated PIDs and
failed on omissions/truncation. It observed Ollama,`llama-server` and the actual
runtime in the new namespace. This is a point-in-time observation, not continuous
tracing, and cannot retroactively repair run1's failed observation gate.

## What the network-isolated experiment establishes

Before launching either service/probe, run2 created a fresh network namespace,
enabled only loopback, checked kernel-visible interfaces and no external IPv4
routes, checked no inherited socket descriptors, set `NoNewPrivs=1`, and dropped
all effective/permitted/bounding capabilities. Numeric external TEST-NET IPv4 and
IPv6 connects returned `ENETUNREACH`. Normally launched services/runner/probe
inherited that boundary. Fresh backend loaded-model inventory was empty before
inference; assets were provisioned beforehand.

**Bounded claim:** the recorded runtime/backend workflow completed real-model CPU
API inference in a fresh loopback-only network namespace, with external IPv4/IPv6
connectivity denied. This is not hostile-code confinement: shared filesystem and
possible Unix-socket IPC were not isolated. It is not a native desktop, whole-
product offline, installer, offline provisioning or backend-attestation certificate.

The original probe conservatively retains `offline_operation_verified=false`;
its HTTP checks alone cannot attest the external boundary. The separate namespace
record supplies scoped additional evidence. Run2's inherited semantic-review
placeholder is inapplicable: it was a mechanical experiment and did not repeat
the selected answer. Keep raw files unchanged and use this ledger to interpret them.

Missing the selected model manifest yielded readiness200/false and generation503;
restoring it returned readiness. Completed backend generation-log entries stayed
22→22 during rejection. That log count is supporting evidence only, not direct
proof that a canary was absent from backend ingress. Both direct services exited0.
Recorded shared-cgroup OOM/OOM-kill counters stayed zero; no memory-headroom or
model-exclusive peak claim follows from that result.

## Reproduction and remaining gates

Keep exact artifact/revision pins and approve their rights/configuration separately
under [MODEL_IDENTITY_POLICY.md](MODEL_IDENTITY_POLICY.md). Start a deliberately
configured private backend/runtime; do not infer approval from its first inventory.
The existing smoke probe can then run without modifying its assertions:

```sh
python3 -B scripts/axiom-live-e2e.py --output new-evidence.json
```

It requires the configured model/backend and private pairing. It can generate up
to2048tokens per request over20prompts plus cancellation/recovery; bound resources
and duration before running. Never put a pairing token in a command argument or
public evidence. A cold backend/model start is not necessarily a cold filesystem.
Historical harness source is stored as `.py.txt` under the raw evidence directory.
It uses experiment-specific absolute paths and is not a portable product command.
The external namespace harness is an authorized lab experiment, not a product
installer or a recommendation to run the desktop with elevated privileges.

Still required before product-level readiness:

1. Actual Tauri window, shortcut behavior, explicit input, review/manual copy,
   clear/discard and error recovery on a named supported native OS/device.
2. Broader representative factual-fidelity tests, adversarial inputs and honest
   failures with stronger models; one accepted short answer is insufficient.
3. Target-device resource/long-session/retention checks, backend cancellation
   observation and platform-specific credential custody.
4. Installer/upgrade/rollback/uninstall, complete supply-chain/license review and
   external-network enforcement for the actual supported deployment.
5. Consent-based recurring task trials measuring correction cost, usefulness,
   repeat use and willingness to pay. CI does not establish traction or100x value.

The next smallest useful step is the native desktop trial, not importing a suite
launcher/provider registry. Prior [integration decisions](INTEGRATION_DECISIONS.md)
remain unchanged. See [device qualification](DEVICE_QUALIFICATION.md) and
[release qualification](RELEASE_QUALIFICATION.md).
