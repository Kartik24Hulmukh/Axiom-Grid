"""AI-002: adversarial surface-form generator for ClassifiedMemoPack (Wave 5).

Uses a frontier model (Melious gateway, OpenAI-compatible) OFFLINE, at build time only,
to rewrite the wedge fixtures into adversarial surface forms whose SEMANTIC ground truth
is unchanged by construction. This converts the wedge pack generalization risk from
"assumed" to "measured" without any runtime egress (KAIRO_AIR_GAP stays true at serve time).

Usage: MELIOUS_API_KEY=... python3 packs/memo/adversarial_gen.py [--variants 3]
"""
from __future__ import annotations
import argparse, json, os, pathlib, re, sys, concurrent.futures as cf
import urllib.request

ROOT = pathlib.Path(__file__).parents[2]
OUT = ROOT / "fixtures/wedge/adversarial"
BASE = os.environ.get("MELIOUS_BASE_URL", "https://api.melious.ai/v1")
PREFS = ["glm-5.3", "glm-5.2", "kimi-k3", "kimi-k2.7", "qwen3-235b", "llama-3.3-70b"]

SYS = ("You rewrite classified-style intelligence memos into ADVERSARIAL SURFACE FORMS. "
       "Rules, absolute: (1) every semantic value - classification marking, control markings, portion marks, "
       "originating org, author, dates, subject, entities, references, handling instructions, PII - must survive "
       "UNCHANGED in meaning and spelling. (2) Only the FORM may change: swap label synonyms (FROM: -> ORIGINATOR:/ORIGINATING OFFICE:), "
       "reorder header blocks, change date formats (15 March 2003 -> 20030315 -> 15 MAR 03), wrap lines differently, "
       "add plausible extra sections (DISTRIBUTION, POC), insert light OCR-style noise in NON-value text only, "
       "change bullet/numbering style. (3) Never invent, drop or rename an entity, reference or marking. "
       "(4) Output the memo text ONLY - no commentary, no code fences.")


def _post(path, payload, key, timeout=180):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def pick_model(key):
    env = os.environ.get("MELIOUS_MODEL")
    if env:
        return env
    req = urllib.request.Request(BASE + "/models", headers={"Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=60) as r:
        ids = [m["id"] for m in json.loads(r.read().decode())["data"]]
    for p in PREFS:
        for i in ids:
            if i.lower().startswith(p):
                return i
    return ids[0]


def variant(key, model, text, style, temp):
    msg = [{"role": "system", "content": SYS},
           {"role": "user", "content": "Adversarial style directive: " + style + "\n\nMEMO:\n" + text}]
    d = _post("/chat/completions", {"model": model, "messages": msg, "temperature": temp, "max_tokens": 2400}, key)
    out = d["choices"][0]["message"]["content"].strip()
    out = re.sub(r"^```[a-zA-Z]*\n|```$", "", out).strip()
    return out


STYLES = [
    "Label-synonym attack: rename every header label to a plausible synonym and reorder the header block.",
    "Format attack: change all date formats, renumber paragraphs with letters, rewrap every line at 60 chars.",
    "Noise attack: add DISTRIBUTION and POC sections plus light OCR noise in prose (never inside a value).",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", type=int, default=3)
    a = ap.parse_args()
    key = os.environ.get("MELIOUS_API_KEY", "")
    if not key:
        print("MELIOUS_API_KEY not set - generation skipped (fixtures are committed).")
        return 0
    gt = json.load(open(ROOT / "fixtures/wedge/ground_truth.json"))
    model = pick_model(key)
    print("model:", model)
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = []
    for fx in gt["fixtures"]:
        src = (ROOT / "fixtures/wedge" / fx["file"]).read_text()
        for i in range(a.variants):
            jobs.append((fx, src, i))
    rows = []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(variant, key, model, s, STYLES[i % len(STYLES)], 0.5 + 0.2 * i): (fx, i) for fx, s, i in jobs}
        for f in cf.as_completed(futs):
            fx, i = futs[f]
            try:
                txt = f.result()
            except Exception as e:
                print("FAIL", fx["fixture_id"], i, type(e).__name__)
                continue
            name = "%s_adv%d.txt" % (fx["fixture_id"], i + 1)
            (OUT / name).write_text(txt)
            rows.append({"fixture_id": name[:-4], "file": "adversarial/" + name,
                         "derived_from": fx["fixture_id"], "style": STYLES[i % len(STYLES)],
                         "ground_truth": fx["ground_truth"]})
    rows.sort(key=lambda r: r["fixture_id"])
    json.dump({"generator_model": model, "invariant": "semantics preserved, surface form perturbed",
               "fixtures": rows}, open(ROOT / "fixtures/wedge/adversarial_ground_truth.json", "w"), indent=1)
    print("wrote", len(rows), "adversarial fixtures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
