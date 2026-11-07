"""Line 3 gate G (OutcomeCPT pre-registration §1): does outcome information in frozen features align with branch attribution?

  python -m hgfm.outcome.value_gate --corpus_feats <feats.pt> --corpus_ww <corpus_to_ww dir> \
      --med_feats <featsmed_base.pt> --med_ww <med_to_ww dir> --out <json>

1 Outcome probe v: LayerNorm + Linear logistic on every LLM-step prefix feature of the corpus runs, target = run is_correct
  (BCE, each run weighted equally), AdamW lr 1e-3 wd 1e-2, <= 20 epochs, early stopping on a question-grouped 10% hold-out
  (step-level AUROC, patience 3); seeds 0 / 1 / 2, probabilities averaged. Validity: AUROC at the last LLM step on the hold-out.
2 Attribution score on the eval parents: drop(t) = v(t_prev) - v(t) over the parent's LLM steps (first LLM step: t_prev
  value = mean v of first LLM steps in the training runs). Secondary: neg_v(t) = -v(t).
3 Evaluation = hgfm.icpt.med_eval (same parents, positives, controls, grid, question-clustered bootstrap).
Gate (pre-registered): GO = controlled AUROC CI lower > 0.50, point >= 0.53, >= 4/6 grid points > 0.50;
NO-GO = CI upper < 0.53; else UNCLEAR. Probe validity requires last-step hold-out AUROC >= 0.60.
"""
import argparse, json, os
import numpy as np
import torch

from hgfm.icpt import med_eval as ME


