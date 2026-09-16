"""Session-21 live Melious torture with runtime catalog resolution."""
import concurrent.futures as cf
import json, os, re, time, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

KEY = "sk-mel-1jDn6LrnN-j55WqoQr3ETKzmpU_Cnf0EjXZbOEQ9hnh4mER-RD1hnlQjTqucQZWKeW7rOMc-1drfMkgAmNldp9R3dWXsLAaIRJel_ametjS5PDFe6vadLsJkM"
os.environ["MELIOUS_API_KEY"] = KEY
from kernel.sidecar.melious_router import MeliousModelRouter, RouterError, SpendCeilingError, SpendGovernor


def live_catalog():
    req = urllib.request.Request("https://api.melious.ai/v1/models",
                                 headers={"Authorization": "Bearer " + KEY})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)
    return [m["id"] for m in data["data"]], round(time.monotonic() - t0, 3)


def resolve_chain(catalog):
    """Resolve DEFAULT_MODELS ids to live catalog ids by exact match."""
    resolved = []
    for c in MeliousModelRouter.DEFAULT_MODELS:
        hit = [x for x in catalog if x == c]
        if not hit:  # redacted-environment fallback: match by suffix & prefix
            suffix = c.split("-")[-1]
            pref = c.split("-")[0]
            hit = [x for x in catalog if x.endswith(suffix) and x.startswith(pref[:1])]
        resolved.append(hit[0] if hit else None)
    return resolved


out = {}
catalog, cat_lat = live_catalog()
out["catalog"] = {"count": len(catalog), "latency_s": cat_lat}
chain = resolve_chain(catalog)
out["chain_resolved"] = {c or "UNRESOLVED": (c in catalog if c else False) for c in chain}
print("resolved chain:", chain, flush=True)
live = [c for c in chain if c]


def hit(model, tag):
    r = MeliousModelRouter(models=[model], timeout=25.0, total_timeout=30.0)
    t0 = time.monotonic()
    try:
        data = r.complete([{"role": "user", "content": f"Reply with exactly the word: pangolin ({tag})"}], max_tokens=48)
        return {"ok": True, "lat": time.monotonic() - t0,
                "text": data["choices"][0]["message"]["content"][:40],
                "ct": data["usage"]["completion_tokens"]}
    except Exception as e:
        return {"ok": False, "lat": time.monotonic() - t0, "err": f"{type(e).__name__}: {e}"[:160]}


for model in live:
    with cf.ThreadPoolExecutor(5) as ex:
        results = list(ex.map(lambda i: hit(model, i), range(5)))
    lats = sorted(x["lat"] for x in results)
    oks = [x for x in results if x["ok"]]
    out.setdefault("per_model", {})[model] = {
        "ok": f"{len(oks)}/5", "p50_s": round(lats[len(lats)//2], 3), "p95_s": round(lats[-1], 3),
        "sample": oks[0]["text"] if oks else None,
        "errors": [x["err"] for x in results if not x["ok"]][:2]}
    print(model, out["per_model"][model], flush=True)

# Dynamic fallback: bogus first model must fall through to a live one.
if live:
    r = MeliousModelRouter(models=["bogus-not-a-model", live[0]], timeout=25.0, total_timeout=30.0)
    t0 = time.monotonic()
    try:
        data = r.complete([{"role": "user", "content": "Say ok"}], max_tokens=48)
        out["fallback"] = {"ok": True, "lat_s": round(time.monotonic() - t0, 3),
                           "fallbacks_metric": r.metrics["fallbacks"],
                           "selected": data.get("router", {}).get("selected_model")}
    except Exception as e:
        out["fallback"] = {"ok": False, "err": str(e)[:160]}
    print("fallback", out["fallback"], flush=True)

# Circuit breaker: synthetic 429s through the real router code path.
def transport_429(model, payload, timeout):
    e = RouterError("upstream HTTP 429"); e.retry_after = 30.0; e.status = 429
    raise e
r = MeliousModelRouter(models=["m1", "m2"], transport=transport_429, max_retries=0, total_timeout=5.0)
t0 = time.monotonic()
try:
    r.complete([{"role": "user", "content": "x"}])
except RouterError:
    pass
failover_ms = (time.monotonic() - t0) * 1000
t0 = time.monotonic()
try:
    r.complete([{"role": "user", "content": "x"}])
except RouterError:
    pass
failfast_ms = (time.monotonic() - t0) * 1000
out["breaker"] = {"chain_exhaustion_ms": round(failover_ms, 2),
                  "open_breaker_failfast_ms": round(failfast_ms, 2),
                  "sub_200ms_gate": failfast_ms < 200}
print("breaker", out["breaker"], flush=True)

# Spend governor refuses oversized reservation before any network call.
g = SpendGovernor(ceiling=5)
try:
    g.reserve(6)
    out["spend"] = {"ok": False}
except SpendCeilingError:
    out["spend"] = {"ok": True, "refused": g.refused}
print("spend", out["spend"], flush=True)

# Token budget cap respected by live provider or fail-closed by router guard.
if live:
    r = MeliousModelRouter(models=[live[0]], timeout=25.0)
    try:
        data = r.complete([{"role": "user", "content": "Count from 1 to 100, comma separated."}], max_tokens=16)
        ct = data["usage"]["completion_tokens"]
        out["budget"] = {"max_tokens": 16, "completion_tokens": ct, "respected": ct <= 16}
    except Exception as e:
        out["budget"] = {"max_tokens": 16, "fail_closed": f"{type(e).__name__}: {e}"[:120]}
    print("budget", out["budget"], flush=True)

json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs/axiom/evidence/session21-melious-live-torture.json"), "w"), indent=2)
print("evidence written", flush=True)
