#!/usr/bin/env python3
"""Opt-in loopback API smoke probe with synthetic prompts (stdlib only).

Requires an operator-approved running runtime/backend. A localhost endpoint does
NOT prove local inference: audit cloud settings, model identity and network
behavior separately. Does not launch a native UI, download a model, or certify
backend locality, offline operation, usefulness or production readiness.
Run: python3 scripts/axiom-live-e2e.py --output evidence.json
Evidence redacts the exact pairing token and refuses existing output files.
"""

import argparse
import concurrent.futures
import json
import math
import os
import statistics
import stat
import time
import urllib.error
import urllib.request
from pathlib import Path

MAX_RESPONSE_BYTES = 1024 * 1024


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
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("Loopback response exceeds evidence byte budget")
        try:
            body = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            body = body.decode(errors="replace")
        return response.status, body


def _validated_token(token):
    if (not isinstance(token, str) or len(token) != 64
            or any(c not in "0123456789abcdefABCDEF" for c in token)):
        raise ValueError("Invalid pairing token")
    return token


def paired_token():
    if "AXIOM_API_TOKEN" in os.environ:
        return _validated_token(os.environ["AXIOM_API_TOKEN"])
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
    # Bound even operator-configured pairing files; do not read an arbitrary
    # large file into the evidence process. Native pairing custody is separate.
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("Pairing-file reading requires POSIX; configure AXIOM_API_TOKEN privately")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600):
            raise ValueError("Pairing file must be an owned private regular file (mode 0600)")
        data = stream.read(129)
    if len(data) > 128:
        raise ValueError("Pairing file exceeds byte budget")
    return _validated_token(data.decode("ascii").strip())


def _redact(value, token):
    """Defense against a runtime echoing a credential into any evidence field."""
    if isinstance(value, str):
        return value.replace(token, "[REDACTED_PAIRING_TOKEN]")
    if type(value) in (int, float) and token in str(value):
        return "[REDACTED_PAIRING_TOKEN]"
    if isinstance(value, list):
        return [_redact(v, token) for v in value]
    if isinstance(value, dict):
        return {_redact(k, token): _redact(v, token) for k, v in value.items()}
    return value


