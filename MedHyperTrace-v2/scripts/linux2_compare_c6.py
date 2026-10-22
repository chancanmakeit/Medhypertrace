# C6 paired comparisons on Linux #2 (round 54; generalises mht_work/compare_gt.py from rounds 51-53).
# Per fold and pooled over the LQD folds (same protocol as hgfm.llm.pool: pool instances, then macro AUROC over codes);
# QD is reported on its own: LQD and QD are two different splits of the same 400 human instances, never pooled together.
# Usage: python linux2_compare_c6.py [llm_dir] [tag]
import json, os, sys, numpy as np
from sklearn.metrics import roc_auc_score
L = sys.argv[1] if len(sys.argv) > 1 else "/data1/ekyang/cgh/CODE/mht_work/maa/llm"
T = sys.argv[2] if len(sys.argv) > 2 else "models--Qwen--Qwen3-8B"
PAIRS = [("graph", "text"), ("graph", "zeroshot"), ("text", "zeroshot")]


def rows(f, v):
    p = f"{L}/{f}/eval_{T}_{v}.json"
    return {r["inst"]: r for r in json.load(open(p))["rows"]} if os.path.exists(p) else None


def macro(keys, src):
    out = []
    for c in sorted({src[k]["code"] for k in keys}):
        kk = [k for k in keys if src[k]["code"] == c]; y = [src[k]["human"] for k in kk]
        if len(set(y)) == 2: out.append(roc_auc_score(y, [src[k]["score"] for k in kk]))
    return float(np.mean(out)) if out else float("nan")


def paired(A, B, n_boot=1000):
    ks = sorted(set(A) & set(B)); rng = np.random.default_rng(0); d = []
    for _ in range(n_boot):
        b = [ks[i] for i in rng.integers(0, len(ks), len(ks))]; d.append(macro(b, A) - macro(b, B))
    return len(ks), macro(ks, A), macro(ks, B), float(np.nanpercentile(d, 2.5)), float(np.nanpercentile(d, 97.5))


def report(name, R, out):
    for a, b in PAIRS:
        if R.get(a) is None or R.get(b) is None or not R[a] or not R[b]: continue
        n, x, y, lo, hi = paired(R[a], R[b])
        out.append({"fold": name, "a": a, "b": b, "n": n, "auc_a": x, "auc_b": y, "diff": x - y, "ci95": [lo, hi]})
        print(f"{name:22s} {a:8s} vs {b:8s} n={n:3d} {x:.3f} vs {y:.3f} diff {x-y:+.3f} [{lo:+.3f}, {hi:+.3f}]", flush=True)


if __name__ == "__main__":
    out = []; pooled = {v: {} for v in ("graph", "text", "zeroshot")}
    folds = sorted(f for f in os.listdir(L) if f.startswith("LQD_"))
    for f in folds:
        R = {v: rows(f, v) for v in pooled}
        for v in pooled:
            if R[v]: pooled[v].update(R[v])
        report(f, R, out)
    report("POOLED_LQD", pooled, out)
    report("QD", {v: rows("QD", v) for v in pooled}, out)
    json.dump(out, open(f"{L}/compare_c6.json", "w"), indent=1)
