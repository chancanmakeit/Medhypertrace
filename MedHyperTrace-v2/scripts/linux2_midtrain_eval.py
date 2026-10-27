# round 62: TAPT pilot v1 evaluation. Taxonomy: MedAgentAudit only (human instances, macro AUROC over the 10 MAA codes).
# Compares SFT on the TAPT-merged LM (seeds 0, 1) with SFT on base Qwen3-8B (MS-Swift seeds 0, 1, 2; round 60 seed study):
#   per seed AUROC, mean +- SD; same-seed paired TAPT - base (bootstrap 1000); seed-ensemble (mean z-score) paired:
#   TAPT 2-seed vs base 3-seed and vs base 2-seed (s0, s1); graph - text under each LM.
# Writes midtrain/tapt_pilot_v1_eval.json and midtrain/tapt_pilot_v1_scores.csv (per instance, every run).
import json, csv, numpy as np
from sklearn.metrics import roc_auc_score
W = "/data1/ekyang/cgh/CODE/mht_work"; L = f"{W}/maa/llm"
BASE, TAPT = "models--Qwen--Qwen3-8B", "Qwen3-8B-tapt_pilot_v1"
def tag(s, T): return f"swift_{T}" if s == 0 else f"swift_s{s}_{T}"
def load(f, s, v, T): return {r["inst"]: r for r in json.load(open(f"{L}/{f}/eval_{tag(s, T)}_{v}.json"))["rows"]}
def macro(keys, src):
    out = []
    for c in sorted({src[k]["code"] for k in keys}):
        kk = [k for k in keys if src[k]["code"] == c]; y = [src[k]["human"] for k in kk]
        if len(set(y)) == 2: out.append(roc_auc_score(y, [src[k]["score"] for k in kk]))
    return float(np.mean(out))
def paired(A, B, n=1000):
    ks = sorted(set(A) & set(B)); rng = np.random.default_rng(0); d = []
    for _ in range(n):
        b = [ks[i] for i in rng.integers(0, len(ks), len(ks))]; d.append(macro(b, A) - macro(b, B))
    a, b = macro(ks, A), macro(ks, B)
    return dict(n=len(ks), A=a, B=b, diff=a - b, ci95=[float(np.nanpercentile(d, 2.5)), float(np.nanpercentile(d, 97.5))])
def ens(runs):
    ks = sorted(set.intersection(*[set(r) for r in runs])); zs = []
    for r in runs:
        a = np.array([r[k]["score"] for k in ks]); zs.append((a - a.mean()) / (a.std() + 1e-9))
    m = np.mean(zs, 0)
    return {k: dict(runs[0][k], score=float(m[i])) for i, k in enumerate(ks)}
def fmt(p): return f"{p['A']:.3f} vs {p['B']:.3f} diff {p['diff']:+.3f} [{p['ci95'][0]:+.3f}, {p['ci95'][1]:+.3f}]"
res = {"per_run": [], "summary": {}, "same_seed": {}, "ensemble": {}, "graph_minus_text": {}}
rows = []
for f in ("QD", "LQD_mac"):
    R = {(T, v, s): load(f, s, v, T) for v in ("graph", "text") for T, ss in ((BASE, (0, 1, 2)), (TAPT, (0, 1))) for s in ss}
    for (T, v, s), D in R.items():
        ks = sorted(D); a = macro(ks, D)
        res["per_run"].append(dict(fold=f, lm=T, variant=v, seed=s, n=len(ks), auroc=a))
        for k in ks: rows.append([f, T, v, s, k, D[k]["code"], D[k]["human"], D[k]["score"]])
    for v in ("graph", "text"):
        for T, ss in ((BASE, (0, 1, 2)), (TAPT, (0, 1))):
            au = [r["auroc"] for r in res["per_run"] if r["fold"] == f and r["lm"] == T and r["variant"] == v]
            res["summary"][f"{f}/{v}/{T}"] = dict(seeds=list(ss), aurocs=au, mean=float(np.mean(au)), sd=float(np.std(au, ddof=1)))
            print(f"{f:8s} {v:5s} {T:28s} {' '.join(f'{x:.3f}' for x in au)}  mean {np.mean(au):.3f} ± {np.std(au, ddof=1):.3f}")
        for s in (0, 1):
            p = paired(R[(TAPT, v, s)], R[(BASE, v, s)]); res["same_seed"][f"{f}/{v}/s{s}"] = p
            print(f"   same-seed s{s} TAPT vs base: {fmt(p)}")
        Et, Eb3, Eb2 = ens([R[(TAPT, v, s)] for s in (0, 1)]), ens([R[(BASE, v, s)] for s in (0, 1, 2)]), ens([R[(BASE, v, s)] for s in (0, 1)])
        res["ensemble"][f"{f}/{v}/tapt2_vs_base3"] = p3 = paired(Et, Eb3)
        res["ensemble"][f"{f}/{v}/tapt2_vs_base2"] = p2 = paired(Et, Eb2)
        print(f"   ensemble TAPT2 vs base3: {fmt(p3)}\n   ensemble TAPT2 vs base2: {fmt(p2)}")
    for T, ss in ((BASE, (0, 1, 2)), (TAPT, (0, 1))):
        per = [paired(R[(T, "graph", s)], R[(T, "text", s)]) for s in ss]
        e = paired(ens([R[(T, "graph", s)] for s in ss]), ens([R[(T, "text", s)] for s in ss]))
        e2 = paired(ens([R[(T, "graph", s)] for s in (0, 1)]), ens([R[(T, "text", s)] for s in (0, 1)]))
        ds = [p["diff"] for p in per]
        res["graph_minus_text"][f"{f}/{T}"] = dict(per_seed=per, mean=float(np.mean(ds)), sd=float(np.std(ds, ddof=1)), ensemble=e, ensemble_s01=e2)
        print(f"{f:8s} graph-text {T:28s} per seed {' '.join(f'{d:+.3f}' for d in ds)} mean {np.mean(ds):+.3f}±{np.std(ds, ddof=1):.3f}; ens(all) {fmt(e)}; ens(s0,1) {e2['diff']:+.3f}")
json.dump(res, open(f"{W}/midtrain/tapt_pilot_v1_eval.json", "w"), indent=1, default=float)
with open(f"{W}/midtrain/tapt_pilot_v1_scores.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["fold", "lm", "variant", "seed", "inst", "code", "human", "score"]); w.writerows(rows)
print("rows", len(rows))
