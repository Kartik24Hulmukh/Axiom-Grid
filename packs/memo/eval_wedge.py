"""Wedge-pack evaluation: field-level F1 of ClassifiedMemoPack vs ground truth."""
import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parents[2]))
from packs.memo.pack import ClassifiedMemoPack

def _items(v):
    if isinstance(v, list):
        return set(json.dumps(x, sort_keys=True) if isinstance(x, (dict, list)) else str(x) for x in v)
    return None

def main() -> int:
    root = pathlib.Path(__file__).parents[2]
    gt = json.load(open(root / "fixtures/wedge/ground_truth.json"))
    pack = ClassifiedMemoPack()
    tot = n = 0
    for fx in gt["fixtures"]:
        pred = pack.extract_text(open(root / "fixtures/wedge" / fx["file"]).read())
        f1s = {}
        for field, gv in fx["ground_truth"].items():
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
            f1s[field] = f1
        mf = sum(f1s.values()) / len(f1s)
        tot += mf; n += 1
        print(fx["fixture_id"], round(mf, 3))
    overall = tot / n
    print("OVERALL_F1 %.3f" % overall)
    return 0 if overall >= 0.80 else 1

if __name__ == "__main__":
    sys.exit(main())