def auc(s, y):
    s = np.asarray(s); y = np.asarray(y, bool)
    if y.all() or (~y).all(): return float("nan")
    o = np.argsort(s, kind="mergesort"); r = np.empty(len(s)); r[o] = np.arange(1, len(s) + 1)
    _, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)   # average ranks for ties
    sums = np.zeros(len(cnt)); np.add.at(sums, inv, r); r = (sums / cnt)[inv]
    return float((r[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum()))


def load_corpus(feats, ww):
    man = {os.path.basename(m["id"]): m for m in json.load(open(os.path.join(ww, "manifest.json")))}
    D = torch.load(feats, weights_only=False); runs = []
    for r in D["rows"]:
        m = man.get(os.path.basename(r["id"]))
        if m is None: continue
        rows = [i + 1 for i, f in enumerate(m["is_llm"]) if f]
        if not rows: continue
        runs.append({"x": r["feats"][rows].float(), "y": float(m["is_correct"]), "q": m["question_id"], "fw": m["framework"]})
    return runs


def train_probe(runs, seed):
    torch.manual_seed(seed); rng = np.random.default_rng(seed)
    qs = sorted({r["q"] for r in runs}); hold = set(np.random.default_rng(12345).permutation(qs)[: max(1, len(qs) // 10)])
    tr = [r for r in runs if r["q"] not in hold]; es = [r for r in runs if r["q"] in hold]
    X = torch.cat([r["x"] for r in tr]); Y = torch.cat([torch.full((len(r["x"]),), r["y"]) for r in tr])
    W = torch.cat([torch.full((len(r["x"]),), 1.0 / len(r["x"])) for r in tr]); W = W / W.mean()
    H = X.shape[1]; h = torch.nn.Sequential(torch.nn.LayerNorm(H), torch.nn.Linear(H, 1))
    opt = torch.optim.AdamW(h.parameters(), lr=1e-3, weight_decay=1e-2); best, state, bad = -1, None, 0

    def evaluate(model):
        with torch.no_grad():
            s = [torch.sigmoid(model(r["x"]).squeeze(-1)).numpy() for r in es]
        step = auc(np.concatenate(s), np.concatenate([[r["y"]] * len(x) for r, x in zip(es, s)]) > 0.5)
        last = auc(np.array([x[-1] for x in s]), np.array([r["y"] for r in es]) > 0.5)
        return step, last

    for ep in range(20):
        h.train(); perm = rng.permutation(len(X))
        for b in range(0, len(perm), 256):
            i = perm[b:b + 256]; opt.zero_grad()
            l = torch.nn.functional.binary_cross_entropy_with_logits(h(X[i]).squeeze(-1), Y[i], weight=W[i]); l.backward(); opt.step()
        h.eval(); v, last = evaluate(h)
        if v > best: best, state, bad, best_last = v, {k: t.detach().clone() for k, t in h.state_dict().items()}, 0, last
        else:
            bad += 1
            if bad >= 3: break
    h.load_state_dict(state); h.eval()
    with torch.no_grad(): first = float(np.mean([torch.sigmoid(h(r["x"][:1])).item() for r in tr]))
    return h, {"holdout_step_auroc": best, "holdout_last_step_auroc": best_last, "first_step_prior": first, "n_train_runs": len(tr), "n_hold_runs": len(es)}


def summarise(M, P, keys):
    def mean(m): v = [M[k][m] for k in keys if M[k][m] is not None]; return float(np.mean(v)) if v else None
    out = {"n": len(keys), "raw": mean("raw"), "resid": mean("resid")}
    out["resid_boot"] = ME.boot([M[k]["resid"] - 0.5 for k in keys], [P[k]["q"] for k in keys])
    out["resid_boot"]["ci95_auroc"] = [0.5 + c for c in out["resid_boot"]["ci95"]]
    g = [mean(f"matched_{r}_{w}") for r, w in ME.GRID]; out["grid"] = g; out["grid_above_half"] = sum(1 for x in g if x is not None and x > 0.5)
    return out


def gate(s):
    lo, hi = s["resid_boot"]["ci95_auroc"]
    if lo > 0.5 and s["resid"] >= 0.53 and s["grid_above_half"] >= 4: return "GO"
    if hi < 0.53: return "NO-GO"
    return "UNCLEAR"


def main():
    ap = argparse.ArgumentParser()
    for k in ("corpus_feats", "corpus_ww", "med_feats", "med_ww", "out"): ap.add_argument("--" + k)
    a = ap.parse_args()
    runs = load_corpus(a.corpus_feats, a.corpus_ww); print(f"{len(runs)} corpus runs, {sum(r['y'] for r in runs):.0f} correct", flush=True)
    probes = [train_probe(runs, s) for s in (0, 1, 2)]
    for _, info in probes: print("probe", json.dumps(info), flush=True)
    prior = float(np.mean([i["first_step_prior"] for _, i in probes]))
    P = ME.build(a.med_feats, a.med_ww, "pooled")
    man = {m["run_id"]: m for m in json.load(open(os.path.join(a.med_ww, "manifest.json")))}
    S = {"drop": {}, "neg_v": {}}
    for k, d in P.items():
        rows = [i + 1 for i, f in enumerate(man[k]["is_llm"]) if f]
        with torch.no_grad():
            v = np.mean([torch.sigmoid(h(d["xf"][rows]).squeeze(-1)).numpy() for h, _ in probes], 0)
        prev = np.r_[prior, v[:-1]]; pos = {r: j for j, r in enumerate(rows)}; idx = [pos[int(r)] for r in d["rows"]]
        S["drop"][k] = (prev - v)[idx].astype(float); S["neg_v"][k] = (-v)[idx].astype(float)
    base = {nm: {k: f(d).astype(float) for k, d in P.items()} for nm, f in
            (("longest", lambda d: d["ntok"]), ("earliest", lambda d: -d["rel"]))}
    res = {"probe": [i for _, i in probes], "prior": prior, "scores": {}}
    valid = min(i["holdout_last_step_auroc"] for _, i in probes) >= 0.60
    for name, sc in list(S.items()) + [(f"baseline_{k}", v) for k, v in base.items()]:
        M = ME.metrics(sc, P); keys = sorted(P)
        r = {"pooled": summarise(M, P, keys),
             "seen": summarise(M, P, [k for k in keys if P[k]["unit"] in ME.SEEN]),
             "unseen": summarise(M, P, [k for k in keys if P[k]["unit"] not in ME.SEEN]),
             "per_unit": {u: summarise(M, P, [k for k in keys if P[k]["unit"] == u]) for u in sorted({P[k]["unit"] for k in keys})}}
        r["gate"] = gate(r["pooled"]) if valid else "UNINFORMATIVE (probe invalid)"
        res["scores"][name] = r
        for st in ("pooled", "seen", "unseen"):
            s = r[st]; ci = s["resid_boot"]["ci95_auroc"]
            print(f"{name:18s} {st:7s} n={s['n']:3d} raw {s['raw']:.3f} resid {s['resid']:.3f} [{ci[0]:.3f}, {ci[1]:.3f}] "
                  f"grid>0.5 {s['grid_above_half']}/6" + (f"  -> GATE {r['gate']}" if st == "pooled" else ""), flush=True)
    res["probe_valid"] = valid; json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
