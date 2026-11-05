"""Interaction-CPT pre-registration §4.1 / §4.3: medical branching eval set, leave-one-framework-out read-out.

  score:   python -m hgfm.icpt.med_eval score --feats <feats.pt> --ww <med_to_ww out dir> --out <arm.json> [--heads linear mlp]
  compare: python -m hgfm.icpt.med_eval compare --arms base=<a.json> lm=<b.json> icpt=<c.json> --out <cmp.json>

Units (frameworks): mdagents (text + multimodal), llm_debate, medagents_mc, mac_groupchat  = SEEN;
                    agentverse, triage_agent, mam                                       = UNSEEN (not in any CPT corpus).
Points = labelled LLM steps of a parent. Positive = labels.jsonl `positive` (pooled reference, amendment A1);
`--rule judgment` uses the original judgment (sensitivity). Positives that only reflect the last call are dropped.
A parent is evaluable with >= 1 positive and >= 1 other point.
Heads: linear (LayerNorm + Linear), mlp (256 hidden), agg = the interface diagnostic's selected interface (c)
(hgfm.icpt.iface_probe.Agg: 2-layer Transformer over ALL steps of the parent, scores read at the labelled points;
lr 3e-4, otherwise the same recipe). agg is meaningful on prefix features (round 87: SELECTED c_prefix_aggregator).
Read-out: for every unit f, a head is trained on the evaluable parents of the other units (listwise softmax, loss = mean
over positives of -log p; other points are the softmax competitors), early stopping on a 10% question-grouped hold-out of
the training parents (mean AUROC, patience 5, <= 30 epochs), AdamW lr 1e-3, wd 1e-2, 32 parents per step; seeds 0-2.
Per parent: AUROC (positives vs other points, ties 0.5), averaged over seeds, for
  raw; resid = scores residualised per unit on [log ntok, relative position] with parent fixed effects (no labels);
  matched_<r>_<w> = pairs with ntok ratio <= r and |relative position difference| <= w (6 grid points as stage 0).
Trivial baselines (same parents): longest, earliest, latest. Relative position = index among the parent's LLM steps / (n - 1).
compare: paired differences per parent, 1,000-draw bootstrap clustered by question_id; verdict (pre-registration §4.3)
HOLDS = resid CI lower > 0 and >= 4 / 6 matched grid points with the same sign; NULL = resid CI upper < +0.04.
"""
import argparse, json, os
import numpy as np
import torch

UNIT = {"mdagents": "mdagents", "llm_debate": "llm_debate", "medagents_mc": "medagents_mc", "mac_groupchat": "mac_groupchat",
        "agentverse": "agentverse", "triage_agent": "triage_agent", "mam": "mam"}
SEEN = {"mdagents", "llm_debate", "medagents_mc", "mac_groupchat"}
GRID = [(1.5, 0.25), (1.25, 0.25), (1.5, 0.15), (1.25, 0.15), (2.0, 0.5), (1.5, 1.0)]


def build(feats_path, ww, rule):
    man = {os.path.basename(m["id"]): m for m in json.load(open(os.path.join(ww, "manifest.json")))}
    lab = {}
    for l in open(os.path.join(ww, "labels.jsonl")):
        x = json.loads(l); lab.setdefault(x["run_id"], {})[x["step_id"]] = x
    D = torch.load(feats_path, weights_only=False); P = {}
    for r in D["rows"]:
        m = man.get(os.path.basename(r["id"]))
        if m is None or m["framework"] not in UNIT: continue
        L = lab.get(m["run_id"], {}); llm_idx = [i for i, f in enumerate(m["is_llm"]) if f]
        pts, pos = [], []
        for k, i in enumerate(llm_idx):
            x = L.get(m["step_ids"][i])
            if x is None: continue
            p = x["positive"] if rule == "pooled" else x["judgment"] == "positive"
            if p and x["last_call_only"]: continue
            pts.append((i + 1, k / max(len(llm_idx) - 1, 1), p))   # feature row = history index + 1
        if not any(p for *_, p in pts) or all(p for *_, p in pts): continue
        rows = [a for a, _, _ in pts]
        P[m["run_id"]] = {"x": r["feats"][rows].float(), "xf": r["feats"].float(), "rows": torch.tensor(rows), "y": np.array([p for *_, p in pts]), "rel": np.array([b for _, b, _ in pts]),
                          "ntok": np.array([max(r["step_ntok"][a], 1) for a in rows], float), "unit": UNIT[m["framework"]],
                          "q": m["question_id"]}
    return P


