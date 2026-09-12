"""Wave 5 generalization gate: field-level F1 of ClassifiedMemoPack on ADVERSARIAL surface forms.

Ground truth is invariant by construction (see packs/memo/adversarial_gen.py).
Gate: overall F1 >= 0.80; prints per-field weak spots.
"""
import json, sys, pathlib, collections
sys.path.insert(0, str(pathlib.Path(__file__).parents[2]))
from packs.memo.pack import ClassifiedMemoPack

GATE = 0.80

def _items(v):
    if isinstance(v, list):
        return set(json.dumps(x, sort_keys=True) if isinstance(x, (dict, list)) else str(x) for x in v)
    return None

def score(pred, gt):
    out = {}
    for field, gv in gt.items():
        pv = pred.get(field)
        gi = _items(gv)
        if gi is not None:
            pi = _items(pv) if pv is not None else set()
            if not gi and not pi:
                f1 = 1.0
            else:
                tp = len(gi & pi)
                prec = tp / len(pi) if pi else 0.0
                rec = tp / len(gi) if gi else 0.0
                f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        else:
            f1 = 1.0 if (pv is not None and str(pv).strip().lower() == str(gv).strip().lower()) else 0.0
        out[field] = f1
    return out

def main():
    root = pathlib.Path(__file__).parents[2]
    data = json.load(open(root / "fixtures/wedge/adversarial_ground_truth.json"))
    pack = ClassifiedMemoPack()
    per_field = collections.defaultdict(list)
    tot = n = 0
    for fx in data["fixtures"]:
        pred = pack.extract_text((root / "fixtures/wedge" / fx["file"]).read_text())
        f1s = score(pred, fx["ground_truth"])
        for k, v in f1s.items():
            per_field[k].append(v)
        mf = sum(f1s.values()) / len(f1s)
        tot += mf; n += 1
        print("%-28s %.3f" % (fx["fixture_id"], mf))
    print("--- per-field mean F1 across %d adversarial fixtures ---" % n)
    for k in sorted(per_field, key=lambda k: sum(per_field[k]) / len(per_field[k])):
        print("  %-24s %.3f" % (k, sum(per_field[k]) / len(per_field[k])))
    overall = tot / n if n else 0.0
    print("ADVERSARIAL_F1 %.3f (gate %.2f, model %s)" % (overall, GATE, data.get("generator_model")))
    return 0 if overall >= GATE else 1

if __name__ == "__main__":
    sys.exit(main())
