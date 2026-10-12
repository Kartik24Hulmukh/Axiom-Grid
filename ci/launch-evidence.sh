#!/usr/bin/env bash
# Evidence producer, never an automatic GA/merge certification.
set -euo pipefail
PY=${PYTHON:-python3}
bash ci/pre-push.sh
"$PY" scripts/axiom_receipts.py verify examples/receipts/sample.json \
  --public-key examples/receipts/sample-public.pem \
  --checkpoint examples/receipts/sample-checkpoint.json
node --test phantom-overlay/tests/app.test.cjs
PYTHON="$PY" npm --prefix tests/browser test
AXIOM_BROWSER_AUTH_TEST=1 PYTHON="$PY" npm --prefix tests/browser test
"$PY" scripts/launch_torture.py --concurrency 100 --output launch-evidence/tcp.json
