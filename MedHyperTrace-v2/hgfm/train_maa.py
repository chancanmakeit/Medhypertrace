"""HGFM v0 phase-1 experiment on MedAgentAudit (round 33). MedAgentAudit taxonomy only.

Data: converted runs (data_tools/maa_to_mas_traj.py), minus mdagents 'basic' runs and minus
runs whose question overlaps the medical-aegis anchor set. Weak supervision = LLM-auditor
labels; evaluation truth = 400 human instances (majority of 3), never trained on.
Splits:
  LOMO  leave-one-MAS-out (6 folds): train on 5 MAS, test on the held-out MAS.
  QD    question-disjoint in-distribution: test = runs of the human-eval questions,
        train = all runs whose question is not a human-eval question.
Variants: layers in {0 (no structure), 2 (HGFM v0)} x gold in {False, True}.
Metrics:
  human   per-code AUROC vs human majority on the 400 instances (instance score = max
          over steps matching target agent_id+phase; 2.1.1 from the run head), macro + CI
  weak    per-code AUROC vs auditor labels on held-out steps
  outcome AUROC of P(final wrong) on held-out runs (no-gold variants only)
References on the 400: the auditor's own label (sees ground truth), and a prior
(training-set positive rate of (phase, code)).
Usage: python -m hgfm.train_maa <mas_traj.jsonl> <emb_dir> <human400.jsonl> <anchor_overlap.json> <out_dir>
"""
import json, sys, os, time, pickle, collections, random
import numpy as np, torch
from sklearn.metrics import roc_auc_score
from hgfm.data_maa import Featuriser, CODES
from hgfm.model_v0 import HGFMv0, collate

torch.set_num_threads(2)
ALLC = CODES + ["2.1.1"]


def load(src, emb, overlap, gold):
    cache = f"{emb}/graphs_gold{int(gold)}.pkl"
    if os.path.exists(cache): return pickle.load(open(cache, "rb"))
    F = Featuriser(emb); ov = set(json.load(open(overlap))); G = []
    for l in open(src):
        r = json.loads(l)
        if r["labels"].get("complexity_level") == "basic": continue
        if r["question_id"].split("/", 1)[1] in ov: continue
        g = F.run(r, gold=gold)
        if g: G.append(g)
    pickle.dump(G, open(cache, "wb")); return G


def train(G, layers, epochs=5, seed=0, d_in=None):
    torch.manual_seed(seed); random.seed(seed)
    m = HGFMv0(d_in, layers=layers)
    idx = list(range(len(G))); random.shuffle(idx)
    batches = [collate([G[i] for i in idx[b:b + 64]]) for b in range(0, len(idx), 64)]  # collate once
    Y = np.concatenate([g["Y"] for g in G]); pos = np.nanmean(Y, 0); pw = torch.tensor(np.clip((1 - pos) / np.maximum(pos, 1e-3), 1, 20), dtype=torch.float32)
    opt = torch.optim.AdamW(m.parameters(), lr=1e-3, weight_decay=1e-4)
    for ep in range(epochs):
        m.train(); random.shuffle(batches)
        for B in batches:
            sl, rl = m(B)
            mask = ~torch.isnan(B["Y"]); yt = torch.nan_to_num(B["Y"])
            ls = (torch.nn.functional.binary_cross_entropy_with_logits(sl, yt, pos_weight=pw, reduction="none") * mask).sum() / mask.sum().clamp(min=1)
            ry = B["run_y"]; rm = ~torch.isnan(ry)
            lr_ = (torch.nn.functional.binary_cross_entropy_with_logits(rl, torch.nan_to_num(ry), reduction="none") * rm).sum() / rm.sum().clamp(min=1)
            loss = ls + 0.5 * lr_
            opt.zero_grad(); loss.backward(); opt.step()
    return m


@torch.no_grad()
def predict(m, G):
    m.eval(); out = []
    for b in range(0, len(G), 128):
        gs = G[b:b + 128]; B = collate(gs); sl, rl = m(B); sl = torch.sigmoid(sl).numpy(); rl = torch.sigmoid(rl).numpy()
        off = 0
        for k, g in enumerate(gs):
            n = g["X"].shape[0]; out.append((sl[off:off + n], rl[k])); off += n
    return out


def auc(y, s):
    y, s = np.asarray(y), np.asarray(s)
    return roc_auc_score(y, s) if len(set(y)) == 2 else float("nan")


