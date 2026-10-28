#!/usr/bin/env python3
"""Fail-closed source guard for the explicit-text preview, not runtime certification."""
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_FRONTEND = {"model_readiness", "trigger_materialize", "cancel_materialize"}
ALLOWED_NATIVE = ALLOWED_FRONTEND | {"toggle_visibility"}
# Lexical regression tripwire, not a JavaScript parser or a security boundary.


def check(root: Path) -> list[str]:
    """Inspect declared source/configuration only. Never execute project code."""
    failures: list[str] = []
    try:
        config = json.loads((root / "phantom-overlay/src-tauri/tauri.conf.json").read_text())
        windows = config["app"]["windows"]
        if len(windows) != 1:
            failures.append("exactly one declared preview window is required")
        for window in windows:
            for key, expected in {"skipTaskbar": False, "alwaysOnTop": False, "focus": True}.items():
                if window.get(key) is not expected:
                    failures.append(f"window {key} must be {expected}")
        if config.get("bundle", {}).get("active") is not False:
            failures.append("bundling must remain disabled until native release qualification")
        capability_dir = root / "phantom-overlay/src-tauri/capabilities"
        if {p.name for p in capability_dir.iterdir() if p.is_file()} != {"default.json"}:
            failures.append("additional capability files require explicit review")
        if "capabilities" in config["app"].get("security", {}):
            failures.append("inline capability overrides require explicit review")
        capability = json.loads((root / "phantom-overlay/src-tauri/capabilities/default.json").read_text())
        if capability.get("permissions") != ["core:default"]:
            failures.append("unreviewed native capabilities are forbidden")
        if capability.get("windows") != ["main"]:
            failures.append("capabilities must be limited to main preview window")
        assets = root / "phantom-overlay/dist"
        if {p.relative_to(assets).as_posix() for p in assets.rglob("*") if p.is_file()} != {"app.js", "app.css", "index.html"}:
            failures.append("additional frontend assets require explicit review")
        tauri_dir = root / "phantom-overlay/src-tauri"
        if {p.name for p in tauri_dir.glob("tauri*.conf.*")} != {"tauri.conf.json"}:
            failures.append("platform-specific Tauri configuration requires review")
        js = (assets / "app.js").read_text()
        invocations = re.findall(r'\.invoke\(\s*"([^"]+)"', js)
        if set(invocations) != ALLOWED_FRONTEND or len(invocations) != len(re.findall(r"\.invoke\s*\(", js)):
            failures.append("frontend IPC must use only literal, approved preview commands")
        # Reject common bracket/alias forms rather than silently missing them.
        # Only the reviewed direct calls and exact optional presence checks remain allowed.
        remainder = re.sub(r'window\.__TAURI__\.core\.invoke\(\s*"(?:model_readiness|trigger_materialize|cancel_materialize)"', "", js)
        remainder = remainder.replace("window.__TAURI__?.core?.invoke)", "")
        if re.search(r"\binvoke\b", remainder):
            failures.append("bracket, aliased or unreviewed IPC syntax requires explicit review")
        if re.search(r"clipboard|localStorage|sessionStorage|activeElement|innerHTML|execCommand|fetch\s*\(|WebSocket", js):
            failures.append("frontend contains an unreviewed capture, persistence, execution or network API")
        native = (root / "phantom-overlay/src-tauri/src/lib.rs").read_text()
        match = re.search(r"generate_handler!\[([\s\S]*?)\]", native)
        commands = {s.strip() for s in match[1].split(",") if s.strip()} if match else set()
        if commands != ALLOWED_NATIVE:
            failures.append("native command allowlist changed; review is required")
        html = (root / "phantom-overlay/dist/index.html").read_text()
        for marker in ["Automatic insertion is disabled", "Authorized devices and permitted tasks only", 'id="clear-session"']:
            if marker not in html:
                failures.append("preview scope/reset disclosure is missing")
        ignore = set((root / ".gitignore").read_text().splitlines())
        if not {".env", "*.pem", ".keys/", "__pycache__/"} <= ignore:
            failures.append("private-key/env/cache ignore rules are missing or malformed")
        cargo = tomllib.loads((root / ".cargo/config.toml").read_text())
        if set(cargo) != {"build"} or set(cargo["build"]) != {"jobs"}:
            failures.append("shared Cargo config contains unreviewed machine-specific overrides")
    except (OSError, UnicodeError, ValueError, KeyError, IndexError, TypeError, AttributeError):
        failures.append("required preview source/configuration is missing or malformed")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    failures = check(args.root)
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("PASS: authorized preview source/config guard (not native/runtime certification)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
