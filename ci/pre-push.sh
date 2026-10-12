#!/usr/bin/env bash
# Axiom-Grid local pre-push gate (Session 16).
# Root cause closed: the local gate ran pytest but never ruff, so a lint-only
# regression (PLR1730 in kernel/sidecar/melious_router.py) reached CI and
# failed focused-runtime on the release head. Lint and tests now share one
# gate, executed from the repository root exactly as CI does (ruff
# first-party detection depends on cwd).
set -euo pipefail
test -f Makefile -a -d overlay -a -d kernel || { echo run from repository root >&2; exit 2; }
PY=${PYTHON:-python3}
echo [1/4] ruff E9,F broad gate
$PY -m ruff check --select E9,F overlay kernel kairo/context/compressor.py scripts/stress_sec006_gauntlet.py stress_test.py
echo [2/4] ruff changed-file gate, exact CI file set
$PY -m ruff check overlay/server.py overlay/request_policy.py overlay/admission.py overlay/telemetry.py overlay/document_store.py overlay/tenant_context.py kernel/sidecar/evidence_store.py kernel/sidecar/melious_router.py overlay/tests/test_server_wave11.py kernel/tests/test_melious_router_wave11.py scripts/stress_wave11.py
$PY -m ruff check --select E9,F install.py tests/test_packaging.py tests/test_root_install_boundaries.py tests/test_default_dependency_policy.py tests/test_legacy_epub_dependency_boundary.py tests/test_smoke_document_intake.py tests/security/test_lan_sync_disabled.py tests/security/test_enterprise_auth_fail_closed.py tests/test_kpx_export_contract.py tests/test_runtime_capacity_configuration.py tests/profile/pdf_absent_engine_guard.py kairo-sidecar/sidecar/exporters/kami_kpx.py kairo-sidecar/sidecar/parsers/pdf_extraction_engine.py
echo [3/4] focused runtime suites under strict resource warnings
$PY -m pytest -q -p no:cacheprovider overlay/tests kernel/tests tests/test_concurrency_safety.py tests/test_bench_corpus_hash.py tests/test_corpus_integrity.py tests/test_load_admission_primitives.py tests/test_load_request_policy_timing.py tests/test_disconnect_admission_race.py tests/security/test_storage_boundaries.py tests/security/test_lan_sync_disabled.py tests/security/test_enterprise_auth_fail_closed.py tests/test_smoke_document_intake.py tests/test_packaging.py tests/test_root_install_boundaries.py tests/test_default_dependency_policy.py tests/test_legacy_epub_dependency_boundary.py tests/test_kpx_export_contract.py tests/test_runtime_capacity_configuration.py -W error::ResourceWarning -W error::pytest.PytestUnraisableExceptionWarning
# This lane requires genuinely absent unsupported optional PDF engines.
# The harness fails rather than skips if the declared profile is not met.
$PY -I tests/profile/pdf_absent_engine_guard.py
echo [4/4] real-model runner syntax
$PY -m py_compile scripts/axiom-live-e2e.py
echo PRE-PUSH GATE: PASS
