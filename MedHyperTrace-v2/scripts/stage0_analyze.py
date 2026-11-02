"""Stage 0 analysis (pre-registration docs/design/Stage0_prereg_v1.md incl. appendix A1). Run on Linux #2 in the code dir:

  python scripts/stage0_analyze.py --w /data1/ekyang/cgh/CODE/mht_work --clean <eval_clean_keys.json> --out <json> [--dry]

Evaluation set: Who&When + TraceElephant groupchat, E4-evaluable trajectories (candidates = model steps), pooled.
Metrics (all from hgfm/e4/e4_eval.py, as E1/E4): within-trajectory rank-AUROC, raw and "controlled" (OLS residual on
[log step tokens, relative position, has_code] with trajectory fixed effects, fitted per setting / dataset / seed without
labels); matched pairs (round-75 rule, function copied verbatim from analysis/e4_overlap_matched.py). Metrics per seed /
draw, then mean per trajectory; paired bootstrap over trajectories (1000, seed 0), percentile 95% CI.
Verdict rule (prereg): CI lower > 0 -> HOLDS; CI upper < +0.04 -> NULL (null bound); else UNDETERMINED.
Sources of scores:
  label efficiency  stage0/le/le_<head>_<proxy>.json   {"scores": {"<head>_<proxy>_n<n>": {"ds|id": [per-draw lists]}}}
  stage A full      e4/stageA/e4a_<head>_scores.json (base tapt S R), stage0/stageA/ (base shuf irr full),
                    stage0/stageA_clean/ (base tapt_clean)   {"<head>_<proxy>": {"ds|id": [per-seed lists]}}
  E1 OAT            e1e3/oat_<proxy>/outputs/results/ood/mcp_atlas_to_<ds>/OAT_coral/predictions_seed<s>.json
Sensitivity subsets: from results/stage0_manifest/eval_clean_keys.json per_key[...]["direct_0.3"] (direct rule, round 75):
  a comparison X - Y keeps the trajectories whose question overlaps none of the corpora of X and Y (+ TT_train for the
  supervised readouts). Corpora: tapt->tapt, S->S, R->R, shuf->R, full->full; base / irr / tapt_clean -> none.
"""
import argparse, json, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from hgfm.e4 import e4_eval as EV   # noqa: E402

EVAL_DS = ("who_and_when", "traceelephant_gc")
SIZES = (100, 300, 1000)
VARIANTS = [(1.5, 0.25), (1.25, 0.25), (1.5, 0.15), (1.25, 0.15), (2.0, 0.5), (1.5, 1.0)]
CORP = {"tapt": {"tapt"}, "S": {"S"}, "R": {"R"}, "shuf": {"R"}, "full": {"full"}, "base": set(), "irr": set(), "tapt_clean": set()}
NULL_BOUND = 0.04


def matched(scs, keys, meta, r, w):   # verbatim from analysis/e4_overlap_matched.py (round 75)
    per = {}
    for k in keys:
        m = meta[k]; c = m["cand"]; L = m["label"]
        if L not in c: continue
        N = max(m["n_steps"] - 1, 1); vals = []
        for sd in scs[k]:
            s = dict(zip(c, sd))
            v = [1.0 if s[L] > s[j] else 0.5 if s[L] == s[j] else 0.0 for j in c
                 if j != L and abs(np.log(max(m["ntok"][j], 1) / max(m["ntok"][L], 1))) <= np.log(r)
                 and abs((j - L) / N) <= w and m["code"][j] == m["code"][L]]
            if v: vals.append(np.mean(v))
        if vals: per[k] = float(np.mean(vals))
    return per


def K(s): return tuple(s.split("|", 1))


def per_traj(sc, meta, kind):
    """{key: [lists]} -> {key: rauc} (raw | resid), via e4_eval.per_traj."""
    keys = [k for k in sc if k in meta]
    return {k: v["rauc"] for k, v in EV.per_traj({"x": {k: sc[k] for k in keys}}, meta, kind).get("x", {}).items()}


