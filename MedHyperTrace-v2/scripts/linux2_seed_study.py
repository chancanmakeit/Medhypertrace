# round 60: seed study (MS-Swift). Per fold x seed: graph, text macro AUROC and paired graph-text diff;
# across seeds: mean, SD; seed-ensembled scores (mean of z-scored instance scores over seeds) graph vs text paired.
import json, numpy as np, itertools
from sklearn.metrics import roc_auc_score
L, T = "/data1/ekyang/cgh/CODE/mht_work/maa/llm", "models--Qwen--Qwen3-8B"
def tag(s): return f"swift_{T}" if s == 0 else f"swift_s{s}_{T}"
def load(f, s, v): return {r["inst"]: r for r in json.load(open(f"{L}/{f}/eval_{tag(s)}_{v}.json"))["rows"]}
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
    return len(ks), macro(ks, A), macro(ks, B), float(np.nanpercentile(d, 2.5)), float(np.nanpercentile(d, 97.5))
def ens(runs):
    ks = sorted(set.intersection(*[set(r) for r in runs])); out = {}
    zs = []
    for r in runs:
        a = np.array([r[k]["score"] for k in ks]); zs.append((a - a.mean()) / (a.std() + 1e-9))
    m = np.mean(zs, 0)
    for i, k in enumerate(ks): out[k] = dict(runs[0][k], score=float(m[i]))
    return out
res = {"per_seed": [], "summary": {}, "ensemble": {}, "cross_seed_spearman": {}}
from scipy.stats import spearmanr
for f in ("QD", "LQD_mac"):
    G = {s: load(f, s, "graph") for s in (0, 1, 2)}; X = {s: load(f, s, "text") for s in (0, 1, 2)}
    for s in (0, 1, 2):
        n, g, x, lo, hi = paired(G[s], X[s])
        res["per_seed"].append(dict(fold=f, seed=s, n=n, graph=g, text=x, diff=g - x, ci95=[lo, hi]))
        print(f"{f:8s} s{s} n={n} graph {g:.3f} text {x:.3f} diff {g-x:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    gs = [r["graph"] for r in res["per_seed"] if r["fold"] == f]; xs = [r["text"] for r in res["per_seed"] if r["fold"] == f]
    ds = [r["diff"] for r in res["per_seed"] if r["fold"] == f]
    res["summary"][f] = dict(graph_mean=np.mean(gs), graph_sd=np.std(gs, ddof=1), text_mean=np.mean(xs), text_sd=np.std(xs, ddof=1),
                             diff_mean=np.mean(ds), diff_sd=np.std(ds, ddof=1))
    print(f"{f:8s} graph {np.mean(gs):.3f}±{np.std(gs,ddof=1):.3f}  text {np.mean(xs):.3f}±{np.std(xs,ddof=1):.3f}  diff {np.mean(ds):+.3f}±{np.std(ds,ddof=1):.3f}")
    n, g, x, lo, hi = paired(ens([G[s] for s in (0,1,2)]), ens([X[s] for s in (0,1,2)]))
    res["ensemble"][f] = dict(n=n, graph=g, text=x, diff=g - x, ci95=[lo, hi])
    print(f"{f:8s} 3-seed ensemble graph {g:.3f} text {x:.3f} diff {g-x:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    for v, D in (("graph", G), ("text", X)):
        rh = [spearmanr([D[a][k]["score"] for k in sorted(D[a])], [D[b][k]["score"] for k in sorted(D[a])])[0] for a, b in itertools.combinations((0,1,2), 2)]
        res["cross_seed_spearman"][f"{f}/{v}"] = rh
        print(f"   {v} cross-seed Spearman {[round(x,3) for x in rh]}")
    tp = {v: {r["inst"]: r for r in json.load(open(f"{L}/{f}/eval_{T}_{v}.json"))["rows"]} for v in ("graph", "text")}
    n, g, x, lo, hi = paired(tp["graph"], tp["text"])
    res["summary"][f]["train_py_single"] = dict(graph=g, text=x, diff=g - x, ci95=[lo, hi])
json.dump(res, open("/data1/ekyang/cgh/CODE/mht_work/seed_study.json", "w"), indent=1, default=float)