def write_evidence(path, evidence, token):
    """Write a new report only; exact-token redaction is not universal DLP."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(_redact(evidence, token), ensure_ascii=False,
                                allow_nan=False, indent=2) + "\n")


def reported_model_identity(ready):
    """Check reported inventory consistency, not backend or weights authenticity."""
    if (not isinstance(ready, dict) or ready.get("ready") is not True
            or not isinstance(ready.get("configured_model"), str)
            or not ready["configured_model"] or len(ready["configured_model"]) > 256
            or any(not 33 <= ord(c) <= 126 for c in ready["configured_model"])
            or ready.get("identity_check_scope") != "reported-only"
            or not isinstance(ready.get("expected_digest"), str)
            or len(ready["expected_digest"]) != 64
            or any(c not in "0123456789abcdef" for c in ready["expected_digest"])
            or not isinstance(ready.get("installed_models"), list)):
        raise ValueError("Invalid model readiness report")
    matches = [m for m in ready["installed_models"]
               if isinstance(m, dict) and m.get("name") == ready["configured_model"]]
    if len(matches) != 1:
        raise ValueError("Configured model inventory is missing or ambiguous")
    model = matches[0]
    digest = model.get("digest")
    if (not isinstance(digest, str) or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
            or digest != ready["expected_digest"]
            or type(model.get("size")) is not int or model["size"] <= 0):
        raise ValueError("Model inventory requires a reported digest and positive byte size")
    return {"name": model["name"], "digest": digest, "size": model["size"]}


def check_reported_loaded_model(loaded, identity):
    """Require matching reported loaded name/digest; still not physical locality."""
    if not isinstance(loaded, dict) or not isinstance(loaded.get("models"), list):
        raise ValueError("Invalid loaded-model report")
    for model in loaded["models"]:
        if (not isinstance(model, dict) or
                ("name" in model and "model" in model and model["name"] != model["model"])):
            raise ValueError("Conflicting or malformed loaded-model entry")
    matches = [m for m in loaded["models"]
               if m.get("name", m.get("model")) == identity["name"]]
    if len(matches) != 1 or matches[0].get("digest") != identity["digest"]:
        raise ValueError("Configured model name/digest not uniquely reported loaded")


def validate_preview_response(result):
    if (not isinstance(result, dict) or not isinstance(result.get("suggestion"), str)
            or not result["suggestion"].strip()
            or type(result.get("char_count")) is not int
            or result["char_count"] != len(result["suggestion"])
            or type(result.get("word_count")) is not int or result["word_count"] < 0):
        raise ValueError("Invalid suggestion or response counts")


def validate_cancellation(body, expected):
    if not isinstance(body, dict) or body.get("cancelled") is not expected:
        raise ValueError("Invalid cancellation acknowledgement")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Evidence output already exists; use a new path")
    token = paired_token()
    evidence = {
        "kind": "loopback API smoke probe; synthetic prompts",
        "backend_locality_verified": False,
        "offline_operation_verified": False,
        "native_ui_tested": False,
        "production_qualified": False,
        "limitations": ["HTTP behavior is not model provenance or output usefulness",
                        "Cancellation acknowledgement is not backend resource-release proof"],
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
        wrong_token = ("1" if token == "0" * 64 else "0") * 64
        check("wrong token", request(7437, "/cancel", wrong_token, {})[0], 401)
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
        identity = reported_model_identity(ready)
        evidence["readiness"] = ready
        evidence["reported_model_identity"] = identity
        status, version = request(11434, "/api/version")
        check("backend version", status, 200)
        if not isinstance(version, dict) or not isinstance(version.get("version"), str) or not version["version"]:
            raise ValueError("Invalid backend version report")
        evidence["ollama_version"] = version
        status, model = request(
            11434, "/api/show", payload={"model": ready["configured_model"]}
        )
        check("model metadata", status, 200)
        if (not isinstance(model, dict) or not isinstance(model.get("details"), dict)
                or not model["details"] or not isinstance(model.get("model_info"), dict)
                or not model["model_info"]):
            raise ValueError("Model metadata incomplete for this evidence profile")
        evidence["model"] = {
            k: model.get(k) for k in ("license", "details", "model_info", "parameters")
        }
        evidence["license_review_completed"] = False
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
            validate_preview_response(result)
            print(f"prompt {index + 1}: HTTP {status}, {elapsed:.3f}s", flush=True)
        status, loaded = request(11434, "/api/ps")
        check("loaded model report", status, 200)
        check_reported_loaded_model(loaded, identity)
        evidence["loaded_models"] = loaded
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
                if status == 200:
                    if not isinstance(cancellation, dict) or type(cancellation.get("cancelled")) is not bool:
                        raise ValueError("Invalid cancellation acknowledgement")
                    if cancellation["cancelled"] is True:
                        validate_cancellation(cancellation, True)
                        acknowledged = True
                        break
            if not acknowledged:
                raise AssertionError(
                    "No in-flight generation acknowledged cancellation"
                )
            check("cancelled generation", running.result()[0], 499)
        status, cancellation = request(7437, "/cancel", token, {})
        check("idempotent cancel", status, 200)
        validate_cancellation(cancellation, False)
        status, recovery = request(
            7437, "/materialize", token, {"context": "Say hello in one sentence."})
        check("generation after cancel", status, 200)
        validate_preview_response(recovery)
        timings = [p["elapsed_seconds"] for p in evidence["prompts"]]
        evidence["latency"] = {
            "first_request_seconds": timings[0],
            "warm_sample_count": len(timings) - 1,
            "sample_caveat": "Descriptive warm sample only, not population tail/SLA",
            "warm_sample_median_seconds": statistics.median(timings[1:]),
            "warm_sample_nearest_rank_p95_seconds": sorted(timings[1:])[
                math.ceil(0.95 * (len(timings) - 1)) - 1
            ],
        }
        evidence["passed"] = True
    except Exception as error:
        evidence["passed"] = False
        # Do not persist arbitrary exception text, which may contain credentials.
        evidence["error_type"] = type(error).__name__
        raise RuntimeError("Loopback probe failed; see redacted evidence (" +
                           type(error).__name__ + ")") from None
    finally:
        write_evidence(args.output, evidence, token)


if __name__ == "__main__":
    main()
