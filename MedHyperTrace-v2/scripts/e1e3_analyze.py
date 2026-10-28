"""E1-E3 analysis, exactly as pre-registered (docs/design/E1-E3_prereg_v1.md). Runs on Linux #2 after linux2_run_e1e3.sh.

  python e1e3_analyze.py [--root /data1/ekyang/cgh/CODE/mht_work/e1e3] [--out e1e3_results.json]

Candidates = model steps (OAT's step_is_model; the question entry is never a candidate). Per trajectory and scorer:
  acc1   top-scoring candidate == labelled mistake step
  hit3   mistake step among the 3 top-scoring candidates
  rauc   within-trajectory rank-AUROC of the mistake step among the candidates
         = (#candidates scoring below it + 0.5 #ties) / (n - 1); trajectories with one candidate are skipped for rauc.
OAT (E1): metrics per seed, then averaged over the 5 seeds per trajectory. Pooled step AUROC (OAT's own metric) from OAT's
metrics.json is reported alongside. E2: one deterministic score per step. Differences: paired bootstrap (1000) over
trajectories, WW, TEgc and pooled. Decision rules are applied verbatim and printed.
Implementation detail fixed here (not a rule change): ties in top-k are broken by step order (earlier first).
"""
import argparse, glob, json, math, os
import numpy as np

B = 1000


def metrics_for(scores, cand, mistake):
    """scores: dict step -> score over candidate steps `cand` (list, in order)."""
    if mistake not in cand or not cand:
        return None
    s = np.array([scores[c] for c in cand], dtype=float)
    if np.isnan(s).any():
        s = np.nan_to_num(s, nan=-1e9)
    order = sorted(range(len(cand)), key=lambda i: (-s[i], i))
    mi = cand.index(mistake); rank = order.index(mi)
    out = {"acc1": float(rank == 0), "hit3": float(rank < 3)}
    if len(cand) > 1:
        out["rauc"] = float(((s < s[mi]).sum() + 0.5 * ((s == s[mi]).sum() - 1)) / (len(cand) - 1))
    return out


def baselines(traj, prior):
    """traj: {cand, mistake, n_steps}. Returns {name: metric dict}. Random = expected values."""
    c, m = traj["cand"], traj["mistake"]; n = len(c); res = {}
    if m not in c:   # mistake on a non-model step: not evaluable for any scorer (OAT drops these too)
        return {k: None for k in ("random", "first_step", "last_step", "position_prior")}
    res["random"] = {"acc1": 1 / n, "hit3": min(3, n) / n, **({"rauc": 0.5} if n > 1 else {})}
    res["first_step"] = metrics_for({x: -i for i, x in enumerate(c)}, c, m)
    res["last_step"] = metrics_for({x: i for i, x in enumerate(c)}, c, m)
    N = max(traj["n_steps"] - 1, 1)
    res["position_prior"] = metrics_for({x: prior[min(int(10 * x / N), 9)] for x in c}, c, m)
    return res


def mean_by(rows, key):
    v = [r[key] for r in rows if r is not None and key in r]
    return float(np.mean(v)) if v else float("nan")