def boot(d, rng, B=1000):
    x = np.array(list(d.values()), float)
    if not len(x): return {"n": 0}
    bs = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(B)]
    return {"n": int(len(x)), "diff": float(x.mean()), "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}


def verdict(b):
    if not b.get("n"): return "n/a"
    lo, hi = b["ci95"]
    return "HOLDS" if lo > 0 else "NULL" if hi < NULL_BOUND else "UNDETERMINED"


def diff(A, B, keys=None):
    ks = [k for k in A if k in B and (keys is None or k in keys)]
    return {k: A[k] - B[k] for k in ks}


class Data:
    def __init__(self, W, clean):
        self.W = W; self.S0 = os.path.join(W, "stage0")
        self.meta = {K(k): v for k, v in json.load(open(os.path.join(self.S0, "le", "meta.json"))).items() if K(k)[0] in EVAL_DS}
        self.per_key = {K(k): set(v["direct_0.3"]) for k, v in json.load(open(clean))["per_key"].items()} if clean else {}

    def clean_keys(self, x, y, supervised):
        bad = CORP.get(x, set()) | CORP.get(y, set()) | ({"TT_train"} if supervised else set())
        return {k for k in self.meta if k in self.per_key and not (self.per_key[k] & bad)}

    def le(self, head, proxy):
        p = os.path.join(self.S0, "le", f"le_{head}_{proxy}.json")
        if not os.path.exists(p): return None
        d = json.load(open(p))["scores"]
        return {n: {K(k): v for k, v in d[f"{head}_{proxy}_n{n}"].items() if K(k)[0] in EVAL_DS} for n in SIZES if f"{head}_{proxy}_n{n}" in d}

    def stageA(self, head, proxy):
        for d in (os.path.join(self.W, "e4", "stageA"), os.path.join(self.S0, "stageA"), os.path.join(self.S0, "stageA_clean")):
            p = os.path.join(d, f"e4a_{head}_scores.json")
            if os.path.exists(p):
                j = json.load(open(p))
                if f"{head}_{proxy}" in j and proxy != "base":
                    return {K(k): v for k, v in j[f"{head}_{proxy}"].items() if K(k)[0] in EVAL_DS}, d
        return None, None

    def stageA_base(self, run_dir, head):
        j = json.load(open(os.path.join(run_dir, f"e4a_{head}_scores.json")))
        return {K(k): v for k, v in j[f"{head}_base"].items() if K(k)[0] in EVAL_DS}

    def oat(self, proxy, avg):
        acc = {}
        for ds in EVAL_DS:
            for s5 in range(5):
                f = os.path.join(self.W, "e1e3", f"oat_{proxy}", "outputs", "results", "ood", f"mcp_atlas_to_{ds}", "OAT_coral", f"predictions_seed{s5}.json")
                if not os.path.exists(f): return None
                for pr in json.load(open(f)):
                    for si, sc in zip(pr["score_step_indices"], pr["scores"]):
                        acc.setdefault((ds, pr["trajectory_id"]), {}).setdefault(si + 1, {})[s5] = sc
        out = {}
        for k, d in acc.items():
            if k not in self.meta: continue
            c = self.meta[k]["cand"]
            seeds = [[d.get(j, {}).get(s5, -1e9) for j in c] for s5 in range(5)]
            out[k] = [[float(np.mean([x for x in col if x > -1e8])) if any(x > -1e8 for x in col) else -1e9 for col in zip(*seeds)]] if avg else seeds
        return out


def le_metrics(D, head, proxy):
    sc = D.le(head, proxy)
    if sc is None or len(sc) < len(SIZES): return None
    out = {"raw": {}, "resid": {}, "matched": {}}
    for n in SIZES:
        out["raw"][n] = per_traj(sc[n], D.meta, "raw"); out["resid"][n] = per_traj(sc[n], D.meta, "resid")
        out["matched"][n] = matched(sc[n], list(sc[n]), D.meta, 1.5, 0.25)
    ks = set.intersection(*[set(out["resid"][n]) for n in SIZES])
    out["area_resid"] = {k: float(np.mean([out["resid"][n][k] for n in SIZES])) for k in ks}
    ks = set.intersection(*[set(out["raw"][n]) for n in SIZES])
    out["area_raw"] = {k: float(np.mean([out["raw"][n][k] for n in SIZES])) for k in ks}
    return out


def compare_le(D, rng, head, x, y="base"):
    A, B = le_metrics(D, head, x), le_metrics(D, head, y)
    if A is None or B is None: return None
    r = {"area_resid": boot(diff(A["area_resid"], B["area_resid"]), rng), "area_raw": boot(diff(A["area_raw"], B["area_raw"]), rng)}
    r["verdict"] = verdict(r["area_resid"])
    for n in SIZES:
        r[f"n{n}"] = {kd: boot(diff(A[kd][n], B[kd][n]), rng) for kd in ("raw", "resid", "matched")}
    ck = D.clean_keys(x, y, True)
    r["clean"] = {"n_keys": len(ck), "area_resid": boot(diff(A["area_resid"], B["area_resid"], ck), rng)}
    r["abs"] = {p: {"area_resid": float(np.mean(list(M["area_resid"].values()))), **{f"n{n}_resid": float(np.mean(list(M["resid"][n].values()))) for n in SIZES}}
                for p, M in ((x, A), (y, B))}
    return r


def compare_stageA(D, rng, head, x, y="base"):
    A, run = D.stageA(head, x)
    if A is None: return None
    if y == "base": Bs = D.stageA_base(run, head)
    else:
        Bs, _ = D.stageA(head, y)
        if Bs is None: return None
    r = {}
    for kd in ("raw", "resid"):
        r[kd] = boot(diff(per_traj(A, D.meta, kd), per_traj(Bs, D.meta, kd)), rng)
    r["matched_1.5_0.25"] = boot(diff(matched(A, list(A), D.meta, 1.5, 0.25), matched(Bs, list(Bs), D.meta, 1.5, 0.25)), rng)
    ck = D.clean_keys(x, y, True)
    r["clean"] = {"n_keys": len(ck), "resid": boot(diff(per_traj(A, D.meta, "resid"), per_traj(Bs, D.meta, "resid"), ck), rng)}
    return r


def compare_e1(D, rng, x, y="base", keys=None):
    Aa, Ba, As, Bs = D.oat(x, True), D.oat(y, True), D.oat(x, False), D.oat(y, False)
    if None in (Aa, Ba, As, Bs): return None
    r = {"matched": {}}
    for rr, w in VARIANTS:
        r["matched"][f"r{rr}_w{w}"] = boot(diff(matched(Aa, list(Aa), D.meta, rr, w), matched(Ba, list(Ba), D.meta, rr, w), keys), rng)
    for kd in ("raw", "resid"):
        r[kd] = boot(diff(per_traj(As, D.meta, kd), per_traj(Bs, D.meta, kd), keys), rng)
    r["primary"] = r["matched"]["r1.5_w0.25"]
    ck = D.clean_keys(x, y, False) if keys is None else None
    if ck is not None:
        r["clean"] = {"n_keys": len(ck), "matched_1.5_0.25": boot(diff(matched(Aa, list(Aa), D.meta, 1.5, 0.25), matched(Ba, list(Ba), D.meta, 1.5, 0.25), ck), rng),
                      "resid": boot(diff(per_traj(As, D.meta, "resid"), per_traj(Bs, D.meta, "resid"), ck), rng)}
    return r


def q2_rule(c):
    def lo(b): return b["ci95"][0] if b and b.get("n") else None
    def has0(b): return b and b.get("n") and b["ci95"][0] <= 0 <= b["ci95"][1]
    irr_b, R_irr, R_shuf = c.get("irr-base"), c.get("R-irr"), c.get("R-shuf")
    if None in (irr_b, R_irr, R_shuf): return "n/a"
    irr_b, R_irr, R_shuf = irr_b["primary"], R_irr["primary"], R_shuf["primary"]
    if lo(irr_b) > 0 and has0(R_irr): return "1 generic continued-pretraining drift"
    if lo(R_irr) > 0 and lo(R_shuf) > 0: return "2 trajectory order / structure matters"
    if lo(R_irr) > 0 and has0(R_shuf): return "3 MAS content, not order"
    return "4 undetermined"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--w"); ap.add_argument("--clean"); ap.add_argument("--out"); ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(); D = Data(a.w, a.clean); rng = np.random.default_rng(0); R = {"n_eval": len(D.meta)}
    # Q1 / Q1' label efficiency (+ descriptive proxies)
    R["Q1"] = {h: {p: compare_le(D, rng, h, p) for p in ("tapt", "tapt_clean", "S", "R", "shuf", "irr", "full")} for h in ("linear", "mlp")}
    # stage A full-label (E4 recipe), every proxy vs its run's base; plus tapt - tapt_clean, full - tapt, full - tapt_clean
    R["stageA"] = {h: {**{f"{p}-base": compare_stageA(D, rng, h, p) for p in ("tapt", "S", "R", "shuf", "irr", "full", "tapt_clean")},
                       **{f"{x}-{y}": compare_stageA(D, rng, h, x, y) for x, y in (("tapt", "tapt_clean"), ("full", "tapt"), ("full", "tapt_clean"))}}
                   for h in ("linear", "mlp")}
    # Q2 negative controls + E1 for every proxy
    pairs = [(p, "base") for p in ("tapt", "S", "R", "shuf", "irr", "full", "tapt_clean")] + [("R", "shuf"), ("R", "irr"), ("tapt", "tapt_clean"), ("full", "tapt"), ("full", "tapt_clean")]
    R["E1"] = {f"{x}-{y}": compare_e1(D, rng, x, y) for x, y in pairs}
    R["Q2_rule"] = q2_rule(R["E1"])
    # Q3 / Q3' dose
    R["Q3"] = {}
    for x, y in (("full", "tapt"), ("full", "tapt_clean")):
        le_ = compare_le(D, rng, "linear", x, y); e1 = R["E1"].get(f"{x}-{y}")
        v = "n/a"
        if le_:
            v = verdict(le_["area_resid"])
            if v != "HOLDS" and e1 and e1["primary"].get("n") and le_["area_resid"]["ci95"][1] < NULL_BOUND and e1["primary"]["ci95"][1] < NULL_BOUND: v = "NULL"
            elif v == "NULL": v = "UNDETERMINED"   # prereg: NULL needs BOTH the LE area and E1 matched under the bound
        R["Q3"][f"{x}-{y}"] = {"le_linear": le_, "verdict": v}
    # descriptive: tapt - base split by overlap with the TAPT corpus (E1 OAT)
    ov = {k for k in D.meta if "tapt" in D.per_key.get(k, set())}
    R["tapt_overlap_split"] = {nm: compare_e1(D, rng, "tapt", "base", keys=ks) for nm, ks in (("overlap", ov), ("no_overlap", set(D.meta) - ov))}
    R["tapt_overlap_split"]["n"] = {"overlap": len(ov), "no_overlap": len(D.meta) - len(ov)}
    json.dump(R, open(a.out, "w"), indent=1, default=str)
    # printout
    f = lambda b: "n/a" if not b or not b.get("n") else f"{b['diff']:+.3f} [{b['ci95'][0]:+.3f}, {b['ci95'][1]:+.3f}] (n={b['n']})"
    print("n_eval", R["n_eval"])
    for h in ("linear", "mlp"):
        for p, c in R["Q1"][h].items():
            if c: print(f"Q1 {h:6s} {p:10s}-base  LE area resid {f(c['area_resid'])}  raw {f(c['area_raw'])}  -> {c['verdict']}"
                        f"   | clean({c['clean']['n_keys']}) {f(c['clean']['area_resid'])}", flush=True)
    for h in ("linear", "mlp"):
        for p, c in R["stageA"][h].items():
            if c: print(f"stageA {h:6s} {p:18s} raw {f(c['raw'])}  resid {f(c['resid'])}  matched {f(c['matched_1.5_0.25'])}  clean({c['clean']['n_keys']}) {f(c['clean']['resid'])}")
    for p, c in R["E1"].items():
        if c: print(f"E1 {p:18s} matched(1.5,.25) {f(c['primary'])}  resid {f(c['resid'])}  raw {f(c['raw'])}" + (f"  clean({c['clean']['n_keys']}) {f(c['clean']['matched_1.5_0.25'])}" if 'clean' in c else ""))
    print("Q2 rule:", R["Q2_rule"])
    for p, c in R["Q3"].items(): print("Q3", p, c["verdict"], f(c["le_linear"]["area_resid"]) if c["le_linear"] else "n/a")
    for nm in ("overlap", "no_overlap"):
        c = R["tapt_overlap_split"][nm]
        if c: print(f"tapt-base E1 on {nm} ({R['tapt_overlap_split']['n'][nm]}): matched {f(c['primary'])} resid {f(c['resid'])} raw {f(c['raw'])}")
    if a.dry: print("DRY RUN: partial inputs, verdicts are not to be reported")


if __name__ == "__main__":
    main()
