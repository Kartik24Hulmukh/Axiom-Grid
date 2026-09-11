#!/usr/bin/env python3
"""Opt-in real-model validation. Requires running runtime and installed Ollama model.

No model downloads, fake model responses, or external inference. Uses stdlib only.
Run: python3 scripts/axiom-live-e2e.py --output evidence.json
The output contains synthetic prompts/results and model metadata, never the token.
"""

import argparse
import concurrent.futures
import json
import math
import os
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path

PROMPTS = [
    "Fix the grammar, return one sentence: She go to school every day.",
    "Make this polite in one sentence: Send the report now.",
    "Summarize in one sentence: The meeting moved from Monday to Tuesday because the office is closed Monday.",
    "Write a short subject line for an email requesting a project update.",
    "Translate to French: Thank you for your help.",
    "Translate to English: Buenos días, ¿cómo estás?",
    "Preserve the name Zoë and rewrite politely: Zoë, fix this now.",
    "Write one sentence thanking a colleague for reviewing a document.",
    "Simplify: We endeavor to facilitate the implementation of the proposal.",
    "Rewrite actively: The report was reviewed by the manager.",
    "Correct punctuation: Lets eat grandma",
    "Write a short reminder about a meeting tomorrow at 10 AM.",
    "Shorten: At this point in time we are currently reviewing the proposal.",
    "Write a one-sentence apology for a delayed reply.",
    "Turn into a question: You can attend the meeting on Friday.",
    "Rewrite professionally: This idea is really bad and will never work.",
    "Explain in one sentence what a project deadline is.",
    "Write one sentence celebrating a team's successful product demo.",
    "Keep the emoji and improve grammar: We is happy 🌍.",
    "Return a brief title for a document about reducing office paper waste.",
]


def request(port, path, token=None, payload=None, headers=None):
    all_headers = dict(headers or {})
    if token is not None:
        all_headers["Authorization"] = "Bearer " + token
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        all_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=data, headers=all_headers
    )

    # Reject redirects rather than following an untrusted model/runtime response.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        response = opener.open(req, timeout=100)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        body = response.read(1024 * 1024)
        try:
            body = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            body = body.decode(errors="replace")
        return response.status, body


def paired_token():
    if os.environ.get("AXIOM_API_TOKEN"):
        return os.environ["AXIOM_API_TOKEN"]
    explicit = os.environ.get("AXIOM_PAIRING_FILE")
    if explicit:
        path = Path(explicit)
    elif os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        path = (
            Path(base) / "AxiomGrid/ipc.token"
            if base
            else Path.home() / ".axiom-grid/ipc.token"
        )
    else:
        base = os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("XDG_CONFIG_HOME")
        path = (
            Path(base) if base else Path.home() / ".config"
        ) / "axiom-grid/ipc.token"
    token = path.read_text().strip()
    if len(token) != 64 or any(c not in "0123456789abcdefABCDEF" for c in token):
        raise ValueError("Invalid pairing token")
    return token


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    token = paired_token()
    evidence = {
        "kind": "real installed Ollama model; synthetic prompts",
        "cases": [],
        "prompts": [],
        "human_usefulness_review": "NOT PERFORMED",
        "minimum_hardware_certification": False,
    }

    def check(name, status, expected):
        evidence["cases"].append({"name": name, "status": status, "expected": expected})
        if status != expected:
            raise AssertionError(f"{name}: expected {expected}, got {status}")

    try:
        check("liveness", request(7437, "/health")[0], 200)
        check("unauthenticated readiness", request(7437, "/readiness")[0], 401)
        check("wrong token", request(7437, "/cancel", "0" * 64, {})[0], 401)
        check(
            "cross origin",
            request(7437, "/cancel", token, {}, {"Origin": "https://evil.example"})[0],
            403,
        )
        for name, payload, status in [
            ("empty input", {"context": " "}, 400),
            ("unknown field", {"context": "hello", "extra": True}, 422),
            ("oversize context", {"context": "x" * 16001}, 400),
        ]:
            check(name, request(7437, "/materialize", token, payload)[0], status)
        status, ready = request(7437, "/readiness", token)
        check("model readiness", status, 200)
        if not ready["ready"]:
            raise AssertionError("Configured model is not installed")
        evidence["readiness"] = ready
        evidence["ollama_version"] = request(11434, "/api/version")[1]
        status, model = request(
            11434, "/api/show", payload={"model": ready["configured_model"]}
        )
        check("model metadata", status, 200)
        evidence["model"] = {
            k: model.get(k) for k in ("license", "details", "model_info", "parameters")
        }
        for index, prompt in enumerate(PROMPTS):
            start = time.monotonic()
            status, result = request(7437, "/materialize", token, {"context": prompt})
            elapsed = time.monotonic() - start
            evidence["prompts"].append(
                {
                    "index": index + 1,
                    "prompt": prompt,
                    "status": status,
                    "elapsed_seconds": round(elapsed, 3),
                    "result": result,
                }
            )
            check(f"prompt {index + 1}", status, 200)
            if not result["suggestion"].strip() or result["char_count"] != len(
                result["suggestion"]
            ):
                raise AssertionError("Invalid suggestion or Unicode count")
            print(f"prompt {index + 1}: HTTP {status}, {elapsed:.3f}s", flush=True)
        evidence["loaded_models"] = request(11434, "/api/ps")[1]
        with concurrent.futures.ThreadPoolExecutor() as pool:
            running = pool.submit(
                request,
                7437,
                "/materialize",
                token,
                {
                    "context": "Write a detailed 2000-word essay about the history of mathematics."
                },
            )
            # Poll the authenticated cancellation endpoint until the handler is armed.
            deadline = time.monotonic() + 10
            acknowledged = False
            while time.monotonic() < deadline and not running.done():
                time.sleep(0.05)
                status, cancellation = request(7437, "/cancel", token, {})
                if status == 200 and cancellation["cancelled"]:
                    acknowledged = True
                    break
            if not acknowledged:
                raise AssertionError(
                    "No in-flight generation acknowledged cancellation"
                )
            check("cancelled generation", running.result()[0], 499)
        status, cancellation = request(7437, "/cancel", token, {})
        check("idempotent cancel", status, 200)
        if cancellation["cancelled"]:
            raise AssertionError("Cancellation slot was not cleared")
        check(
            "generation after cancel",
            request(
                7437, "/materialize", token, {"context": "Say hello in one sentence."}
            )[0],
            200,
        )
        timings = [p["elapsed_seconds"] for p in evidence["prompts"]]
        evidence["latency"] = {
            "first_request_seconds": timings[0],
            "warm_p50_seconds": statistics.median(timings[1:]),
            "warm_p95_seconds": sorted(timings[1:])[
                math.ceil(0.95 * (len(timings) - 1)) - 1
            ],
        }
        evidence["passed"] = True
    except Exception as error:
        evidence["passed"] = False
        evidence["error"] = str(error)
        raise
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
        )


if __name__ == "__main__":
    main()
