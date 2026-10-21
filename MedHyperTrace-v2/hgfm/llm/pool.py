"""Pool per-fold LLM-layer evaluations over the LQD folds -> human macro AUROC + bootstrap CI (round 38).
Same protocol as results/phase1_maa: every human instance is scored once, by the LQD fold whose
held-out MAS it belongs to (QD is reported separately). Usage: python -m hgfm.llm.pool <llm_dir> <tag>
"""
import json, os, sys, glob, warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)
import numpy as np
from sklearn.metrics import roc_auc_score


def macro(rows):
    out = {}
    for c in sorted({r["code"] for r in rows}):
        y = [r["human"] for r in rows if r["code"] == c]; s = [r["score"] for r in rows if r["code"] == c]
        out[c] = roc_auc_score(y, s) if len(set(y)) == 2 else float("nan")
    return float(np.nanmean(list(out.values()))), out


def main(d, tag):
    res = {}
    for kind in ("LQD", "QD"):
        rows = []
        for f in sorted(glob.glob(os.path.join(d, f"{kind}*", f"eval_{tag}.json"))):
            if kind == "QD" and os.path.basename(os.path.dirname(f)).startswith("LQD"): continue
            rows += json.load(open(f))["rows"]
        if not rows: continue
        m, per = macro(rows); rng = np.random.default_rng(0)
        bs = [macro([rows[i] for i in rng.integers(0, len(rows), len(rows))])[0] for _ in range(1000)]
        res[kind] = {"n": len(rows), "macro_auroc": m, "ci95": [float(np.nanpercentile(bs, 2.5)), float(np.nanpercentile(bs, 97.5))], "per_code": per}
        print(f"{tag} {kind}: n={len(rows)} macro AUROC {m:.3f} [{res[kind]['ci95'][0]:.3f}, {res[kind]['ci95'][1]:.3f}]")
    json.dump(res, open(os.path.join(d, f"pooled_{tag}.json"), "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:3])
