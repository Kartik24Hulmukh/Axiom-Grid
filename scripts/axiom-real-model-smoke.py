#!/usr/bin/env python3
"""Explicit opt-in real-model smoke. No installation, download, or quality claims.
Starts only the supplied runtime and writes non-sensitive fixture results.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

spec = importlib.util.spec_from_file_location("launcher", Path(__file__).with_name("axiom-launch.py"))
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    env = launcher.credential_env(args.model)
    # Refuse an existing server before launching our own.
    import socket
    with socket.socket() as probe:
        if os.name != "nt":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", 7437))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), launcher.NoRedirect())
    child = subprocess.Popen([str(args.runtime.resolve())], env=env)
    evidence = {"model":args.model,"scope":"real installed model; synthetic fixtures; not a benchmark or quality certification", "samples":[]}
    try:
        for _ in range(100):
            if child.poll() is not None: raise RuntimeError("Runtime failed to start")
            try:
                ready = launcher.fetch_readiness(opener, env["AXIOM_API_TOKEN"])
                break
            except OSError: time.sleep(0.1)
        else: raise RuntimeError("Runtime unavailable")
        if not ready["ready"]: raise RuntimeError("Exact configured model is not installed")
        evidence["readiness"] = ready
        prompts = [
            "Rewrite clearly in one sentence, preserving the Friday deadline: We are in the process of doing the work and will have it done by Friday.",
            "Return exactly this text without any commentary: Hello 🌍 — café.",
            "Rewrite politely without inventing details: Send the invoice today.",
        ]
        for prompt in prompts:
            started = time.monotonic()
            request = urllib.request.Request(launcher.BASE + "/materialize", data=json.dumps({"context":prompt}).encode(), headers={"Authorization":"Bearer " + env["AXIOM_API_TOKEN"], "Content-Type":"application/json"})
            with opener.open(request, timeout=100) as response:
                result = json.loads(response.read(512 * 1024))
            assert result["suggestion"].strip()
            assert result["char_count"] == len(result["suggestion"])
            evidence["samples"].append({"prompt":prompt,"elapsed_seconds":round(time.monotonic()-started,3),"response":result})
        evidence["transport_pass"] = True
    finally:
        launcher.stop(child)
        evidence["owned_runtime_stopped"] = child.poll() is not None
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n")
    print("Real-model smoke passed; review fixture outputs separately for quality.")

if __name__ == "__main__": main()
