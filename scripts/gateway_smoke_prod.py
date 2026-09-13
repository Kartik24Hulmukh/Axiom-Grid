"""Bounded, explicitly opt-in live gateway benchmark. No payloads/secrets logged."""
import argparse
import concurrent.futures
import json
import os
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    args = parser.parse_args()
    assert args.live
    key = os.environ["MELIOUS_API_KEY"]
    base = os.getenv("MELIOUS_BASE_URL", "https://api.melious.ai/v1").rstrip("/")
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    with urllib.request.urlopen(urllib.request.Request(base + "/models", headers=headers), timeout=20) as r:
        catalog = json.load(r)["data"]
    targets = ("glm-5.3", "glm-5.3-flash", "kimi-k3", "qwen3.8-27b")
    ids = {m["id"] for m in catalog}
    def smoke(model):
        result = {"model": model, "catalog_present": model in ids}
        if model not in ids:
            return result
        body = json.dumps({"model": model, "messages": [{"role": "user", "content": "Reply OK."}], "max_tokens": 32}).encode()
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(urllib.request.Request(base + "/chat/completions", body, headers), timeout=20) as r:
                data = json.load(r)
                result.update(status=r.status, usage=data.get("usage"), choices=len(data.get("choices", [])))
        except urllib.error.HTTPError as exc:
            result["status"] = exc.code
            exc.close()
        except (OSError, ValueError) as exc:
            result["error_type"] = type(exc).__name__
        result["latency_ms"] = round((time.perf_counter()-start)*1000, 2)
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(smoke, targets))
    print(json.dumps({"scope": "one live sample/model; no percentile or capacity claim", "max_requests": 4, "max_completion_tokens_total": 128, "results": results}, indent=2))
    return 0 if all(r.get("status") == 200 for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