def main(src, emb, human, overlap, out):
    os.makedirs(out, exist_ok=True)
    H = [json.loads(l) for l in open(human)]
    hq = {h["run_id"].split("|")[3] + "/" + h["qid"] for h in H}
    results = {}; preds_h = collections.defaultdict(list)
    for gold in (False, True):
        G = load(src, emb, overlap, gold); d_in = G[0]["X"].shape[1]
        by = {g["run_id"]: g for g in G}
        folds = [("LOMO:" + m_, [g for g in G if g["mas"] != m_], [g for g in G if g["mas"] == m_]) for m_ in sorted({g["mas"] for g in G})]
        folds.append(("QD", [g for g in G if g["qid"] not in hq], [g for g in G if g["qid"] in hq]))
        for layers in (0, 2):
            for name, tr, te in folds:
                t0 = time.time(); m = train(tr, layers, d_in=d_in); P = predict(m, te); te_ids = {g["run_id"]: k for k, g in enumerate(te)}
                key = f"gold{int(gold)}_L{layers}_{name}"
                # weak-label AUROC on held-out steps
                Y = np.concatenate([g["Y"] for g in te]); S = np.concatenate([p[0] for p in P])
                weak = {c: auc(Y[~np.isnan(Y[:, j]), j], S[~np.isnan(Y[:, j]), j]) for j, c in enumerate(CODES)}
                outcome = auc([g["wrong"] for g in te], [p[1][0] for p in P])
                # prior from training set: rate of (phase, code)
                prior = collections.defaultdict(list)
                for g in tr:
                    for i, (a, ph) in enumerate(g["steps"]):
                        for j, c in enumerate(CODES):
                            if not np.isnan(g["Y"][i, j]): prior[(ph, c)].append(g["Y"][i, j])
                # human instances in this fold's test runs
                hs = []
                for h in H:
                    if h["run_id"] not in te_ids: continue
                    if name.startswith("LOMO") and h["mas"] != name[5:]: continue
                    g = te[te_ids[h["run_id"]]]; p = P[te_ids[h["run_id"]]]
                    if h["code"] == "2.1.1": sc = float(p[1][1]); pr = np.nanmean([x["y211"] for x in tr])
                    else:
                        j = CODES.index(h["code"]); rows = [i for i, (a, ph) in enumerate(g["steps"]) if a == h["agent_id"] and ph == h["phase"]]
                        sc = float(max(p[0][i, j] for i in rows)) if rows else float("nan"); pr = float(np.mean(prior.get((h["phase"], h["code"]), [np.nan])))
                    hs.append({**{k: h[k] for k in ("run_id", "code", "human", "auditor", "mas")}, "score": sc, "prior": pr})
                preds_h[(gold, layers, name.split(":")[0])] += hs
                results[key] = {"weak": weak, "outcome": outcome, "n_train": len(tr), "n_test": len(te), "n_human": len(hs), "sec": round(time.time() - t0)}
                print(key, f"n_tr={len(tr)} n_te={len(te)} human={len(hs)} outcome={outcome:.3f} weak-macro={np.nanmean(list(weak.values())):.3f} {time.time()-t0:.0f}s", flush=True)
    # aggregate human-eval metrics
    summ = {}
    rng = np.random.default_rng(0)
    for (gold, layers, split), hs in preds_h.items():
        hs = [h for h in hs if not np.isnan(h["score"])]
        per = {c: auc([h["human"] for h in hs if h["code"] == c], [h["score"] for h in hs if h["code"] == c]) for c in ALLC}
        macro = np.nanmean(list(per.values()))
        boots = []
        for _ in range(500):
            b = [hs[i] for i in rng.integers(0, len(hs), len(hs))]
            boots.append(np.nanmean([auc([h["human"] for h in b if h["code"] == c], [h["score"] for h in b if h["code"] == c]) for c in ALLC]))
        ref_aud = np.nanmean([auc([h["human"] for h in hs if h["code"] == c], [h["auditor"] for h in hs if h["code"] == c]) for c in ALLC])
        ref_pri = np.nanmean([auc([h["human"] for h in hs if h["code"] == c], [h["prior"] for h in hs if h["code"] == c]) for c in ALLC])
        summ[f"gold{int(gold)}_L{layers}_{split}"] = {"n": len(hs), "macro_auroc": macro, "ci95": [float(np.nanpercentile(boots, 2.5)), float(np.nanpercentile(boots, 97.5))],
                                                     "per_code": per, "auditor_macro_auroc_same_instances": ref_aud, "prior_macro_auroc": ref_pri}
        print(f"HUMAN {split:4s} gold={int(gold)} L={layers}: n={len(hs)} macro AUROC={macro:.3f} [{np.nanpercentile(boots,2.5):.3f},{np.nanpercentile(boots,97.5):.3f}]  auditor={ref_aud:.3f} prior={ref_pri:.3f}", flush=True)
    json.dump({"folds": results, "human": summ}, open(f"{out}/results.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main(*sys.argv[1:6])