def head_of(kind, H):
    if kind == "agg":
        from hgfm.icpt.iface_probe import Agg
        return Agg(H)
    if kind == "linear": return torch.nn.Sequential(torch.nn.LayerNorm(H), torch.nn.Linear(H, 1))
    return torch.nn.Sequential(torch.nn.LayerNorm(H), torch.nn.Linear(H, 256), torch.nn.GELU(), torch.nn.Linear(256, 1))


def auroc(s, y):
    p, n = s[y], s[~y]
    return float(((p[:, None] > n[None]).sum() + 0.5 * (p[:, None] == n[None]).sum()) / (len(p) * len(n)))


def score(h, d, kind):
    return h(d["xf"])[d["rows"]] if kind == "agg" else h(d["x"]).squeeze(-1)


def fit(P, keys, kind, seed):
    torch.manual_seed(seed); rng = np.random.default_rng(seed)
    qs = sorted({P[k]["q"] for k in keys}); hold_q = set(np.random.default_rng(12345).permutation(qs)[: max(1, len(qs) // 10)])
    tr = [k for k in keys if P[k]["q"] not in hold_q]; es = [k for k in keys if P[k]["q"] in hold_q]
    H = P[keys[0]]["x"].shape[1]; h = head_of(kind, H); opt = torch.optim.AdamW(h.parameters(), lr=3e-4 if kind == "agg" else 1e-3, weight_decay=1e-2)
    best, state, bad = -1, None, 0
    for ep in range(30):
        h.train(); perm = rng.permutation(len(tr))
        for b in range(0, len(perm), 32):
            opt.zero_grad(); loss = 0.0
            for i in perm[b:b + 32]:
                d = P[tr[i]]; lp = torch.log_softmax(score(h, d, kind), 0)
                loss = loss - lp[torch.from_numpy(d["y"])].mean()
            (loss / len(perm[b:b + 32])).backward(); opt.step()
        h.eval()
        with torch.no_grad(): v = np.mean([auroc(score(h, P[k], kind).numpy(), P[k]["y"]) for k in es])
        if v > best: best, state, bad = v, {k: t.detach().clone() for k, t in h.state_dict().items()}, 0
        else:
            bad += 1
            if bad >= 5: break
    h.load_state_dict(state); h.eval(); return h


def resid(S, P, keys):
    """OLS of scores on [log ntok, rel] with parent fixed effects, per unit (no labels)."""
    out = {}
    for u in {P[k]["unit"] for k in keys}:
        ks = [k for k in keys if P[k]["unit"] == u]
        X = np.vstack([np.c_[np.log(P[k]["ntok"]), P[k]["rel"]] - np.c_[np.log(P[k]["ntok"]), P[k]["rel"]].mean(0) for k in ks])
        Y = np.concatenate([S[k] - S[k].mean() for k in ks]); beta, *_ = np.linalg.lstsq(X, Y, rcond=None); i = 0
        for k in ks:
            n = len(S[k]); out[k] = np.round(Y[i:i + n] - X[i:i + n] @ beta, 9); i += n   # exact ties stay ties
    return out


def matched(s, d, r, w):
    v = [1.0 if s[i] > s[j] else 0.5 if s[i] == s[j] else 0.0 for i in np.nonzero(d["y"])[0] for j in np.nonzero(~d["y"])[0]
         if abs(np.log(d["ntok"][i] / d["ntok"][j])) <= np.log(r) and abs(d["rel"][i] - d["rel"][j]) <= w]
    return float(np.mean(v)) if v else None


def metrics(S, P):
    R = resid(S, P, list(S)); out = {}
    for k, s in S.items():
        d = P[k]; out[k] = {"raw": auroc(s, d["y"]), "resid": auroc(R[k], d["y"])}
        for r, w in GRID: out[k][f"matched_{r}_{w}"] = matched(s, d, r, w)
    return out


def cmd_score(a):
    P = build(a.feats, a.ww, a.rule); units = sorted({d["unit"] for d in P.values()}); res = {"parents": {}, "heads": {}}
    for k, d in P.items(): res["parents"][k] = {"unit": d["unit"], "q": d["q"], "n_pos": int(d["y"].sum()), "n": len(d["y"])}
    for kind in a.heads:
        per_seed = []
        for sd in (0, 1, 2):
            S = {}
            for u in units:
                tr = [k for k in P if P[k]["unit"] != u]; h = fit(P, tr, kind, sd)
                with torch.no_grad():
                    for k in P:
                        if P[k]["unit"] == u: S[k] = score(h, P[k], kind).numpy().astype(float)
            per_seed.append(metrics(S, P)); print(kind, "seed", sd, "done", flush=True)
        res["heads"][kind] = {k: {m: (float(np.mean([ps[k][m] for ps in per_seed if ps[k][m] is not None]))
                                      if any(ps[k][m] is not None for ps in per_seed) else None) for m in per_seed[0][k]} for k in P}
    base = {}
    for nm, f in (("longest", lambda d: d["ntok"]), ("earliest", lambda d: -d["rel"]), ("latest", lambda d: d["rel"])):
        base[nm] = metrics({k: f(d).astype(float) for k, d in P.items()}, P)
    res["heads"].update({f"baseline_{k}": v for k, v in base.items()})
    res["args"] = vars(a); json.dump(res, open(a.out, "w"))
    for h, v in res["heads"].items():
        for m in ("raw", "resid"):
            print(f"{h:18s} {m:5s}", {u: round(float(np.mean([v[k][m] for k in v if P[k]["unit"] == u])), 3) for u in units})


def boot(diffs, qs, B=1000, seed=0):
    qs = np.asarray(qs); d = np.asarray(diffs, float); uq = np.unique(qs); idx = {q: np.nonzero(qs == q)[0] for q in uq}
    sums = np.array([d[idx[q]].sum() for q in uq]); cnt = np.array([len(idx[q]) for q in uq]); rng = np.random.default_rng(seed)
    bs = [sums[p].sum() / cnt[p].sum() for p in (rng.integers(0, len(uq), len(uq)) for _ in range(B))]
    return {"n": int(len(d)), "n_questions": int(len(uq)), "diff": float(d.mean()), "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}


def cmd_compare(a):
    arms = dict(x.split("=", 1) for x in a.arms); R = {n: json.load(open(p)) for n, p in arms.items()}
    par = next(iter(R.values()))["parents"]; out = {}
    pairs = [("icpt", "lm"), ("icpt", "base"), ("lm", "base")]
    strata = {"pooled": lambda u: True, "seen": lambda u: u in SEEN, "unseen": lambda u: u not in SEEN}
    strata.update({u: (lambda uu: (lambda u: u == uu))(u) for u in sorted({v["unit"] for v in par.values()})})
    for head in a.heads:
        for x, y in pairs:
            if x not in R or y not in R: continue
            A, Bm = R[x]["heads"][head], R[y]["heads"][head]
            for sn, f in strata.items():
                ks = [k for k in A if k in Bm and f(par[k]["unit"])]
                if not ks: continue
                rec = {}
                for m in ["raw", "resid"] + [f"matched_{r}_{w}" for r, w in GRID]:
                    kk = [k for k in ks if A[k][m] is not None and Bm[k][m] is not None]
                    rec[m] = boot([A[k][m] - Bm[k][m] for k in kk], [par[k]["q"] for k in kk]) if kk else {"n": 0}
                g = [rec[f"matched_{r}_{w}"]["diff"] for r, w in GRID if rec[f"matched_{r}_{w}"].get("n")]
                lo, hi = rec["resid"]["ci95"]; same = max(sum(v > 0 for v in g), sum(v < 0 for v in g))
                rec["grid"] = {"median": float(np.median(g)) if g else None, "range": [float(min(g)), float(max(g))] if g else None,
                               "same_sign": int(sum(v > 0 for v in g)) if rec["resid"]["diff"] > 0 else int(sum(v < 0 for v in g))}
                rec["verdict"] = "HOLDS" if lo > 0 and rec["grid"]["same_sign"] >= 4 else "NULL" if hi < 0.04 else "UNDETERMINED"
                out[f"{head}/{x}-{y}/{sn}"] = rec
    json.dump(out, open(a.out, "w"), indent=1)
    for k, v in out.items():
        r = v["resid"]; print(f"{k:40s} resid {r['diff']:+.3f} [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}] n={r['n']}/{r['n_questions']}q "
                              f"raw {v['raw']['diff']:+.3f} grid med {v['grid']['median']} same {v['grid']['same_sign']}/6 -> {v['verdict']}")


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("score"); s.add_argument("--feats"); s.add_argument("--ww"); s.add_argument("--out")
    s.add_argument("--heads", nargs="+", default=["linear", "mlp", "agg"]); s.add_argument("--rule", default="pooled", choices=["pooled", "judgment"])
    c = sp.add_parser("compare"); c.add_argument("--arms", nargs="+"); c.add_argument("--out"); c.add_argument("--heads", nargs="+", default=["linear", "mlp", "agg"])
    a = ap.parse_args(); cmd_score(a) if a.cmd == "score" else cmd_compare(a)


if __name__ == "__main__":
    main()
