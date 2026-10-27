# round 62: robustness check for the TAPT pilot (runs in the sandbox on results/midtrain_pilot/tapt_pilot_v1_scores.csv.gz).
# Taxonomy: MedAgentAudit only. (1) recompute per-run macro AUROC from the CSV (must match tapt_pilot_v1_eval.json);
# (2) "robust macro": mean AUROC over codes with >= 2 positives and >= 2 negatives (on LQD_mac two scorable codes have a
# single positive, so one instance's rank moves the 7-code macro by up to ~0.14); (3) paired bootstrap (1000) of the
# seed-ensemble TAPT vs base and graph - text under both metrics.
import csv, gzip, json, sys, numpy as np
from collections import defaultdict
from sklearn.metrics import roc_auc_score
D = sys.argv[1] if len(sys.argv) > 1 else "."
R = defaultdict(dict)
for r in csv.DictReader(gzip.open(f"{D}/tapt_pilot_v1_scores.csv.gz", "rt")):
    R[(r["fold"], r["lm"], r["variant"], int(r["seed"]))][r["inst"]] = dict(code=r["code"], human=int(float(r["human"])), score=float(r["score"]))
BASE, TAPT = "models--Qwen--Qwen3-8B", "Qwen3-8B-tapt_pilot_v1"
def macro(keys, src, k=1):
    out = []
    for c in sorted({src[x]["code"] for x in keys}):
        kk = [x for x in keys if src[x]["code"] == c]; y = [src[x]["human"] for x in kk]
        if sum(y) >= k and len(y) - sum(y) >= k: out.append(roc_auc_score(y, [src[x]["score"] for x in kk]))
    return float(np.mean(out)) if out else np.nan
def eligible(src, k):  # codes eligible on the full set; bootstrap keeps this code set fixed
    cs = defaultdict(list)
    for x, v in src.items(): cs[v["code"]].append(v["human"])
    return {c for c, y in cs.items() if sum(y) >= k and len(y) - sum(y) >= k}
def paired(A, B, k, n=1000):
    ks = sorted(set(A) & set(B)); el = eligible(A, k); ks_el = [x for x in ks if A[x]["code"] in el]
    rng = np.random.default_rng(0); d = []
    for _ in range(n):
        b = [ks_el[i] for i in rng.integers(0, len(ks_el), len(ks_el))]; d.append(macro(b, A) - macro(b, B))
    a, bb = macro(ks_el, A, k), macro(ks_el, B, k)
    return dict(n=len(ks_el), codes=len(el), A=a, B=bb, diff=a - bb, ci95=[float(np.nanpercentile(d, 2.5)), float(np.nanpercentile(d, 97.5))])
def ens(runs):
    ks = sorted(set.intersection(*[set(r) for r in runs])); zs = []
    for r in runs:
        a = np.array([r[x]["score"] for x in ks]); zs.append((a - a.mean()) / (a.std() + 1e-9))
    m = np.mean(zs, 0)
    return {x: dict(runs[0][x], score=float(m[i])) for i, x in enumerate(ks)}
ref = json.load(open(f"{D}/tapt_pilot_v1_eval.json"))
mx = max(abs(macro(sorted(R[(p["fold"], p["lm"], p["variant"], p["seed"])]), R[(p["fold"], p["lm"], p["variant"], p["seed"])]) - p["auroc"]) for p in ref["per_run"])
print(f"recomputed per-run AUROC vs Linux #2: max |diff| = {mx:.2e}")
out = {"recompute_max_abs_diff": mx, "per_run_robust": [], "ensemble_robust": {}, "graph_minus_text_robust": {}}
SS = {BASE: (0, 1, 2), TAPT: (0, 1)}
for f in ("QD", "LQD_mac"):
    for v in ("graph", "text"):
        for T, ss in SS.items():
            au = [macro(sorted(R[(f, T, v, s)]), R[(f, T, v, s)], 2) for s in ss]
            out["per_run_robust"].append(dict(fold=f, lm=T, variant=v, seeds=list(ss), aurocs=au, mean=float(np.mean(au)), sd=float(np.std(au, ddof=1))))
            print(f"{f:8s} {v:5s} {T:24s} robust {' '.join(f'{a:.3f}' for a in au)} mean {np.mean(au):.3f} ± {np.std(au, ddof=1):.3f}")
        Et = ens([R[(f, TAPT, v, s)] for s in (0, 1)])
        for nm, sb in (("base3", (0, 1, 2)), ("base2", (0, 1))):
            p = paired(Et, ens([R[(f, BASE, v, s)] for s in sb]), 2); out["ensemble_robust"][f"{f}/{v}/tapt2_vs_{nm}"] = p
            print(f"   robust ens TAPT2 vs {nm}: {p['A']:.3f} vs {p['B']:.3f} diff {p['diff']:+.3f} [{p['ci95'][0]:+.3f}, {p['ci95'][1]:+.3f}] ({p['codes']} codes, n={p['n']})")
    for T, ss in SS.items():
        p = paired(ens([R[(f, T, "graph", s)] for s in ss]), ens([R[(f, T, "text", s)] for s in ss]), 2)
        out["graph_minus_text_robust"][f"{f}/{T}"] = p
        print(f"{f:8s} robust graph-text {T:24s} ens {p['A']:.3f} vs {p['B']:.3f} diff {p['diff']:+.3f} [{p['ci95'][0]:+.3f}, {p['ci95'][1]:+.3f}]")
json.dump(out, open(f"{D}/tapt_pilot_v1_robust.json", "w"), indent=1, default=float)
