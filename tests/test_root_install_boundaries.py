"""Hermetic command-boundary units only; no installer process/clean-host attestation.

Import inert helpers and replace subprocess.run before exercising the plan. No
installer entrypoint, pip, Cargo, network endpoint or privilege changes execute.
"""
import argparse
import importlib.util
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).absolute().parent.parent
spec = importlib.util.spec_from_file_location("local_install", ROOT / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


@pytest.fixture
def plan(tmp_path, monkeypatch):
    root = tmp_path / "checkout with spaces"
    root.mkdir()
    for name in ["install.py", "install.sh", "install.ps1", "Cargo.toml", "Cargo.lock",
                 "phantom-core/Cargo.toml", "tests/test_corpus_integrity.py",
                 "kairo-sidecar/requirements.txt", "requirements-test.txt"]:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("example>=1.0\n" if "requirements" in name else "reviewed fixture\n")
    wheels = tmp_path / "reviewed wheels"
    wheels.mkdir()
    (wheels / "example-1.0-py3-none-any.whl").write_bytes(b"inert fixture; never installed")
    dest = tmp_path / "new environment"
    args = argparse.Namespace(python_env=True, rust_local=False, reviewed_checkout=True,
                              reviewed_prerequisites=True, destination=str(dest), wheelhouse=str(wheels))
    monkeypatch.setattr(installer.platform, "system", lambda: "Linux")
    monkeypatch.setattr(installer.os, "geteuid", lambda: 1000)
    calls = []

    def boundary(argv, **kwargs):
        calls.append((argv, kwargs))
        assert kwargs["check"] is True
        assert "shell" not in kwargs
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(installer.subprocess, "run", boundary)
    return root, args, calls, dest


def test_python_offline_plan_and_smoke_are_preserved(plan, capsys):
    root, args, calls, dest = plan
    installer.setup(args, root)
    assert len(calls) == 5
    assert calls[0][0][-3:-1] == ["-m", "venv"]
    pip, pip_kwargs = calls[1]
    for flag in ["--no-index", "--only-binary=:all:", "--isolated", "--no-deps"]:
        assert flag in pip
    assert str(root / "kairo-sidecar/requirements.txt") in pip
    assert str(root / "requirements-test.txt") in pip
    assert pip_kwargs["env"]["PIP_CONFIG_FILE"] == installer.os.devnull
    assert pip_kwargs["env"]["KAIRO_OFFLINE"] == "1"
    assert all("http" not in arg for argv, _ in calls for arg in argv)
    assert all(kwargs["cwd"] == root for _, kwargs in calls)
    assert calls[2][0][-1] == "check"
    assert str(Path(args.wheelhouse) / "example-1.0-py3-none-any.whl") in pip
    assert all(f"import {module}" in calls[3][0][-1] for module in ["kernel", "packs", "bench"])
    assert "test_corpus_integrity.py" in calls[4][0][-1]
    assert dest.stat().st_mode & 0o777 == 0o700
    assert "No signed-artifact, clean-host" in capsys.readouterr().out


@pytest.mark.parametrize("os_name", ["Darwin", "Windows", "Plan9"])
def test_unsupported_platform_no_commands_or_writes(plan, monkeypatch, os_name):
    root, args, calls, dest = plan
    monkeypatch.setattr(installer.platform, "system", lambda: os_name)
    with pytest.raises(installer.InstallError, match="unverified"):
        installer.setup(args, root)
    assert not calls and not dest.exists()


def test_root_no_commands_or_writes(plan, monkeypatch):
    root, args, calls, dest = plan
    monkeypatch.setattr(installer.os, "geteuid", lambda: 0)
    with pytest.raises(installer.InstallError, match="Root"):
        installer.setup(args, root)
    assert not calls and not dest.exists()


@pytest.mark.parametrize("flag", ["reviewed_checkout", "reviewed_prerequisites"])
def test_explicit_trust_acknowledgements_required(plan, flag):
    root, args, calls, dest = plan
    setattr(args, flag, False)
    with pytest.raises(installer.InstallError, match="acknowledge"):
        installer.setup(args, root)
    assert not calls and not dest.exists()


@pytest.mark.parametrize("placement", ["input", "root", "destination", "parent", "wheelhouse"])
def test_symlinks_refused_before_commands(plan, placement, tmp_path):
    root, args, calls, dest = plan
    link = tmp_path / "link"
    if placement == "input":
        (root / "linked-config").symlink_to(tmp_path / "missing")
    elif placement == "root":
        link.symlink_to(root, target_is_directory=True)
        root = link
    elif placement == "destination":
        dest.symlink_to(tmp_path / "missing")
    elif placement == "parent":
        link.symlink_to(tmp_path, target_is_directory=True)
        args.destination = str(link / "new")
    else:
        link.symlink_to(args.wheelhouse, target_is_directory=True)
        args.wheelhouse = str(link)
    with pytest.raises(installer.InstallError, match="Symlink"):
        installer.setup(args, root)
    assert not calls
    assert not dest.is_dir()


@pytest.mark.parametrize("line", ["https://untrusted.invalid/pkg.whl", "-r remote.txt", "-e .",
                                  "pkg @ https://untrusted.invalid/a.whl", "--extra-index-url https://untrusted.invalid",
                                  "git+https://untrusted.invalid/repo"])
def test_remote_or_build_requirements_fail_closed(plan, line):
    root, args, calls, dest = plan
    (root / "requirements-test.txt").write_text(line)
    with pytest.raises(installer.InstallError, match="unverified requirement"):
        installer.setup(args, root)
    assert not calls and not dest.exists()


@pytest.mark.parametrize("problem", ["missing", "writable", "reused", "inside", "no_wheels"])
def test_bad_local_prerequisites(plan, problem):
    root, args, calls, dest = plan
    if problem == "missing":
        (root / "Cargo.lock").unlink()
    elif problem == "writable":
        (root / "requirements-test.txt").chmod(0o666)
    elif problem == "reused":
        dest.mkdir()
    elif problem == "inside":
        args.destination = str(root / "output")
    else:
        for wheel in Path(args.wheelhouse).glob("*.whl"):
            wheel.unlink()
    with pytest.raises(installer.InstallError):
        installer.setup(args, root)
    assert not calls


@pytest.mark.parametrize("failure_stage", [0, 1, 2, 3, 4])
def test_every_command_failure_is_fatal_no_success(plan, monkeypatch, capsys, failure_stage):
    root, args, calls, dest = plan
    def failure(argv, **kwargs):
        calls.append((argv, kwargs))
        if len(calls) - 1 == failure_stage:
            raise subprocess.CalledProcessError(17, argv)
    monkeypatch.setattr(installer.subprocess, "run", failure)
    with pytest.raises(subprocess.CalledProcessError):
        installer.setup(args, root)
    assert len(calls) == failure_stage + 1
    assert "prepared" not in capsys.readouterr().out


def test_cargo_missing_is_not_success(plan, monkeypatch):
    root, args, calls, dest = plan
    args.python_env = False
    monkeypatch.setattr(installer.shutil, "which", lambda _: None)
    with pytest.raises(installer.InstallError, match="Cargo must already"):
        installer.setup(args, root)
    assert not calls and not dest.exists()


def test_cargo_preserves_local_single_binary_install(plan, monkeypatch, capsys):
    root, args, calls, dest = plan
    args.python_env = False
    monkeypatch.setattr(installer.shutil, "which", lambda _: "/reviewed tools/cargo")
    def cargo(argv, **kwargs):
        calls.append((argv, kwargs))
        if "install" in argv:
            (dest / "bin").mkdir()
            (dest / "bin/kairo-phantom").write_bytes(b"inert; not executed")
    monkeypatch.setattr(installer.subprocess, "run", cargo)
    installer.setup(args, root)
    assert calls[0][0] == ["/reviewed tools/cargo", "--version"]
    argv = calls[1][0]
    assert "--offline" in argv and "--locked" in argv
    assert argv[argv.index("--bin") + 1] == "kairo-phantom"
    assert argv[argv.index("--root") + 1] == str(dest)
    assert "not launched or host-verified" in capsys.readouterr().out


def test_cargo_no_output_cannot_claim_success(plan, monkeypatch, capsys):
    root, args, calls, dest = plan
    args.python_env = False
    monkeypatch.setattr(installer.shutil, "which", lambda _: "/reviewed/cargo")
    with pytest.raises(installer.InstallError, match="binary is absent"):
        installer.setup(args, root)
    assert "built at" not in capsys.readouterr().out


def test_wrappers_have_no_remote_execution_or_success_claim():
    sh = (ROOT / "install.sh").read_text()
    ps = (ROOT / "install.ps1").read_text()
    assert 'exec python3 -I "$SCRIPT_DIR/install.py" --python-env "$@"' in sh
    assert "git clone" not in sh and "curl" not in sh
    assert "exit 1" in ps and "unverified" in ps
    for forbidden in ["Invoke-WebRequest", "Invoke-RestMethod", "Start-Process", "Set-Content",
                      "SetEnvironmentVariable", "Copy-Item", "cargo build", "ollama pull", "| iex"]:
        assert forbidden not in ps


@pytest.mark.parametrize("failure_stage", [0, 1])
def test_cargo_exit_failure_propagates(plan, monkeypatch, capsys, failure_stage):
    root, args, calls, dest = plan
    args.python_env = False
    monkeypatch.setattr(installer.shutil, "which", lambda _: "/reviewed/cargo")
    def failure(argv, **kwargs):
        calls.append((argv, kwargs))
        if len(calls) - 1 == failure_stage:
            raise subprocess.CalledProcessError(23, argv)
    monkeypatch.setattr(installer.subprocess, "run", failure)
    with pytest.raises(subprocess.CalledProcessError):
        installer.setup(args, root)
    assert len(calls) == failure_stage + 1
    assert "built at" not in capsys.readouterr().out
    if failure_stage == 0:
        assert not dest.exists()


def test_python_import_environment_sanitized(plan, monkeypatch):
    root, args, calls, dest = plan
    monkeypatch.setenv("PYTHONPATH", "/unreviewed/imports")
    monkeypatch.setenv("PYTHONHOME", "/unreviewed/python")
    installer.setup(args, root)
    for _, kwargs in calls[1:]:
        assert "PYTHONPATH" not in kwargs["env"]
        assert "PYTHONHOME" not in kwargs["env"]


def test_unsafe_destination_parent_rejected(plan, tmp_path):
    root, args, calls, dest = plan
    parent = tmp_path / "writable parent"
    parent.mkdir(mode=0o777)
    parent.chmod(0o777)
    args.destination = str(parent / "new")
    with pytest.raises(installer.InstallError, match="writable"):
        installer.setup(args, root)
    assert not calls and not Path(args.destination).exists()
