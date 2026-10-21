"""HGFM v0.2 (C1-C4) on MedAgentAudit, same protocol as train_maa.py (round 35).

Variants (gold=False unless noted): full, no_pos (C1 off), no_instr (C3 off, gamma=0),
no_rel (C2 off), no_qattn (C4 off: mean aggregation, query only concatenated);
full with gold=True. Folds: LQD (6, leave-one-MAS-out AND question-disjoint, see splits_maa.py) + QD. Metrics and references as in train_maa.py.
Usage: python -m hgfm.train_v02 <mas_traj.jsonl> <emb_dir> <human400.jsonl> <anchor_overlap.json> <out_dir> [variants]
"""
import json, sys, os, time, pickle, collections, random
import numpy as np, torch
from hgfm.data_maa import CODES
from hgfm.data_v02 import edges_of, relation_graph, TextEmb, SLOTS, N_PAIR
from hgfm.model_v02 import HGFMv02
from hgfm.train_maa import load, auc, ALLC
from hgfm.splits_maa import folds as make_folds

torch.set_num_threads(2)
VARIANTS = {"full": {}, "no_pos": {"use_pos": False}, "no_instr": {"use_instr": False},
            "no_rel": {"use_rel": False}, "no_qattn": {"query_attn": False}}


def attach_edges(G, src, emb_dir, overlap, gold):
    cache = f"{emb_dir}/graphs_v02_gold{int(gold)}.pkl"
    if os.path.exists(cache): return pickle.load(open(cache, "rb"))
    by = {g["run_id"]: g for g in G}; T = TextEmb(); fw_desc = {}
    for l in open(src):
        r = json.loads(l)
        g = by.get(r["run_id"])
        if g is None: continue
        E = edges_of(r); rels, links = relation_graph(E); ri = {k: i for i, k in enumerate(rels)}
        rel_text = {e["rel_key"]: e["rel_text"] for e in E}
        g["e_inc"] = [(k, v, s) for k, e in enumerate(E) for v, s in e["members"]]
        g["e_rel"] = [ri[e["rel_key"]] for e in E]
        g["e_instr"] = T([e["instr"] for e in E])
        g["r_txt"] = T([rel_text[k] for k in rels])
        g["r_links"] = links
        g["q"] = g["q"] + 0.5 * T([r["framework_description"]])[0]   # IHP-style task description in the query
    pickle.dump(G, open(cache, "wb")); return G


def collate(gs):
    X, NR, Y, last, nn_, inc_e, inc_v, inc_s, e_rel, e_run, e_instr, r_txt, r_run, rg_s, rg_d, rg_p = ([] for _ in range(16))
    vo = eo = ro = 0
    for k, g in enumerate(gs):
        n = g["X"].shape[0]; X.append(torch.from_numpy(g["X"])); Y.append(torch.from_numpy(g["Y"]))
        NR += [k] * n; last.append(vo + n - 1); nn_.append(n)
        ne = len(g["e_rel"]); nr = g["r_txt"].shape[0]
        for e, v, s in g["e_inc"]: inc_e.append(eo + e); inc_v.append(vo + v); inc_s.append(s)
        e_rel += [ro + x for x in g["e_rel"]]; e_run += [k] * ne; e_instr.append(torch.from_numpy(g["e_instr"]).reshape(-1, 384))
        r_txt.append(torch.from_numpy(g["r_txt"]).reshape(-1, 384)); r_run += [k] * nr
        for a, b, p in g["r_links"]: rg_s.append(ro + a); rg_d.append(ro + b); rg_p.append(p)
        vo += n; eo += ne; ro += nr
    L = lambda x: torch.tensor(x, dtype=torch.long)
    return {"X": torch.cat(X), "Y": torch.cat(Y), "node_run": L(NR), "last": L(last), "n_nodes": torch.tensor(nn_, dtype=torch.float32),
            "q": torch.from_numpy(np.stack([g["q"] for g in gs])), "run_y": torch.tensor([[g["wrong"], g["y211"]] for g in gs], dtype=torch.float32),
            "inc_e": L(inc_e), "inc_v": L(inc_v), "inc_s": L(inc_s), "n_edges": eo, "edge_rel": L(e_rel), "edge_run": L(e_run),
            "edge_instr": torch.cat(e_instr) if e_instr else torch.zeros(0, 384), "rel_txt": torch.cat(r_txt), "rel_run": L(r_run),
            "rg_src": L(rg_s), "rg_dst": L(rg_d), "rg_pair": L(rg_p)}


