"""Line 2 (PostTrain pre-registration v1 §2): evaluation of LoRA post-trained scorers against the frozen references.

medical:  python -m hgfm.posttrain.posttrain_eval med --base_feats <featsmed_base.pt> --med_ww <dir> \
              --arm pmed=<fold dir> <fold dir> ... --arm ptt=<P-TT dir> --ref flofo=<med_prefix_base.json>:agg \
              --pairs pmed-flofo ptt-flofo pmedtt-pmed --out <json>
public:   python -m hgfm.posttrain.posttrain_eval pub --w <mht_work> --clusters <clusters.json> --ptt <P-TT dir> --out <json>

medical: per-parent AUROC (raw / controlled / 6-point matched grid) with hgfm.icpt.med_eval.metrics on the base feature
file's parents (step lengths, relative positions); paired differences, question-clustered bootstrap, verdict as
interaction-CPT §4.3 (HOLDS = controlled CI lower > 0 and >= 4/6 grid points with the same sign; NULL = CI upper < 0.04).
public: P-TT vs F-TT (frozen base + linear head trained on TT, E4 stage A) on WW + TEgc, controlled rank-AUROC per
trajectory (scripts/stage0_analyze.per_traj), jac0.7 question clusters (scripts/stage0_cluster_ci.boot_cluster).
"""
import argparse, glob, json, os, sys
import numpy as np

from hgfm.icpt import med_eval as ME


def load_scores(dirs):
    out = {}
    for d in dirs:
        for p in sorted(glob.glob(d)):
            if not os.path.isdir(p): continue   # the glob also matches <run>.log files
            out.update(json.load(open(os.path.join(p, "scores.json"))))
    return out


def cmp(A, B, par):
    strata = {"pooled": lambda u: True, "seen": lambda u: u in ME.SEEN, "unseen": lambda u: u not in ME.SEEN}
    strata.update({u: (lambda uu: (lambda u: u == uu))(u) for u in sorted({v["unit"] for v in par.values()})})
    res = {}
    for sn, f in strata.items():
        ks = [k for k in A if k in B and f(par[k]["unit"])]
        if not ks: continue
        rec = {}
        for m in ["raw", "resid"] + [f"matched_{r}_{w}" for r, w in ME.GRID]:
            kk = [k for k in ks if A[k][m] is not None and B[k][m] is not None]
            rec[m] = ME.boot([A[k][m] - B[k][m] for k in kk], [par[k]["q"] for k in kk]) if kk else {"n": 0}
        g = [rec[f"matched_{r}_{w}"]["diff"] for r, w in ME.GRID if rec[f"matched_{r}_{w}"].get("n")]
        lo, hi = rec["resid"]["ci95"]
        rec["grid"] = {"median": float(np.median(g)) if g else None,
                       "same_sign": int(sum(v > 0 for v in g)) if rec["resid"]["diff"] > 0 else int(sum(v < 0 for v in g))}
        rec["verdict"] = "HOLDS" if lo > 0 and rec["grid"]["same_sign"] >= 4 else "NULL" if hi < 0.04 else "UNDETERMINED"
        res[sn] = rec
    return res


def cmd_med(a):
    P = ME.build(a.base_feats, a.med_ww, "pooled"); arms = {}; par = {k: {"unit": d["unit"], "q": d["q"]} for k, d in P.items()}
    for spec in a.arm:
        name, first = spec[0].split("=", 1); sc = load_scores([first] + spec[1:]); S = {}
        for k, d in P.items():
            v = sc.get(f"med|{k}")
            if v is not None: S[k] = np.array([v[str(int(r))] for r in d["rows"]], float)
        arms[name] = ME.metrics(S, P); print(f"arm {name}: {len(S)} parents scored", flush=True)
    for spec in a.ref:
        name, rest = spec.split("=", 1); path, head = rest.rsplit(":", 1); arms[name] = json.load(open(path))["heads"][head]
        if "longest" not in arms: arms["longest"] = json.load(open(path))["heads"]["baseline_longest"]
    out = {"abs": {}, "cmp": {}}
    for n, M in arms.items():
        ks = [k for k in M if k in P]
        out["abs"][n] = {st: {m: float(np.mean([M[k][m] for k in ks if f(P[k]["unit"]) and M[k][m] is not None]))
                              for m in ("raw", "resid")} for st, f in (("pooled", lambda u: True), ("seen", lambda u: u in ME.SEEN),
                                                                      ("unseen", lambda u: u not in ME.SEEN))}
        print(f"abs {n:8s}", json.dumps(out["abs"][n]))
    for pr in a.pairs:
        x, y = pr.split("-")
        if x not in arms or y not in arms: print(f"skip {pr}"); continue
        out["cmp"][pr] = r = cmp(arms[x], arms[y], par)
        for sn in ("pooled", "seen", "unseen"):
            if sn not in r: continue
            v = r[sn]; z = v["resid"]
            print(f"{pr:14s} {sn:7s} resid {z['diff']:+.3f} [{z['ci95'][0]:+.3f}, {z['ci95'][1]:+.3f}] n={z['n']}/{z['n_questions']}q "
                  f"raw {v['raw']['diff']:+.3f} grid med {v['grid']['median']} same {v['grid']['same_sign']}/6 -> {v['verdict']}", flush=True)
    json.dump(out, open(a.out, "w"), indent=1)


def cmd_pub(a):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
    import stage0_analyze as S, stage0_cluster_ci as C
    C.CL.update(json.load(open(a.clusters))["jac0.7"]); rng = np.random.default_rng(0)
    D = S.Data(a.w, None); sc = json.load(open(os.path.join(a.ptt, "scores.json")))
    A = {S.K(k): [v] for k, v in sc.items() if S.K(k)[0] in S.EVAL_DS and S.K(k) in D.meta}
    B = D.stageA_base(os.path.join(a.w, "e4", "stageA"), "linear"); B = {k: v for k, v in B.items() if k in A}
    out = {}
    for kind in ("raw", "resid"):
        pa, pb = S.per_traj(A, D.meta, kind), S.per_traj(B, D.meta, kind)
        out[kind] = C.boot_cluster(S.diff(pa, pb), rng); out[f"abs_{kind}"] = {"ptt": float(np.mean(list(pa.values()))), "ftt": float(np.mean(list(pb.values())))}
    g = []
    for r, w in ME.GRID:
        ma, mb = S.matched(A, list(A), D.meta, r, w), S.matched(B, list(B), D.meta, r, w); g.append(C.boot_cluster(S.diff(ma, mb), rng)["diff"])
    lo, hi = out["resid"]["ci95"]; same = int(sum(v > 0 for v in g)) if out["resid"]["diff"] > 0 else int(sum(v < 0 for v in g))
    out["grid"] = {"values": g, "same_sign": same}
    out["verdict"] = "HOLDS" if lo > 0 and same >= 4 else "NULL" if hi < 0.04 else "UNDETERMINED"
    json.dump(out, open(a.out, "w"), indent=1); print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    m = sp.add_parser("med"); m.add_argument("--base_feats"); m.add_argument("--med_ww"); m.add_argument("--arm", nargs="+", action="append", default=[])
    m.add_argument("--ref", nargs="*", default=[]); m.add_argument("--pairs", nargs="*", default=[]); m.add_argument("--out")
    p = sp.add_parser("pub"); p.add_argument("--w"); p.add_argument("--clusters"); p.add_argument("--ptt"); p.add_argument("--out")
    a = ap.parse_args(); cmd_med(a) if a.cmd == "med" else cmd_pub(a)


if __name__ == "__main__":
    main()
