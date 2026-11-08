"""Layer-18 re-check analysis (docs/design/Layer18_recheck_prereg_v1.md incl. C1, round 101).

  python scripts/l18rc_analyze.py med --f <runs/l18rc/feats> --out <med_results.json>
  python scripts/l18rc_analyze.py pub --w <runs/l18rc/w> --stage0 <stage0_L18.json> --med <med_results.json> --out <json>
        [--clean results/stage0_manifest/eval_clean_keys.json]

med:
  R1a: cross-fit layer choice. The medical parents are split by question_id into halves A / B; the permutation
       uses numpy default_rng(0) over the sorted unique question ids, and A is the first floor(n/2).
       - On each half, pick the layer with the highest mean controlled AUROC of the post-trained model (it) alone,
         separately for each head.
       - On the other half, take lm(l) and it(l) at that layer.
       - The two halves are pooled into one composite per-parent table, and posttrain_eval.cmp (question-clustered
         bootstrap, the section 4.3 rule) is applied to it.
       - Descriptive output: the lm - it curve over all 8 layers.
  R2.5: at L18, H1 icpt - lm, H2 icpt - it, H3 lm - it. Prefix interface (e4_features), agg head primary,
        linear secondary. The query interface (feat_query, qmed_*) is reported as secondary.
  R2.6: descriptive, every arm at L18 minus it at L18.
pub:
  R2.1: stage A, linear (MLP secondary), tapt / S / R - base.
  R2.2: LE area, tapt / tapt_clean - base.
  R2.3: LE area, R - irr and R - shuf; plus the Q2 rule with the LE area in place of E1 (C1.3).
  R2.4: LE area, full - tapt and full - tapt_clean ("partial NULL" when only the LE condition can be checked, C1.3).
  Holm over the 12-comparison family of C1.5, with a two-sided normal-approximation p from the 95% CI.
"""
import argparse, json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
LS = (9, 12, 15, 18, 21, 24, 27, 36)
HEADS = ("agg", "linear")


def fmt(b):
    if not b or not b.get("n"): return "n/a"
    return f"{b['diff']:+.4f} [{b['ci95'][0]:+.4f}, {b['ci95'][1]:+.4f}] (n={b['n']})"


def pval(b):
    lo, hi = b["ci95"]; se = (hi - lo) / 3.92
    if se <= 0: return 0.0 if b["diff"] != 0 else 1.0
    z = abs(b["diff"]) / se
    return float(math.erfc(z / math.sqrt(2)))


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i]); m = len(ps); adj = [0.0] * m; run = 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (m - r) * ps[i])); adj[i] = run
    return adj


