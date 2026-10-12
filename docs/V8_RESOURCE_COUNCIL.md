# Axiom v8 resource-lifetime review — final, frozen after cycle 3

## Isolation and delivery

- Base: parent `/data/axiom-integration` HEAD `b7653ac`.
- Requested worktree did not exist; created `/data/axiom-v8-resource-fix`, branch `fix/axiom-v8-resources`, at that base. Parent checkout was not edited.
- Committed socket fix: `b2a680f` (`fix(airgap): close probe sockets on denied connections`).
- Committed loader and regressions: `fca6db502c74f54962aa4d5023cdf27684176a02` (`fix(embeddings): own local Model2Vec asset lifetimes`). Files: `kairo/core/model2vec_assets.py`, `kairo-sidecar/sidecar/model_paths.py`, `kairo/docintel/retrieval.py`, `tests/test_model2vec_asset_lifecycle.py`. The retained `/data/axiom-v8-resource-loader-draft.patch` is historical checkpoint evidence, includes the pre-correction failing test, and is **not** the final delivery; use the commits.
- Existing `/data/axiom-venv/bin/python` used read-only; no package install/upgrade, third-party source edit, or parent venv modification.

## Root causes and bounded changes

### Socket ownership (committed)

`connect()` is deliberately denied and raises, so trailing `close()` was unreachable. Socket creation now uses context managers in:

- `tests/test_airgap_ci.py`: both configured-endpoint and denied-endpoint RestrictedSocket instances.
- `tests/test_airgap_zero_egress.py`: real connection-attempt monitor probe.
- `kairo/oracles/airgap_egress.py`: `run_kill_proof` external socket probe.
- `kairo/oracles/production_ops.py`: telemetry kill-proof external socket probe.
- `kairo-sidecar/tests/test_airgap_egress.py`: direct interceptor denied-connect regression.
- `kairo-sidecar/tests/test_offline_mode.py`: test-owned offline-mode socket.

Targets, denied-egress assertions, interception policy, exception handling, and warning policy are unchanged. No provider/auth calls or actual external egress were initiated; external-address probes remain blocked by the existing interceptors. Localhost DNS checks in the existing kill-proof tests remain intact.

### Model config ownership (committed)

Installed Model2Vec is **0.9.0**. Read-only inspection confirmed `model2vec/persistence/persistence.py:130` calls `json.load(open(selected_layout.config))`. Its upstream load path also opens the safetensors container without a context manager.

No cached candidate wheel was found. No fixed upstream version is claimed or pinned. To honor the no-external-egress constraint, no wheel download was attempted. If parent chooses a dependency solution, candidate wheels must be downloaded/inspected and reported before any isolated installation or requirement change; no unverified upgrade should be inferred from this review.

Repository-owned loader supports only the existing flat local model2vec layout. Uses public `StaticModel(...)`, `Tokenizer.from_file`, `safetensors.safe_open` context manager, and UTF-8 config file context manager. Keeps original tensors, optional weights/mapping, config normalization, and metadata fields. No quantization/dimensionality transform or hub resolution. Missing local assets fail locally. Both sidecar shared loader and repository-only retrieval fallback use it; offline environment handling remains unchanged.

API compatibility was inspected/tested with installed 0.9.0 only; requirements currently allow older releases (`model2vec>=0.1.1`), which were not tested. Parent independently reviewed and accepted the loader design for this integration; older dependency releases still need a compatibility gate if supported. No dependency requirements were changed.

## Exact relevant failures from expanded broad log

Source: `/data/axiom-v8-merged-scoped-broad.log`.

- ERROR: `TestAskYourDocsPdf.test_correct_answer_with_citation[What was the total revenue in fiscal year 2025?-$42.7 million-1]` setup — config resource warning.
- `TestAskYourDocsPdf.test_offline_mode_works` — config resource warning.
- `TestAskYourDocsPdf.test_secure_mode_fails_loudly_without_sidecar` — config resource warning.
- `TestTrustStack.test_airgap_zero_egress` — oracle probe socket.
- `TestByoKeyEgress.test_cloud_mode_egress_only_to_configured_endpoint` — two RestrictedSocket handles.
- `test_egress_monitor_catches_real_connection_attempt` — socket.
- `TestCanaryEgress.test_forced_egress_caught` — oracle probe socket.
- `TestAirgapTelemetryKillProof.test_forced_telemetry_send_caught` — telemetry probe socket.
- `TestAirgapTelemetryKillProof.test_kill_proof_report_not_passing` — telemetry probe socket.
- `TestInjectionBlocked.test_injection_payloads_blocked_in_semantic_store` — config resource warning.