def train(G, kw, epochs=5, seed=0):
    torch.manual_seed(seed); random.seed(seed)
    m = HGFMv02(G[0]["X"].shape[1], len(SLOTS), N_PAIR, **kw)
    Y = np.concatenate([g["Y"] for g in G]); pos = np.nanmean(Y, 0); pw = torch.tensor(np.clip((1 - pos) / np.maximum(pos, 1e-3), 1, 20), dtype=torch.float32)
    idx = list(range(len(G))); random.shuffle(idx); batches = [collate([G[i] for i in idx[b:b + 64]]) for b in range(0, len(idx), 64)]
    opt = torch.optim.AdamW(m.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(epochs):
        m.train(); random.shuffle(batches)
        for B in batches:
            sl, rl = m(B); mask = ~torch.isnan(B["Y"])
            ls = (torch.nn.functional.binary_cross_entropy_with_logits(sl, torch.nan_to_num(B["Y"]), pos_weight=pw, reduction="none") * mask).sum() / mask.sum().clamp(min=1)
            ry = B["run_y"]; rm = ~torch.isnan(ry)
            lr_ = (torch.nn.functional.binary_cross_entropy_with_logits(rl, torch.nan_to_num(ry), reduction="none") * rm).sum() / rm.sum().clamp(min=1)
            loss = ls + 0.5 * lr_; opt.zero_grad(); loss.backward(); opt.step()
    return m


@torch.no_grad()
def predict(m, G):
    m.eval(); out = []
    for b in range(0, len(G), 128):
        gs = G[b:b + 128]; B = collate(gs); sl, rl = m(B); sl = torch.sigmoid(sl).numpy(); rl = torch.sigmoid(rl).numpy(); off = 0
        for k, g in enumerate(gs):
            n = g["X"].shape[0]; out.append((sl[off:off + n], rl[k])); off += n
    return out


def human_scores(H, te, P, name, tr):
    ids = {g["run_id"]: k for k, g in enumerate(te)}; hs = []
    for h in H:
        if h["run_id"] not in ids or (name[:4] in ("LOMO", "LQD:") and h["mas"] != name.split(":")[1]): continue
        g, p = te[ids[h["run_id"]]], P[ids[h["run_id"]]]
        if h["code"] == "2.1.1": sc = float(p[1][1])
        else:
            j = CODES.index(h["code"]); rows = [i for i, (a, ph) in enumerate(g["steps"]) if a == h["agent_id"] and ph == h["phase"]]
            sc = float(max(p[0][i, j] for i in rows)) if rows else float("nan")
        hs.append({**{k: h[k] for k in ("run_id", "code", "human", "auditor", "mas")}, "score": sc})
    return hs


def main(src, emb, human, overlap, out, variants="full,no_pos,no_instr,no_rel,no_qattn,full_gold"):
    os.makedirs(out, exist_ok=True)
    H = [json.loads(l) for l in open(human)]; hq = {h["run_id"].split("|")[3] + "/" + h["qid"] for h in H}
    res, preds_h = {}, collections.defaultdict(list)
    for v in variants.split(","):
        gold = v.endswith("_gold"); kw = VARIANTS[v.replace("_gold", "")]
        G = attach_edges(load(src, emb, overlap, gold), src, emb, overlap, gold)
        folds = make_folds(G, hq, ("LQD", "QD"))
        for name, tr, te in folds:
            t0 = time.time(); m = train(tr, kw); P = predict(m, te)
            Y = np.concatenate([g["Y"] for g in te]); S = np.concatenate([p[0] for p in P])
            weak = {c: auc(Y[~np.isnan(Y[:, j]), j], S[~np.isnan(Y[:, j]), j]) for j, c in enumerate(CODES)}
            outcome = auc([g["wrong"] for g in te], [p[1][0] for p in P])
            hs = human_scores(H, te, P, name, tr); preds_h[(v, name.split(":")[0])] += hs
            res[f"{v}_{name}"] = {"weak": weak, "outcome": outcome, "n_human": len(hs)}
            print(f"{v}_{name} outcome={outcome:.3f} weak-macro={np.nanmean(list(weak.values())):.3f} human={len(hs)} {time.time()-t0:.0f}s", flush=True)
    pickle.dump(dict(preds_h), open(f"{out}/human_preds.pkl", "wb")); json.dump(res, open(f"{out}/folds.json", "w"), indent=1, default=float)
    summ = {}; rng = np.random.default_rng(0)
    for (v, split), hs in preds_h.items():
        hs = [h for h in hs if not np.isnan(h["score"])]
        per = {c: auc([h["human"] for h in hs if h["code"] == c], [h["score"] for h in hs if h["code"] == c]) for c in ALLC}
        boots = [np.nanmean([auc([h["human"] for h in b if h["code"] == c], [h["score"] for h in b if h["code"] == c]) for c in ALLC])
                 for b in ([hs[i] for i in rng.integers(0, len(hs), len(hs))] for _ in range(500))]
        summ[f"{v}_{split}"] = {"n": len(hs), "macro_auroc": float(np.nanmean(list(per.values()))), "ci95": [float(np.nanpercentile(boots, 2.5)), float(np.nanpercentile(boots, 97.5))], "per_code": per}
        print(f"HUMAN {split:4s} {v:10s} n={len(hs)} macro AUROC={summ[f'{v}_{split}']['macro_auroc']:.3f} [{summ[f'{v}_{split}']['ci95'][0]:.3f},{summ[f'{v}_{split}']['ci95'][1]:.3f}]", flush=True)
    json.dump({"folds": res, "human": summ}, open(f"{out}/results.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main(*sys.argv[1:7])
