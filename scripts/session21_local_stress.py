"""Local overlay-server stress: cold boot probes, 100-worker burst,
concurrent extraction (process-isolation mode), adversarial fuzzing,
sustained load + RSS + recovery + clean shutdown."""
import concurrent.futures as cf
import json, os, random, signal, subprocess, sys, time
import urllib.request, urllib.error
import psutil

ROOT = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:8788"
EVID = os.path.join(ROOT, "docs/axiom/evidence/session21-local-stress.json")
TRAVERSAL = os.pardir + "/" + os.pardir + "/etc/passwd"

env = dict(os.environ, AXIOM_EXTRACTION_ISOLATION="process",
           AXIOM_EXTRACTION_WORKERS="4", PYTHONPATH=ROOT)
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "overlay.server:app", "--host", "127.0.0.1", "--port", "8788"],
    cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
out = {"isolation_mode": "process"}

def req(path, method="GET", body=None, headers=None, timeout=90):
    r = urllib.request.Request(BASE + path, data=body, method=method,
                               headers=headers or {})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            resp.read()
            return resp.status, time.monotonic() - t0
    except urllib.error.HTTPError as e:
        e.read()
        return e.code, time.monotonic() - t0
    except Exception as e:
        return "ERR:" + type(e).__name__, time.monotonic() - t0

try:
    t0 = time.monotonic()
    while True:
        try:
            with urllib.request.urlopen(BASE + "/livez", timeout=1) as r:
                if r.status == 200:
                    break
        except Exception:
            if time.monotonic() - t0 > 30:
                raise SystemExit("server did not boot")
            time.sleep(0.1)
    p = psutil.Process(proc.pid)
    out["cold_boot"] = {"readyz": req("/readyz"), "livez": req("/livez"),
                        "metrics": req("/metrics"), "rss_mb": round(p.memory_info().rss / 1e6, 1)}
    print("cold_boot", out["cold_boot"], flush=True)

    paths = ["/healthz", "/livez", "/readyz", "/metrics", "/api/health"]
    t0 = time.monotonic()
    with cf.ThreadPoolExecutor(100) as ex:
        results = list(ex.map(lambda i: req(paths[i % 5], timeout=30), range(600)))
    dur = time.monotonic() - t0
    lats = sorted(l for s, l in results)
    oks = sum(1 for s, _ in results if s == 200)
    out["burst"] = {"workers": 100, "requests": 600, "ok": oks, "errors": 600 - oks,
                    "rps": round(600 / dur, 1), "p50_ms": round(lats[300] * 1000, 1),
                    "p95_ms": round(lats[569] * 1000, 1), "p99_ms": round(lats[593] * 1000, 1),
                    "max_ms": round(lats[-1] * 1000, 1)}
    print("burst", out["burst"], flush=True)

    files = ["fixtures/wedge/sample_memo_01.txt", "fixtures/wedge/sample_memo_02.txt",
             "fixtures/adversarial/prompt_injection_qa.txt",
             "fixtures/adversarial/oversized_input.txt",
             "fixtures/demo/sample_nda.docx",
             "fixtures/pdf/s01_born_digital_report.pdf"]
    def extract(i):
        f = files[i % len(files)]
        body = json.dumps({"file": f}).encode()
        return req("/api/extract-document", "POST", body,
                   {"Content-Type": "application/json"}, timeout=120)
    t0 = time.monotonic()
    with cf.ThreadPoolExecutor(40) as ex:
        results = list(ex.map(extract, range(40)))
    dur = time.monotonic() - t0
    codes = {}
    for s, _ in results:
        codes[str(s)] = codes.get(str(s), 0) + 1
    lats = sorted(l for _, l in results)
    out["extraction_burst"] = {"workers": 40, "codes": codes, "duration_s": round(dur, 1),
                               "p95_s": round(lats[int(len(lats) * 0.95) - 1], 2),
                               "no_unexpected_5xx": all(str(s) in ("200", "503", "504", "422", "413") for s, _ in results)}
    print("extraction", out["extraction_burst"], flush=True)

    fz = {}
    fz["3MiB_body"] = req("/api/extract-document", "POST", b"A" * (3 * 1024 * 1024), {"Content-Type": "application/json"})[0]
    fz["malformed_json"] = req("/api/extract-document", "POST", b"{not json", {"Content-Type": "application/json"})[0]
    fz["path_traversal"] = req("/api/extract-document", "POST", json.dumps({"file": TRAVERSAL}).encode(), {"Content-Type": "application/json"})[0]
    fz["abs_passwd"] = req("/api/extract-document", "POST", json.dumps({"file": "/etc/passwd"}).encode(), {"Content-Type": "application/json"})[0]
    fz["empty_field"] = req("/api/extract-document", "POST", json.dumps({"file": ""}).encode(), {"Content-Type": "application/json"})[0]
    fz["oversized_graph_query"] = req("/api/graph/query", "POST", json.dumps({"keyword": "x" * 4096}).encode(), {"Content-Type": "application/json"})[0]
    fz["garbage_bytes"] = req("/api/extract-document", "POST", bytes(random.getrandbits(8) for _ in range(2048)), {"Content-Type": "application/octet-stream"})[0]
    fz["unknown_route"] = req("/api/definitely-not-a-route")[0]
    fz["huge_header"] = req("/healthz", headers={"X-Pad": "y" * 60000})[0]
    out["fuzz"] = fz
    out["fuzz_fail_closed"] = all(v in (400, 404, 413, 422, 200) for v in fz.values())
    print("fuzz", fz, flush=True)

    rss0 = p.memory_info().rss / 1e6
    stop = time.monotonic() + 20
    def loop(i):
        n = 0
        while time.monotonic() < stop:
            req(paths[(i + n) % 5], timeout=30)
            n += 1
        return n
    with cf.ThreadPoolExecutor(30) as ex:
        counts = list(ex.map(loop, range(30)))
    rss1 = p.memory_info().rss / 1e6
    rec, _ = req("/healthz")
    out["sustained"] = {"requests": sum(counts), "rss_start_mb": round(rss0, 1),
                        "rss_end_mb": round(rss1, 1), "rss_growth_mb": round(rss1 - rss0, 1),
                        "healthz_after": rec}
    print("sustained", out["sustained"], flush=True)
finally:
    t0 = time.monotonic()
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=20)
        out["shutdown"] = {"clean": True, "seconds": round(time.monotonic() - t0, 1)}
    except subprocess.TimeoutExpired:
        proc.kill()
        out["shutdown"] = {"clean": False}

json.dump(out, open(EVID, "w"), indent=2)
print("evidence written", flush=True)
