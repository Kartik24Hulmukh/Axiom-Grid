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
$PY -m ruff check overlay/server.py kernel/sidecar/melious_router.py overlay/tests/test_server_wave11.py kernel/tests/test_melious_router_wave11.py scripts/stress_wave11.py
echo [3/4] focused runtime suites under strict resource warnings
$PY -m pytest -q -p no:cacheprovider overlay/tests kernel/tests -W error::ResourceWarning -W error::pytest.PytestUnraisableExceptionWarning
echo [4/4] real-model runner syntax
$PY -m py_compile scripts/axiom-live-e2e.py
echo PRE-PUSH GATE: PASS
