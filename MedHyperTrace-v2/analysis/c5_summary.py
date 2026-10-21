"""Round 41/42: checks on the C5 run (hgfm/ssl_v02.py output).
1. per-seed pooled human macro AUROC per setting (seed 0 scratch must reproduce phase-1 v0.2 full = 0.645)
2. paired differences per seed and seed-averaged
3. label-free scores vs untrained, code-agnostic scalar baselines computed from the same node features
   (answer != round majority, answer != final, disagree flag, step position, random)
Usage: python -m analysis.c5_summary <c5_out_dir> <graphs_v02_gold0.pkl> <human400.jsonl>
"""
import sys, json, pickle, collections
import numpy as np
from hgfm.train_maa import auc, ALLC
from hgfm.ssl_v02 import macro


def main(out, graphs, human):
    d = pickle.load(open(f"{out}/preds.pkl", "rb")); P, LF = d["P"], d["LF"]
    seeds = sorted({s for _, s in P}); sets = sorted({v for v, _ in P})
    rep = {"per_seed": {}, "paired_per_seed": {}}
    ok = lambda hs: [h for h in hs if not np.isnan(h["score"])]
    for v in sets:
        rep["per_seed"][v] = [macro(ok(P[(v, s)])) for s in seeds]
    rng = np.random.default_rng(0)
    for v in sets:
        if v == "scratch": continue
        rows = []
        for s in seeds:
            a, b = P[(v, s)], P[("scratch", s)]
            assert [(h["run_id"], h["code"]) for h in a] == [(h["run_id"], h["code"]) for h in b]
            keep = [i for i in range(len(a)) if not (np.isnan(a[i]["score"]) or np.isnan(b[i]["score"]))]
            a = [a[i] for i in keep]; b = [b[i] for i in keep]
            bs = [rng.integers(0, len(a), len(a)) for _ in range(500)]
            dd = [macro([a[i] for i in x]) - macro([b[i] for i in x]) for x in bs]
            rows.append({"seed": s, "diff": macro(a) - macro(b), "ci95": [float(np.percentile(dd, 2.5)), float(np.percentile(dd, 97.5))]})
        rep["paired_per_seed"][v] = rows
    # label-free vs trivial scalar baselines on the same instances
    G = {g["run_id"]: g for g in pickle.load(open(graphs, "rb"))}
    H = [json.loads(l) for l in open(human)]
    ref = LF[next(iter(LF))]                     # instance list in fold order
    feats = {"not_majority": lambda X: (X[:, 768] > 0) * (1 - X[:, 770]), "not_final": lambda X: (X[:, 768] > 0) * (1 - X[:, 769]),
             "disagree_flag": lambda X: (X[:, 771] < 0).astype(float), "position": lambda X: X[:, 773]}
    hmap = collections.defaultdict(list)
    for h in H: hmap[(h["run_id"], h["code"])].append(h)
    base = {k: [] for k in feats}; base["random"] = []; r = np.random.default_rng(0); used = collections.Counter()
    for inst in ref:
        cands = hmap[(inst["run_id"], inst["code"])]; h = cands[used[(inst["run_id"], inst["code"])] % len(cands)]; used[(inst["run_id"], inst["code"])] += 1
        g = G[inst["run_id"]]; X = g["X"]
        rows = list(range(len(g["steps"]))) if h["code"] == "2.1.1" else [i for i, (a, ph) in enumerate(g["steps"]) if a == h["agent_id"] and ph == h["phase"]]
        for k, f in feats.items():
            base[k].append({**inst, "score": float(np.max(f(X)[rows])) if rows else float("nan")})
        base["random"].append({**inst, "score": float(r.random())})
    rep["label_free"] = {f"{st}|{nm}|{s}": macro(ok(hs)) for (st, nm, s), hs in LF.items()}
    rep["label_free_trivial"] = {k: macro(ok(v)) for k, v in base.items()}
    json.dump(rep, open(f"{out}/checks.json", "w"), indent=1, default=float)
    print(json.dumps(rep, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:4])
