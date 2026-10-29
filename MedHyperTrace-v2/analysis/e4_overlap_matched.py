"""Round 75 (exploratory, after E1/E4 results): (1) near-duplicate task overlap between TracerTraj and the E3 held-out
sets, and E4 re-scored on the non-overlapping subset; (2) matched-pair within-trajectory ranking for E1 (OAT) and E4.

  python -m analysis.e4_overlap_matched --e4 <mht_work/e4> --e1 <mht_work/e1e3> --tt <agentracer-data-v1.0.0> --out <json>

(1) overlap = max word-set Jaccard between an E3 question and any TracerTraj *train-file* question (our train + val);
    >= 0.3 counts as overlapping (the distribution is bimodal: 110 at >= 0.3, 106 at >= 0.5).
(2) matched pairs (rule fixed before computing): mistake step vs another candidate of the same trajectory with
    |log length ratio| <= log(r), |relative position difference| <= w, same has_code; score = P(mistake ranked higher)
    (ties 0.5), mean over seeds, then over trajectories with >= 1 pair; paired bootstrap over trajectories (1000).
    Variants (r, w): (1.5, 0.25) first, then (1.25, 0.25), (1.5, 0.15), (1.25, 0.15), (2.0, 0.5), (1.5, 1.0) -- all reported.
"""
import argparse, json, os, re, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from hgfm.e4 import e4_eval as EV   # noqa: E402
from hgfm.e4.e4_probe import load   # noqa: E402

tokset = lambda s: set(re.findall(r"[a-z0-9]+", (s or "").lower()))
VARIANTS = [(1.5, 0.25), (1.25, 0.25), (1.5, 0.15), (1.25, 0.15), (2.0, 0.5), (1.5, 1.0)]


def boot(d, rng):
    x = np.array(list(d.values()))
    if not len(x): return {"n": 0}
    bs = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(1000)]
    return {"mean": float(x.mean()), "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], "n": len(x)}


def matched(scs, keys, meta, r, w):
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


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--e4"); ap.add_argument("--e1"); ap.add_argument("--tt"); ap.add_argument("--out")
    a = ap.parse_args(); rng = np.random.default_rng(0); R = {}
    sys.path.insert(0, os.path.join(a.e1, "oat_src")); cwd = os.getcwd(); os.chdir(os.path.join(a.e1, "oat_src"))
    import data_pipeline as dp
    Q = {(ds, t["id"]): t.get("question", "") for ds in ("who_and_when", "traceelephant_gc") for t in dp.load_raw_trajectories(ds)}
    os.chdir(cwd)
    TT = [tokset(json.loads(l)["question"]) for dom in ("agentic", "coding", "math") for l in open(os.path.join(a.tt, dom, "train.jsonl"))]
    ovl = {k: max(len(tokset(q) & b) / max(1, len(tokset(q) | b)) for b in TT if b) for k, q in Q.items()}
    R["overlap_counts"] = {str(th): sum(v >= th for v in ovl.values()) for th in (0.3, 0.5, 0.7, 0.9)}
    rows, _ = load(os.path.join(a.e4, "feats_base.pt")); SC = {}
    for kind in ("linear", "mlp"):
        d = json.load(open(os.path.join(a.e4, "stageA", f"e4a_{kind}_scores.json")))
        for st in (f"{kind}_base", f"{kind}_tapt"): SC[st] = {tuple(k.split("|", 1)): v for k, v in d[st].items()}
    for n in ("base", "tapt"):
        SC[f"beft_{n}"] = {tuple(k.split("|", 1)): [v] for k, v in json.load(open(os.path.join(a.e4, f"beft_{n}", "scores.json"))).items()}
    keys = set.intersection(*[set(v) for v in SC.values()]) & {k for k in rows if k[0] in ("who_and_when", "traceelephant_gc")}
    meta = {k: {kk: rows[k][kk] for kk in ("cand", "label", "ntok", "code", "n_steps")} for k in keys}
    for proxy in ("base", "tapt"):
        acc = {}
        for ds in ("who_and_when", "traceelephant_gc"):
            for s5 in range(5):
                f = os.path.join(a.e1, f"oat_{proxy}", "outputs", "results", "ood", f"mcp_atlas_to_{ds}", "OAT_coral", f"predictions_seed{s5}.json")
                for pr in json.load(open(f)):
                    for si, s in zip(pr["score_step_indices"], pr["scores"]): acc.setdefault((ds, pr["trajectory_id"]), {}).setdefault(si + 1, []).append(s)
        SC[f"oat_{proxy}"] = {k: [[float(np.mean(acc[k][j])) if j in acc[k] else -1e9 for j in rows[k]["cand"]]] for k in acc if k in keys}
    SC["longest"] = {k: [[rows[k]["ntok"][j] for j in rows[k]["cand"]]] for k in keys}
    # (1) E4 on clean / overlap subsets
    clean = {k for k in keys if ovl[k] < 0.3}; R["subsets"] = {}
    for nm, ks in (("clean", clean), ("overlap", keys - clean)):
        EV.SETS = {nm: ("who_and_when", "traceelephant_gc")}
        sc = {st: {k: v for k, v in d.items() if k in ks} for st, d in SC.items() if st.startswith(("linear", "mlp", "beft"))}
        res = EV.evaluate(sc, {k: meta[k] for k in ks}, [("linear_tapt", "linear_base"), ("mlp_tapt", "mlp_base"), ("beft_tapt", "beft_base")])
        R["subsets"][nm] = {"n": len(ks), "summary": res["summary"], "paired": {k: v for k, v in res["paired"].items() if "rauc" in k}}
    # (2) matched pairs
    R["matched"] = {}
    for r, w in VARIANTS:
        row = {"abs": {st: boot(matched(SC[st], keys, meta, r, w), rng) for st in SC}}
        for x, y in (("oat_tapt", "oat_base"), ("linear_tapt", "linear_base"), ("mlp_tapt", "mlp_base"), ("beft_tapt", "beft_base")):
            A, Bm = matched(SC[x], keys, meta, r, w), matched(SC[y], keys, meta, r, w)
            row[f"{x} - {y}"] = boot({k: A[k] - Bm[k] for k in A if k in Bm}, rng)
        R["matched"][f"r{r}_w{w}"] = row
        print(f"r={r} w={w}", {k: (round(v["mean"], 3), [round(c, 3) for c in v["ci95"]], v["n"]) for k, v in row.items() if k != "abs"}, flush=True)
    print("overlap", R["overlap_counts"], {nm: (v["n"], round(v["paired"][f"beft_tapt - beft_base / {nm} / resid / rauc"]["diff"], 3)) for nm, v in R["subsets"].items()})
    json.dump(R, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
