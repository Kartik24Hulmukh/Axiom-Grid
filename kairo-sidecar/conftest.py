"""kairo-sidecar conftest — put the sidecar root on sys.path for every worker.

`kairo-sidecar/` is a hyphenated directory, so it can never be a Python
package and `sidecar.*` is only importable when this directory itself is on
`sys.path`. Running from `kairo-sidecar/` works because pytest's default
rootdir insertion does it implicitly; running the whole repository from the
root (CI, `--import-mode=importlib`, pytest-xdist workers) does not, which
surfaced as `ModuleNotFoundError: No module named 'sidecar'` across
`test_phase0_1_opik.py`, `test_phase_a_track.py`, `test_domain*` and friends.
This is the same mechanism the repository-root conftest uses for `kernel.*`
and `kairo.*` — no mocks, no skips, no environment-specific hacks.
"""
import os
import sys

_SIDECAR_ROOT = os.path.dirname(os.path.abspath(__file__))
if _SIDECAR_ROOT not in sys.path:
    sys.path.insert(0, _SIDECAR_ROOT)