Separate non-resource broad failure `TestScriptedDemo.test_demo_has_redline_command` was not changed or rerun here; parent owns it and the broad gate.

## Validation / bounded cycle accounting

1. `/data/axiom-v8-resource-cycle1.log`: collection failed because selector `TestKillProof` should have been `TestKillProofs`; exit 4, **no tests ran**.
2. `/data/axiom-v8-resource-cycle2.log`: **48 passed, 1 failed in 2.17s**, exit 1. Every original relevant resource failure passed, including frozen real PDF answer/citation tests, real semantic-store injection rejection, blocked-egress kill-proofs, and real local/upstream model equivalence. Sole failure is the NEW repo-only regression calling nonexistent `_init_embed_backend`; the actual method is `_init_embedding`. This test failed before exercising the fallback.

Stopped implementation/retesting and checkpointed to parent after cycle 2, per the requested bound. Parent then explicitly authorized resource cycle 3/5: only correct the new test method name, rerun the complete identical narrow suite, and freeze afterward. No runtime code changes were made after that checkpoint.

3. `/data/axiom-v8-resource-cycle3.log`: **49 passed in 2.58s**, exit 0. The corrected repo-only-layout regression now executes and passes. Same complete command/selection and both error-warning flags as cycle 2. No skipped tests, failures, warnings, or broad/load/benchmark run. New regression module contains 5 passing cases. Runtime/module work frozen after cycle 3; no cycles 4 or 5 used. Prior two logs retained unchanged.

The **narrow** resource gate is green. Parent alone owns the broad gate.

Command for cycle 2, from isolated worktree:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 KAIRO_NO_NET=1 KAIRO_REQUIRE_SEMANTIC=1 \
PYTHONPATH="$PWD:$PWD/kairo-sidecar" /data/axiom-venv/bin/python -m pytest -q \
-W error::ResourceWarning -W error::pytest.PytestUnraisableExceptionWarning \
tests/test_model2vec_asset_lifecycle.py tests/test_airgap_ci.py tests/test_airgap_zero_egress.py \
tests/test_acceptance_gauntlet.py::TestTrustStack::test_airgap_zero_egress \
tests/test_canary_break.py::TestCanaryEgress \
tests/test_production_ops_oracles.py::TestAirgapTelemetryKillProof \
tests/e2e/test_ask_your_docs_pdf.py \
kairo-sidecar/test_domain10_memory.py::TestInjectionBlocked::test_injection_payloads_blocked_in_semantic_store \
kairo-sidecar/tests/test_airgap_egress.py::TestKillProofs \
kairo-sidecar/tests/test_offline_mode.py
```

No warning suppression, mocked model, deleted tests, broad test retry, benchmark/full workload, or latency-threshold change. The equivalence test owns upstream's existing unclosed file using `ExitStack` around `builtins.open` in the reference harness only; it calls actual unmodified upstream `StaticModel.from_pretrained` and actual encode. It asserts exact tensor/config/tokenizer/metadata/embedding equality with network methods denied.

`git diff --check`: clean. Ruff `E9,F` passes for new loader, new regression module, and sidecar model_paths. Including retrieval.py reveals two PRE-EXISTING unused imports (`dataclasses.field`, `typing.Optional`) which were not changed as unrelated cleanup; original lint report: `/data/axiom-v8-resource-lint.log`.

## Preserved assets / ground truth

No diff to any vendored assets or `tests/e2e/test_ask_your_docs_pdf.py`.

SHA-256:

- config.json: `2a6ac0e9aaa356a68a5688070db78fc3a464fefe85d2f06a1905ce3718687553`
- model.safetensors: `f65d0f325faadc1e121c319e2faa41170d3fa07d8c89abd48ca5358d9a223de2`
- tokenizer.json: `e67e803f624fb4d67dea1c730d06e1067e1b14d830e2c2202569e3ef0f70bb50`

## Parent handoff

Cherry-pick, in order:

1. `b2a680f329a1ecd9d1bf8af0c44ee42d52e2deae` — socket ownership and affected test cleanup.
2. `fca6db502c74f54962aa4d5023cdf27684176a02` — reviewed local loader, both production entry paths, and 5 real-model/lifecycle regression cases.

Final exact narrow result: **49 passed in 2.58s**. Working tree clean. Frozen after cycle 3 as authorized. Parent owns final integration and broad warning gate; no release-wide green claim is made.
