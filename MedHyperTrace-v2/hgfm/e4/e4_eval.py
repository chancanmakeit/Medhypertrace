"""E4 evaluation (pre-registration docs/design/E4_prereg_v1.md): within-trajectory metrics, raw and length-controlled,
trivial baselines, paired bootstrap. Shared by stage A (e4_probe.py) and stage B.

Input `scores`: {setting: {(dataset, traj_id): [per-seed list of candidate-step score lists]}};
`meta`: {(dataset, traj_id): {"cand": [feature-row indices], "label": row index, "ntok": [...], "code": [...], "n_steps": T}}.
Metrics per seed (acc1, hit3, rank-AUROC), then mean over seeds per trajectory (as E1). Length control = OLS of the
score on [log ntok, relative position, has_code] with trajectory fixed effects, fitted per (setting, dataset, seed)
without labels; the residual is scored. Ties broken by step order.
"""
import numpy as np

SETS = {"WW": ("who_and_when",), "TEgc": ("traceelephant_gc",), "pooled": ("who_and_when", "traceelephant_gc"), "TT_test": ("tt_test",)}


def metrics(s, mi):
    s = np.asarray(s, float); order = sorted(range(len(s)), key=lambda i: (-s[i], i)); rank = order.index(mi)
    out = {"acc1": float(rank == 0), "hit3": float(rank < 3)}
    if len(s) > 1: out["rauc"] = float(((s < s[mi]).sum() + 0.5 * ((s == s[mi]).sum() - 1)) / (len(s) - 1))
    return out


def covars(m):
    c = m["cand"]; N = max(m["n_steps"] - 1, 1)
    return np.array([[np.log(max(m["ntok"][j], 1)), (j - 1) / N, m["code"][j]] for j in c], float)


def residualise(score_lists, metas):
    Y = [np.asarray(s, float) - np.mean(s) for s in score_lists]; X = [covars(m) - covars(m).mean(0) for m in metas]
    beta, *_ = np.linalg.lstsq(np.vstack(X), np.concatenate(Y), rcond=None)
    return [y - x @ beta for y, x in zip(Y, X)]


def per_traj(scores, meta, kind):
    """-> {setting: {key: {metric: value}}} averaged over seeds; kind = raw | resid."""
    out = {}
    for st, d in scores.items():
        out[st] = {}
        for ds in {k[0] for k in d}:
            keys = [k for k in d if k[0] == ds and meta[k]["label"] in meta[k]["cand"] and len(meta[k]["cand"]) >= 2]
            if not keys: continue
            n_seeds = len(d[keys[0]])
            for sd in range(n_seeds):
                sl = [d[k][sd] for k in keys]
                if kind == "resid": sl = residualise(sl, [meta[k] for k in keys])
                for k, s in zip(keys, sl):
                    out[st].setdefault(k, []).append(metrics(s, meta[k]["cand"].index(meta[k]["label"])))
        out[st] = {k: {mm: float(np.mean([x[mm] for x in v if mm in x])) for mm in ("acc1", "hit3", "rauc")} for k, v in out[st].items()}
    return out


def baselines(meta, keys):
    sc = {"random": {}, "first_step": {}, "last_step": {}, "longest_step": {}}
    for k in keys:
        m = meta[k]; c = m["cand"]
        sc["first_step"][k] = [[-i for i in range(len(c))]]; sc["last_step"][k] = [[i for i in range(len(c))]]
        sc["longest_step"][k] = [[m["ntok"][j] for j in c]]
    return sc


def summarise(pt, keys_by_set):
    return {st: {sn: {**{mm: float(np.mean([pt[st][k][mm] for k in ks if k in pt[st]])) for mm in ("acc1", "hit3", "rauc")},
                      "n": sum(1 for k in ks if k in pt[st])} for sn, ks in keys_by_set.items()} for st in pt}


def paired(a, b, keys, mm, rng, B=1000):
    ks = [k for k in keys if k in a and k in b]; d = np.array([a[k][mm] - b[k][mm] for k in ks])
    if not len(d): return {"n": 0}
    bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(B)]
    return {"n": len(d), "diff": float(d.mean()), "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}


def evaluate(scores, meta, pairs, seed=0):
    keys = sorted({k for d in scores.values() for k in d})
    scores = {**scores, **baselines(meta, keys)}
    keys_by_set = {sn: [k for k in keys if k[0] in dss] for sn, dss in SETS.items()}
    R = {"raw": per_traj(scores, meta, "raw"), "resid": per_traj(scores, meta, "resid")}
    rnd = {k: {"acc1": 1 / len(meta[k]["cand"]), "hit3": min(3, len(meta[k]["cand"])) / len(meta[k]["cand"]), "rauc": 0.5}
           for k in keys if meta[k]["label"] in meta[k]["cand"] and len(meta[k]["cand"]) >= 2}
    R["raw"]["random"] = rnd; R["resid"]["random"] = rnd
    out = {"summary": {kind: summarise(R[kind], keys_by_set) for kind in ("raw", "resid")}, "paired": {}}
    rng = np.random.default_rng(seed)
    for x, y in pairs + [(s, b) for s in scores if s not in ("random", "first_step", "last_step", "longest_step") for b in ("random", "longest_step")]:
        for kind in ("raw", "resid"):
            if x not in R[kind] or y not in R[kind]: continue
            for sn, ks in keys_by_set.items():
                for mm in ("rauc", "acc1"):
                    out["paired"][f"{x} - {y} / {sn} / {kind} / {mm}"] = paired(R[kind][x], R[kind][y], ks, mm, rng)
    return out
