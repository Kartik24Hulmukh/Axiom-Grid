#!/usr/bin/env python3
"""Launch the engineering preview with one ephemeral, never-printed IPC token.

This is process-scoped credential provisioning, not OS-keychain pairing.
Only trusted, locally built binaries should be supplied.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:7437"


def credential_env(model):
    if not model.strip() or len(model.encode()) > 256 or any(ord(c) < 32 for c in model):
        raise ValueError("Provide an exact installed model tag (1–256 bytes).")
    return {**os.environ, "AXIOM_MODEL": model, "AXIOM_API_TOKEN": secrets.token_hex(32), "KAIRO_OFFLINE": "1"}


def fetch_readiness(opener, token):
    request = urllib.request.Request(BASE + "/readiness", headers={"Authorization": "Bearer " + token})
    with opener.open(request, timeout=6) as response:
        data = response.read(256 * 1024 + 1)
        if len(data) > 256 * 1024:
            raise ValueError("Readiness response too large")
        value = json.loads(data)
        if not isinstance(value.get("ready"), bool):
            raise ValueError("Invalid readiness response")
        return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Redirect refused", headers, fp)


def stop(child):
    if child is not None and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    suffix = ".exe" if os.name == "nt" else ""
    parser.add_argument("--model", required=True, help="Exact tag already installed in Ollama")
    parser.add_argument("--runtime", type=Path, default=root / "axiom-runtime/target/debug" / ("axiom-grid" + suffix))
    parser.add_argument("--desktop", type=Path, default=root / "phantom-overlay/src-tauri/target/debug" / ("phantom-overlay" + suffix))
    args = parser.parse_args(argv)
    env = credential_env(args.model)
    for binary in [args.runtime, args.desktop]:
        if not binary.is_file():
            parser.error(f"Build the focused runtime and desktop first; binary missing: {binary}")
    # Do not attach to, kill, or reconfigure a pre-existing service.
    with socket.socket() as probe:
        if os.name != "nt":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", 7437))
        except OSError:
            parser.error("Port 7437 is occupied. Stop the existing runtime yourself before launching.")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    runtime = desktop = None
    try:
        runtime = subprocess.Popen([str(args.runtime.resolve())], env=env)
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if runtime.poll() is not None:
                raise RuntimeError("Focused runtime exited during startup.")
            try:
                state = fetch_readiness(opener, env["AXIOM_API_TOKEN"])
                print("Model inventory: " + ("configured tag installed (inference unverified)." if state["ready"] else "configured tag missing; use Check local models."), flush=True)
                break
            except urllib.error.HTTPError as error:
                if error.code == 502:
                    print("Ollama unavailable; desktop will show setup guidance. No download started.", flush=True)
                    break
                raise RuntimeError("Runtime authentication or protocol mismatch.") from None
            except urllib.error.URLError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Runtime startup timed out.")
        if runtime.poll() is not None:
            raise RuntimeError("Focused runtime exited during startup.")
        desktop = subprocess.Popen([str(args.desktop.resolve())], env=env)
        print("Axiom preview running. Quit the desktop or press Ctrl+C to stop both owned processes.", flush=True)
        while desktop.poll() is None:
            if runtime.poll() is not None:
                raise RuntimeError("Runtime stopped; closing the desktop to avoid stale state.")
            time.sleep(0.2)
        return desktop.returncode
    finally:
        stop(desktop)
        stop(runtime)


if __name__ == "__main__":
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except (RuntimeError, ValueError, OSError) as error:
        print(f"Axiom launcher: {error}", file=sys.stderr)
        sys.exit(1)
