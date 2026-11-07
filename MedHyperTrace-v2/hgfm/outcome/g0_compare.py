"""Gate G0 (OutcomeCPT amendment A1): Qwen3-8B post-trained vs Qwen3-8B-Base x layers, frozen read-outs.

  python -m hgfm.outcome.g0_compare --w <mht_work> --g0 <mht_work>/outcome/g0 --clusters <clusters.json> --out <json>

Configurations: base (= post-trained, layer 36, the reference), it9 / it18 / it27 (post-trained), b9 / b18 / b27 / b36 (Base).
medical: <g0>/med_<cfg>.json from `hgfm.icpt.med_eval score` (heads linear / agg) -> per-parent paired differences vs base,
  question_id-clustered bootstrap, verdict machinery of hgfm.posttrain.posttrain_eval.cmp.
public:  <g0>/stageA/e4a_<head>_scores.json from `hgfm.e4.e4_probe` (full TT labels) -> controlled rank-AUROC per WW / TEgc
  trajectory (scripts/stage0_analyze.per_traj), jac0.7-clustered bootstrap of the paired difference vs base.
Rule (A1, primary = agg): better = medical controlled diff CI lower > 0 and point >= +0.02 and public controlled diff CI upper >= 0;
switch to the better configuration with the largest medical point estimate; none -> no switch.
"""
import argparse, json, os, sys
import numpy as np

from hgfm.posttrain.posttrain_eval import cmp

CFGS = ["base", "it9", "it18", "it27", "b9", "b18", "b27", "b36"]


def main():
    ap = argparse.ArgumentParser()
    for k in ("w", "g0", "clusters", "out"): ap.add_argument("--" + k)
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
    import stage0_analyze as S, stage0_cluster_ci as C
    C.CL.update(json.load(open(a.clusters))["jac0.7"]); D = S.Data(a.w, None); rng = np.random.default_rng(0)
    R = {"med": {}, "pub": {}, "abs": {}}
    for head in ("agg", "linear"):
        M = {c: json.load(open(os.path.join(a.g0, f"med_{c}.json"))) for c in CFGS if os.path.exists(os.path.join(a.g0, f"med_{c}.json"))}
        par = M["base"]["parents"]
        Ps = json.load(open(os.path.join(a.g0, "stageA", f"e4a_{head}_scores.json")))
        pub = {}
        for c in CFGS:
            sc = Ps.get(f"{head}_{c}")
            if sc is None: continue
            A = {S.K(k): v for k, v in sc.items() if S.K(k)[0] in S.EVAL_DS and S.K(k) in D.meta}
            pub[c] = {kind: S.per_traj(A, D.meta, kind) for kind in ("raw", "resid")}
        for c in CFGS:
            if c not in M: continue
            h = M[c]["heads"][head]
            R["abs"][f"{head}/{c}"] = {"med_resid": float(np.mean([v["resid"] for v in h.values()])), "med_raw": float(np.mean([v["raw"] for v in h.values()])),
                                       "pub_resid": float(np.mean(list(pub[c]["resid"].values()))) if c in pub else None,
                                       "pub_raw": float(np.mean(list(pub[c]["raw"].values()))) if c in pub else None}
            if c == "base": continue
            R["med"][f"{head}/{c}"] = cmp(h, M["base"]["heads"][head], par)
            if c in pub: R["pub"][f"{head}/{c}"] = C.boot_cluster(S.diff(pub[c]["resid"], pub["base"]["resid"]), rng)
    better = []
    for c in CFGS[1:]:
        m = R["med"].get(f"agg/{c}", {}).get("pooled"); p = R["pub"].get(f"agg/{c}")
        if not m or not p: continue
        ok = m["resid"]["ci95"][0] > 0 and m["resid"]["diff"] >= 0.02 and p["ci95"][1] >= 0
        if ok: better.append((m["resid"]["diff"], c))
    R["decision"] = {"better": [c for _, c in sorted(better, reverse=True)], "switch_to": max(better)[1] if better else None}
    json.dump(R, open(a.out, "w"), indent=1)
    for head in ("agg", "linear"):
        print(f"== {head}: absolute (controlled / raw)")
        for c in CFGS:
            x = R["abs"].get(f"{head}/{c}")
            if x: print(f"  {c:5s} med {x['med_resid']:.3f} / {x['med_raw']:.3f}   pub {x['pub_resid'] if x['pub_resid'] is None else round(x['pub_resid'], 3)} / {x['pub_raw'] if x['pub_raw'] is None else round(x['pub_raw'], 3)}")
        print(f"== {head}: paired vs base (post-trained L36), controlled")
        for c in CFGS[1:]:
            m = R["med"].get(f"{head}/{c}", {}).get("pooled"); p = R["pub"].get(f"{head}/{c}")
            if not m: continue
            mr = m["resid"]
            print(f"  {c:5s} med {mr['diff']:+.3f} [{mr['ci95'][0]:+.3f}, {mr['ci95'][1]:+.3f}] grid {m['grid']['same_sign']}/6 {m['verdict']:12s}"
                  + (f" | pub {p['diff']:+.3f} [{p['ci95'][0]:+.3f}, {p['ci95'][1]:+.3f}]" if p else ""))
    print("DECISION", json.dumps(R["decision"]))


if __name__ == "__main__":
    main()