def cmd_med(a):
    from hgfm.posttrain.posttrain_eval import cmp
    L = lambda n: json.load(open(os.path.join(a.f, n)))
    it = {l: L(f"med_it_L{l}.json") for l in LS}; lm = {l: L(f"med_lm_L{l}.json") for l in LS}
    par = it[18]["parents"]; out = {"R1a": {}, "R2_5": {}, "R2_6": {}}
    qs = sorted({v["q"] for v in par.values()}); rng = np.random.default_rng(0); perm = [qs[i] for i in rng.permutation(len(qs))]
    A = set(perm[: len(qs) // 2]); halves = {"A": [k for k in par if par[k]["q"] in A], "B": [k for k in par if par[k]["q"] not in A]}
    out["R1a"]["split"] = {"n_questions": len(qs), "n_parents": {h: len(v) for h, v in halves.items()}}
    for head in HEADS:
        mean = lambda M, ks: float(np.mean([M[k]["resid"] for k in ks if k in M and M[k]["resid"] is not None]))
        sel = {h: {l: mean(it[l]["heads"][head], ks) for l in LS} for h, ks in halves.items()}
        pick = {h: max(LS, key=lambda l: sel[h][l]) for h in halves}
        LMc, ITc = {}, {}
        for h, other in (("A", "B"), ("B", "A")):
            l = pick[h]
            for k in halves[other]:
                if k in lm[l]["heads"][head] and k in it[l]["heads"][head]:
                    LMc[k] = lm[l]["heads"][head][k]; ITc[k] = it[l]["heads"][head][k]
        r = cmp(LMc, ITc, par)["pooled"]
        curve = {l: cmp(lm[l]["heads"][head], it[l]["heads"][head], par)["pooled"]["resid"] for l in LS}
        absit = {l: mean(it[l]["heads"][head], list(par)) for l in LS}; abslm = {l: mean(lm[l]["heads"][head], list(par)) for l in LS}
        out["R1a"][head] = {"selection_it_resid": sel, "picked": pick, "crossfit": r, "curve_lm_minus_it": curve, "abs_it": absit, "abs_lm": abslm}
        print(f"R1a {head:6s} picked A->{pick['A']} B->{pick['B']}  cross-fit lm - it controlled {fmt(r['resid'])} grid {r['grid']['same_sign']}/6 -> {r['verdict']}")
        print(f"    curve lm - it (resid): " + "  ".join(f"L{l} {curve[l]['diff']:+.4f}" for l in LS))
        print(f"    abs it (resid):        " + "  ".join(f"L{l} {absit[l]:.4f}" for l in LS))
    # R2.5: prefix (e4_features) primary, query (feat_query) secondary
    for iface, pre in (("prefix", "med"), ("query", "qmed")):
        try:
            X = {"it": L(f"{pre}_it_L18.json"), "lm": L(f"{pre}_lm_L18.json"), "icpt": L(f"{pre}_icpt_L18.json")}
        except FileNotFoundError as e:
            print(f"R2.5 {iface}: missing {e}"); continue
        out["R2_5"][iface] = {}
        for head in HEADS:
            for nm, x, y in (("H1", "icpt", "lm"), ("H2", "icpt", "it"), ("H3", "lm", "it")):
                r = cmp(X[x]["heads"][head], X[y]["heads"][head], par)
                out["R2_5"][iface][f"{nm}_{head}"] = r
                p = r["pooled"]; print(f"R2.5 {iface:6s} {nm} {x}-{y} {head:6s} controlled {fmt(p['resid'])} grid {p['grid']['same_sign']}/6 -> {p['verdict']}"
                                       f"   seen {fmt(r.get('seen', {}).get('resid'))} unseen {fmt(r.get('unseen', {}).get('resid'))}")
    # R2.6 descriptive
    for m in ("tapt", "S", "R", "full", "irr", "shuf", "tapt_clean"):
        f = os.path.join(a.f, f"med_{m}_L18.json")
        if not os.path.exists(f): print(f"R2.6 {m}: missing"); continue
        X = json.load(open(f)); out["R2_6"][m] = {}
        for head in HEADS:
            r = cmp(X["heads"][head], it[18]["heads"][head], par)["pooled"]; out["R2_6"][m][head] = r
            print(f"R2.6 {m:10s}-it {head:6s} controlled {fmt(r['resid'])} grid {r['grid']['same_sign']}/6 (descriptive)")
    json.dump(out, open(a.out, "w"), indent=1, default=str)


def cmd_pub(a):
    import stage0_analyze as S
    D = S.Data(a.w, a.clean); rng = np.random.default_rng(0); R0 = json.load(open(a.stage0)); out = {"family": [], "secondary": {}}
    fam = []
    for p in ("tapt", "S", "R"):
        c = R0["stageA"]["linear"].get(f"{p}-base"); fam.append(("R2.1", f"stageA linear {p}-base", c["resid"] if c else None, None))
        cm = R0["stageA"]["mlp"].get(f"{p}-base"); out["secondary"][f"stageA mlp {p}-base"] = cm["resid"] if cm else None
    le = {}
    for x, y in (("tapt", "base"), ("tapt_clean", "base"), ("R", "irr"), ("R", "shuf"), ("full", "tapt"), ("full", "tapt_clean"), ("irr", "base"),
                 ("S", "base"), ("R", "base"), ("shuf", "base"), ("full", "base")):
        for h in ("linear", "mlp"):
            le[(h, x, y)] = S.compare_le(D, rng, h, x, y)
    for tag, pairs in (("R2.2", (("tapt", "base"), ("tapt_clean", "base"))), ("R2.3", (("R", "irr"), ("R", "shuf"))),
                       ("R2.4", (("full", "tapt"), ("full", "tapt_clean")))):
        for x, y in pairs:
            c = le[("linear", x, y)]; fam.append((tag, f"LE linear {x}-{y}", c["area_resid"] if c else None, None))
    for x, y in [k[1:] for k in le if k[0] == "mlp"]:
        c = le[("mlp", x, y)]; out["secondary"][f"LE mlp {x}-{y}"] = c["area_resid"] if c else None
    for x, y in (("irr", "base"), ("S", "base"), ("R", "base"), ("shuf", "base"), ("full", "base")):
        c = le[("linear", x, y)]; out["secondary"][f"LE linear {x}-{y}"] = c["area_resid"] if c else None
    M = json.load(open(a.med))["R2_5"]["prefix"]
    for nm, lab in (("H1", "icpt-lm"), ("H2", "icpt-it"), ("H3", "lm-it")):
        p = M[f"{nm}_agg"]["pooled"]; fam.append(("R2.5", f"med agg {nm} {lab}", p["resid"], p))
    ps = [pval(b) if b and b.get("n") else 1.0 for _, _, b, _ in fam]; adj = holm(ps)
    print("== Holm family (12, controlled, primary readout) ==")
    for (tag, lab, b, med), pv, pa in zip(fam, ps, adj):
        if med is not None: v = med["verdict"]; extra = f" grid {med['grid']['same_sign']}/6"
        else: v = S.verdict(b) if b else "n/a"; extra = ""
        concl = ("overturned at L18" if v == "HOLDS" and pa < 0.05 else "needs replication" if v == "HOLDS" else
                 "NULL at L18" if v == "NULL" else "undetermined at L18")
        out["family"].append({"tag": tag, "label": lab, "boot": b, "verdict": v, "p": pv, "p_holm": pa, "conclusion": concl})
        print(f"{tag:5s} {lab:28s} {fmt(b)}{extra} -> {v:12s} p={pv:.4f} Holm={pa:.4f}  {concl}")
    # Q2 rule (LE area in place of E1 primary, C1.3)
    c2 = {f"{x}-{y}": {"primary": le[("linear", x, y)]["area_resid"]} if le[("linear", x, y)] else None for x, y in (("irr", "base"), ("R", "irr"), ("R", "shuf"))}
    out["Q2_rule_LE"] = S.q2_rule(c2); print("Q2 rule (LE area for E1):", out["Q2_rule_LE"])
    out["Q3_LE"] = {}
    for x, y in (("full", "tapt"), ("full", "tapt_clean")):
        c = le[("linear", x, y)]; v = S.verdict(c["area_resid"]) if c else "n/a"
        out["Q3_LE"][f"{x}-{y}"] = "partial NULL (E1 not checked at L18)" if v == "NULL" else v
    print("Q3 (LE only):", out["Q3_LE"])
    print("== secondary ==")
    for k, b in out["secondary"].items(): print(f"  {k:28s} {fmt(b)}")
    json.dump(out, open(a.out, "w"), indent=1, default=str)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd")
    m = sp.add_parser("med"); m.add_argument("--f"); m.add_argument("--out")
    p = sp.add_parser("pub"); p.add_argument("--w"); p.add_argument("--stage0"); p.add_argument("--med"); p.add_argument("--out")
    p.add_argument("--clean", default=os.path.join(os.path.dirname(__file__), "..", "results", "stage0_manifest", "eval_clean_keys.json"))
    a = ap.parse_args(); {"med": cmd_med, "pub": cmd_pub}[a.cmd](a)
