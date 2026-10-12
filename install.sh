#!/usr/bin/env bash
# Local Linux developer Python setup, not a signed release installer.
# Linux clean-host installation is NOT CI-verified by this script.
# macOS is NOT verified; Windows is NOT verified: both fail closed.
# Read docs/LOCAL_INSTALL.md, review the checkout and local wheelhouse first.
set -euo pipefail
if [[ -z "${BASH_SOURCE[0]:-}" || ! -f "${BASH_SOURCE[0]}" || -L "${BASH_SOURCE[0]}" ]]; then
    echo "Use a reviewed local checkout; piped or symlink installers are refused." >&2
    exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3.11+ must already be installed; no bootstrap is downloaded." >&2
    exit 1
fi
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -L)"
# The shared engine checks the source root, prerequisites and fresh destination.
# It installs requirements.txt and requirements-test.txt from offline wheels,
# then requires import kernel, import packs, import bench and
# tests/test_corpus_integrity.py before reporting environment preparation.
exec python3 -I "$SCRIPT_DIR/install.py" --python-env "$@"
