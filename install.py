#!/usr/bin/env python3
"""Explicit offline setup from a reviewed local checkout, not release attestation."""

import argparse
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys


class InstallError(RuntimeError):
    pass


def plain_path(path):
    """Reject symlinks in existing components, without first resolving them away."""
    path = Path(os.path.abspath(path))
    for component in (path, *path.parents):
        if component.is_symlink():
            raise InstallError(f"Symlink path refused: {component}")
    return path


def owned_private(path):
    info = path.stat()
    if info.st_uid != os.getuid() or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise InstallError(f"Must be user-owned and not group/world writable: {path}")


def validate_tree(root):
    root = plain_path(root)
    if not root.is_dir():
        raise InstallError(f"Missing local directory: {root}")
    owned_private(root)
    for directory, dirs, files in os.walk(root, followlinks=False):
        # Git metadata is not an installation input. No Git commands are invoked.
        if Path(directory) == root and ".git" in dirs:
            dirs.remove(".git")
        for name in dirs + files:
            entry = Path(directory) / name
            if entry.is_symlink():
                raise InstallError(f"Symlink input refused: {entry}")
            owned_private(entry)
            if not (entry.is_file() or entry.is_dir()):
                raise InstallError(f"Non-regular input refused: {entry}")
    return root


def require_files(root, names):
    for name in names:
        if not (root / name).is_file():
            raise InstallError(f"Missing checkout prerequisite: {name}")


def validate_requirements(path):
    # Only ordinary package/version lines: forbid URLs, VCS, -r, -e, indexes,
    # local project builds and environment markers that hide alternate sources.
    package = r"[A-Za-z0-9][A-Za-z0-9_.-]*(?:\[[A-Za-z0-9_,.-]+\])?"
    versions = r"(?:\s*(?:==|!=|~=|>=|<=|>|<)\s*[A-Za-z0-9.*+_-]+(?:\s*,\s*(?:==|!=|~=|>=|<=|>|<)\s*[A-Za-z0-9.*+_-]+)*)?"
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line and not re.fullmatch(package + versions, line):
            raise InstallError(f"Unsupported/unverified requirement in {path.name}: {line}")


def run(argv, root, env=None):
    # No shell, captured/truncated failures, endpoint probing or remote bootstrap.
    subprocess.run([str(value) for value in argv], cwd=root, env=env, check=True)


def fresh_destination(value):
    dest = plain_path(value)
    if dest.exists():
        raise InstallError("Destination must not exist; no reuse/overwrite is allowed")
    if not dest.parent.is_dir():
        raise InstallError("Destination parent must already exist")
    owned_private(dest.parent)
    return dest


def setup(args, root=None):
    # Reject unsupported OS/root before commands or writes.
    if platform.system() != "Linux":
        raise InstallError("macOS/Windows/other automated installs are unverified and blocked")
    if os.geteuid() == 0:
        raise InstallError("Root installation is refused; use an unprivileged account")
    if sys.version_info < (3, 11):
        raise InstallError("Python 3.11+ must already be installed")
    if not args.reviewed_checkout or not args.reviewed_prerequisites:
        raise InstallError("Review and explicitly acknowledge local source AND prerequisites first")
    root = validate_tree(root if root is not None else Path(__file__).absolute().parent)
    require_files(root, ["install.py", "install.sh", "install.ps1", "Cargo.toml", "Cargo.lock",
                         "phantom-core/Cargo.toml", "kairo-sidecar/requirements.txt",
                         "requirements-test.txt", "tests/test_corpus_integrity.py"])
    dest = fresh_destination(args.destination)
    # Outputs may not modify the reviewed source tree or be its ancestors.
    if dest == root or root in dest.parents or dest in root.parents:
        raise InstallError("Destination must be outside the reviewed checkout")
    if args.python_env:
        if not args.wheelhouse:
            raise InstallError("An explicitly reviewed local wheelhouse is required")
        wheels = validate_tree(args.wheelhouse)
        if dest == wheels or wheels in dest.parents or dest in wheels.parents:
            raise InstallError("Destination must not overlap the wheelhouse")
        if not any(wheels.glob("*.whl")):
            raise InstallError("No prerequisite wheels found")
        for name in ["kairo-sidecar/requirements.txt", "requirements-test.txt"]:
            validate_requirements(root / name)
        # Check installed stdlib tooling before creating the destination.
        import ensurepip
        import venv
        del ensurepip, venv
    else:
        cargo = shutil.which("cargo")
        if not cargo:
            raise InstallError("Cargo must already be installed; no rustup is downloaded")
        run([cargo, "--version"], root)
    # Failed installs retain their private destination for diagnosis, never claim success.
    dest.mkdir(mode=0o700)
    if args.python_env:
        run([sys.executable, "-I", "-m", "venv", dest], root)
        python = dest / "bin/python"
        # venv interpreter links are created by the trusted prerequisite, not sourced.
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        env.update(PIP_CONFIG_FILE=os.devnull, PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1",
                   KAIRO_OFFLINE="1", KAIRO_FORCE_CPU="1", KAIRO_SEALED="1")
        run([python, "-I", "-m", "pip", "--isolated", "install", "--no-index",
             "--find-links", wheels, "--only-binary=:all:", "--no-deps",
             "-r", root / "kairo-sidecar/requirements.txt",
             "-r", root / "requirements-test.txt",
             "pytest", "pytest-asyncio", "pytest-xdist", "pytest-timeout", "anyio",
             *sorted(wheels.glob("*.whl"))], root, env)
        # Never resolve metadata dependency URLs; the reviewed wheel set must
        # be complete and compatible, verified before executing smoke checks.
        run([python, "-I", "-m", "pip", "--isolated", "check"], root, env)
        # -I omits cwd: insert only the already-reviewed absolute source root.
        smoke = f"import sys; sys.path.insert(0, {str(root)!r}); import kernel; import packs; import bench"
        run([python, "-I", "-c", smoke], root, env)
        run([python, "-I", "-c", f"import sys; sys.path.insert(0, {str(root)!r}); import pytest; "
             "raise SystemExit(pytest.main(['tests/test_corpus_integrity.py', '-v', '--timeout=30', '-p', 'no:cacheprovider']))"], root, env)
        print(f"Local Python environment prepared at {dest}; import/corpus checks passed.")
    else:
        run([cargo, "install", "--offline", "--locked", "--path", root / "phantom-core",
             "--bin", "kairo-phantom", "--root", dest, "--target-dir", dest / "target"], root)
        if not (dest / "bin/kairo-phantom").is_file():
            raise InstallError("Cargo returned success but the expected binary is absent")
        print(f"Local Rust binary built at {dest / 'bin/kairo-phantom'}; not launched or host-verified.")
    print("No signed-artifact, clean-host, desktop or production-readiness attestation.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--python-env", action="store_true")
    mode.add_argument("--rust-local", action="store_true")
    parser.add_argument("--reviewed-checkout", action="store_true")
    parser.add_argument("--reviewed-prerequisites", action="store_true")
    parser.add_argument("--destination", required=True)
    parser.add_argument("--wheelhouse")
    args = parser.parse_args(argv)
    try:
        setup(args)
    except (InstallError, OSError, subprocess.CalledProcessError, ImportError) as exc:
        print(f"Installation blocked/failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