def paired(a, b, key, rng):
    """a, b: dict traj_id -> metric dict. Mean difference a - b and 95% bootstrap CI over common trajectories."""
    ids = [i for i in a if i in b and a[i] is not None and b[i] is not None and key in a[i] and key in b[i]]
    d = np.array([a[i][key] - b[i][key] for i in ids])
    if not len(d):
        return {"n": 0}
    bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(B)]
    return {"n": len(d), "diff": float(d.mean()), "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}


def load_trajs(root):
    """Candidates / labels from the E2 score files (same OAT loader, all trajectories, independent of extraction)."""
    f = os.path.join(root, "e2_scores_base.json")
    T = {}
    for r in json.load(open(f))["rows"]:
        cand = [si for si, im in zip(r["step_indices"], r["step_is_model"]) if si >= 0 and im]
        T[(r["dataset"], r["id"])] = {"cand": cand, "mistake": r["mistake_step"], "n_steps": len(r["step_indices"]) - 1,
                                      "nll": dict(zip(r["step_indices"], r["step_nll"])), "yarn": bool(r.get("yarn"))}
    return T


def oat_seed_metrics(root, proxy, ds, T):
    d = os.path.join(root, f"oat_{proxy}", "outputs", "results", "ood", f"mcp_atlas_to_{ds}", "OAT_coral")
    per = {}
    files = sorted(glob.glob(os.path.join(d, "predictions_seed*.json")))
    for f in files:
        for p in json.load(open(f)):
            key = (ds, p["trajectory_id"])
            if key not in T: continue
            sc = dict(zip(p["score_step_indices"], p["scores"]))
            cand = [c for c in T[key]["cand"] if c in sc]
            m = metrics_for(sc, cand, T[key]["mistake"])
            if m: per.setdefault(key, []).append(m)
    out = {k: {kk: float(np.mean([x[kk] for x in v if kk in x])) for kk in ("acc1", "hit3", "rauc") if any(kk in x for x in v)} for k, v in per.items()}
    pooled = json.load(open(os.path.join(d, "metrics.json"))) if os.path.exists(os.path.join(d, "metrics.json")) else {}
    return out, len(files), pooled


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default="/data1/ekyang/cgh/CODE/mht_work/e1e3"); ap.add_argument("--out", default=None)
    a = ap.parse_args(); rng = np.random.default_rng(0); R = {"scorers": {}, "compare": {}, "decisions": {}}
    T = load_trajs(a.root)
    sets = {"WW": [k for k in T if k[0] == "who_and_when"], "TEgc": [k for k in T if k[0] == "traceelephant_gc"]}
    sets["pooled"] = sets["WW"] + sets["TEgc"]
    # pre-registered sensitivity: without the trajectories > 32,768 tokens (YaRN pass); not used by the decision rules
    sets["pooled_le32k"] = [k for k in sets["pooled"] if not T[k]["yarn"]]
    # position prior: relative-position histogram of the OTHER dataset's mistake steps (10 bins, add-one)
    def hist(keys):
        h = np.ones(10)
        for k in keys:
            t = T[k]; h[min(int(10 * t["mistake"] / max(t["n_steps"] - 1, 1)), 9)] += 1
        return h / h.sum()
    prior = {"who_and_when": hist(sets["TEgc"]), "traceelephant_gc": hist(sets["WW"])}
    S = {}   # scorer -> {traj: metrics}
    for name in ("random", "first_step", "last_step", "position_prior"):
        S[name] = {k: baselines(T[k], prior[k[0]])[name] for k in sets["pooled"]}
    pooled_oat = {}
    for proxy in ("base", "tapt"):
        S[f"oat_{proxy}"] = {}
        for ds in ("who_and_when", "traceelephant_gc"):
            m, nseeds, pooled = oat_seed_metrics(a.root, proxy, ds, T); S[f"oat_{proxy}"].update(m)
            pooled_oat[f"{proxy}/{ds}"] = {"n_seeds": nseeds, **{k: pooled.get(k) for k in ("auroc_mean", "auroc_std", "auprc_mean", "topk_detection_hit_rate_mean", "topk_detection_f1_mean", "n")}}
    E2 = {}
    for n in ("base", "tapt", "S", "R"):
        f = os.path.join(a.root, f"e2_scores_{n}.json")
        if os.path.exists(f):
            E2[n] = {(r["dataset"], r["id"]): dict(zip(r["step_indices"], r["step_nll"])) for r in json.load(open(f))["rows"]}
    def e2_scorer(fn):
        out = {}
        for k in sets["pooled"]:
            try: sc = {c: fn(c, k) for c in T[k]["cand"]}
            except KeyError: continue
            out[k] = metrics_for(sc, T[k]["cand"], T[k]["mistake"])
        return out
    if "base" in E2: S["nll_base"] = e2_scorer(lambda c, k: E2["base"][k][c])
    if "tapt" in E2 and "base" in E2: S["nll_tapt_minus_base"] = e2_scorer(lambda c, k: E2["tapt"][k][c] - E2["base"][k][c])
    if "S" in E2 and "R" in E2: S["lr_S_minus_R"] = e2_scorer(lambda c, k: E2["S"][k][c] - E2["R"][k][c])
    for name, d in S.items():
        R["scorers"][name] = {sn: {m: mean_by([d.get(k) for k in keys], m) for m in ("acc1", "hit3", "rauc")} | {"n": sum(1 for k in keys if d.get(k))}
                              for sn, keys in sets.items()}
    R["oat_pooled_metrics"] = pooled_oat
    def cmp(x, y):
        return {sn: {m: paired({k: S[x].get(k) for k in keys}, {k: S[y].get(k) for k in keys}, m, rng) for m in ("acc1", "hit3", "rauc")} for sn, keys in sets.items()}
    triv = ("first_step", "last_step", "position_prior")
    pairs = [("oat_tapt", "oat_base")] + [("oat_base", t) for t in triv] + [("oat_tapt", t) for t in triv]
    if "lr_S_minus_R" in S:
        pairs += [("lr_S_minus_R", t) for t in triv] + [("lr_S_minus_R", "nll_base"), ("lr_S_minus_R", "oat_base")]
    for x, y in pairs:
        if x in S and y in S: R["compare"][f"{x} - {y}"] = cmp(x, y)
    # ---- decisions, verbatim from the pre-registration
    e1 = R["compare"].get("oat_tapt - oat_base", {})
    if e1:
        p_ok = e1["pooled"]["rauc"].get("ci95", [-1])[0] > 0 and e1["pooled"]["acc1"].get("diff", -1) >= 0
        part = [sn for sn in ("WW", "TEgc") if e1[sn]["rauc"].get("ci95", [-1])[0] > 0 and e1[sn]["acc1"].get("diff", -1) >= 0]
        R["decisions"]["E1"] = "HOLDS" if p_ok else ("PARTIAL (" + ", ".join(part) + ")" if part else "DOES NOT HOLD")
    if "lr_S_minus_R" in S:
        best = max(triv, key=lambda t: R["scorers"][t]["pooled"]["rauc"])
        c1 = R["compare"][f"lr_S_minus_R - {best}"]["pooled"]["rauc"]; c2 = R["compare"]["lr_S_minus_R - nll_base"]["pooled"]["rauc"]
        R["decisions"]["E2"] = {"best_trivial": best, "vs_best_trivial": c1, "vs_nll_base": c2,
                                "verdict": "HOLDS" if c1["ci95"][0] > 0 and c2["ci95"][0] > 0 else "DOES NOT HOLD"}
    print(f"{'scorer':22s} " + "  ".join(f"{sn:>22s}" for sn in sets))
    for name, v in R["scorers"].items():
        print(f"{name:22s} " + "  ".join(f"a1 {v[sn]['acc1']:.3f} h3 {v[sn]['hit3']:.3f} r {v[sn]['rauc']:.3f}" for sn in sets))
    for k, v in R["compare"].items():
        p = v["pooled"]
        print(f"{k:34s} pooled: " + "  ".join(f"{m} {p[m].get('diff', float('nan')):+.3f} [{p[m].get('ci95', [math.nan, math.nan])[0]:+.3f},{p[m].get('ci95', [math.nan, math.nan])[1]:+.3f}]" for m in ("acc1", "hit3", "rauc")))
    print("OAT pooled (OAT's own metric):", json.dumps(pooled_oat))
    print("DECISIONS:", json.dumps(R["decisions"]))
    json.dump(R, open(a.out or os.path.join(a.root, "e1e3_results.json"), "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
