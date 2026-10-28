"""E1-E3 exploratory checks (round 67, written AFTER seeing the pre-registered results; not part of any decision rule).

  python e1e3_exploratory.py [--root /data1/ekyang/cgh/CODE/mht_work/e1e3]

1. E1 seed robustness: pooled within-trajectory rank-AUROC of OAT for each of the 5 seeds, per proxy.
2. Sign-reversed E2 controls (post hoc): base - tapt and R - S; rank-AUROC per dataset, mean within-trajectory Spearman of
   the score with step position, and the same rank-AUROC with the first model step removed from the candidates
   (trajectories whose mistake is the first model step dropped), next to "earliest remaining step" and NLL_base.
"""
import argparse, json, os, sys
import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, os.path.dirname(__file__))
import e1e3_analyze as EA   # noqa: E402

DS = ("who_and_when", "traceelephant_gc")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default="/data1/ekyang/cgh/CODE/mht_work/e1e3")
    a = ap.parse_args(); D = a.root; T = EA.load_trajs(D); out = {"seed_rauc": {}, "reversed": {}}
    for proxy in ("base", "tapt"):
        vals = []
        for k in range(5):
            v = []
            for ds in DS:
                f = f"{D}/oat_{proxy}/outputs/results/ood/mcp_atlas_to_{ds}/OAT_coral/predictions_seed{k}.json"
                for p in json.load(open(f)):
                    key = (ds, p["trajectory_id"])
                    if key not in T: continue
                    sc = dict(zip(p["score_step_indices"], p["scores"])); cand = [c for c in T[key]["cand"] if c in sc]
                    m = EA.metrics_for(sc, cand, T[key]["mistake"])
                    if m and "rauc" in m: v.append(m["rauc"])
            vals.append(float(np.mean(v)))
        out["seed_rauc"][proxy] = vals
    E2 = {n: {(r["dataset"], r["id"]): dict(zip(r["step_indices"], r["step_nll"])) for r in json.load(open(f"{D}/e2_scores_{n}.json"))["rows"]}
          for n in ("base", "tapt", "S", "R")}
    fns = {"base_minus_tapt": lambda k, c: E2["base"][k][c] - E2["tapt"][k][c], "R_minus_S": lambda k, c: E2["R"][k][c] - E2["S"][k][c]}
    for name, fn in fns.items():
        for ds in DS:
            ra, rho, ra2, first2, nb2 = [], [], [], [], []
            for k in T:
                if k[0] != ds: continue
                cand, m = T[k]["cand"], T[k]["mistake"]
                if m not in cand or len(cand) < 3: continue
                s = {c: fn(k, c) for c in cand}
                ra.append(EA.metrics_for(s, cand, m)["rauc"]); rho.append(spearmanr(cand, [s[c] for c in cand]).correlation)
                c2 = cand[1:]
                if m in c2 and len(c2) >= 2:
                    ra2.append(EA.metrics_for(s, c2, m)["rauc"])
                    first2.append(EA.metrics_for({c: -i for i, c in enumerate(c2)}, c2, m)["rauc"])
                    nb2.append(EA.metrics_for({c: E2["base"][k][c] for c in c2}, c2, m)["rauc"])
            out["reversed"][f"{name}/{ds}"] = {"n": len(ra), "rauc": float(np.mean(ra)), "spearman_with_position": float(np.nanmean(rho)),
                                               "without_first_step": {"n": len(ra2), "rauc": float(np.mean(ra2)),
                                                                      "earliest_remaining": float(np.mean(first2)), "nll_base": float(np.mean(nb2))}}
    print(json.dumps(out, indent=1))
    json.dump(out, open(os.path.join(D, "e1e3_exploratory.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
