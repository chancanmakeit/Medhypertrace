"""C5: self-supervised pretraining of the HGFM v0.2 encoder on MedAgentAudit (round 41).
MedAgentAudit taxonomy only (§0.33). See docs/design/HGFM_design_v0.2.md, C5.

Pretext objectives (no labels of any kind):
  rec   GraphMAE-style masked feature reconstruction: for a random 30% of step nodes the step-output
        embedding is replaced by a learned mask token, and the encoder state must reconstruct it
        (scaled cosine error, gamma=2).
  ans   answer-flow prediction on the same masked nodes: the answer scalars of a masked node
        (has_answer, answer==final, answer==round majority, agree) are zeroed as well and predicted
        from context. Without masking these scalars the target would be visible (leak).
  fill  HypeBoy-style read-hyperedge filling, only on `matched` sources (inferred from logged
        llm_input) and only for (framework x phase) keys whose most common source pattern covers
        < 90% of steps (protocol sources and near-deterministic patterns are solvable from the
        phase name alone; data profile in RUN_v0.40). For a target step its whole read hyperedge is
        removed (the edge instruction names the number and phases of its sources), and it scores
        earlier steps of the same run; candidates are restricted to earlier steps whose phase occurs
        among the true sources, so the phase alone cannot solve it.

Settings per fold (LQD = leave-one-MAS-out and question-disjoint; folds from splits_maa.py):
  strict   pretraining runs = the fold's supervised training runs (MAS != held-out, questions in A)
  trans    pretraining runs = all runs of all MAS incl. the held-out one, both question halves
           (transductive: unlabeled test-MAS runs are seen; reported separately, never pooled with strict)
  shuffle  as strict, but read-hyperedge tails replaced by random earlier steps (degree matched):
           pretraining compute without the true structure
Then the same supervised fine-tuning as train_v02.train (auditor labels + outcome, 5 epochs) from the
pretrained encoder; `scratch` = no pretraining. All share the fine-tuning seed.
Label-free scores (no fine-tuning): masked reconstruction error and answer-flow surprise of each step.

Usage: python -m hgfm.ssl_v02 <mas_traj.jsonl> <emb_dir> <human400.jsonl> <anchor_overlap.json> <out_dir>
          [settings=scratch,strict,shuffle,trans] [folds=all|LQD:colacare,...] [pre_epochs=3] [seeds=0]
"""
import json, sys, os, time, pickle, collections, random, copy
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F
from hgfm.data_maa import CODES
from hgfm.data_v02 import SLOTS, S2I, N_PAIR
from hgfm.model_v02 import HGFMv02
from hgfm.train_maa import load, auc, ALLC
from hgfm.train_v02 import attach_edges, collate, predict, human_scores
from hgfm.splits_maa import folds as make_folds

torch.set_num_threads(2)
ANS = slice(768, 772)          # has_answer, answer==final, answer==round-majority, agree  (data_maa.Featuriser)
HEAD, TAIL_M = S2I["read_head"], S2I["read_tail_matched"]
TAIL_SLOTS = {S2I[s] for s in SLOTS if s.startswith("read_tail")}
ENC_PREFIX = ("inp.", "rel.", "layers.")


# ---------------------------------------------------------------- read-edge bookkeeping
def read_edges(g):
    """{head node: (edge index, [matched tails], [all tails])} for the run's read hyperedges."""
    heads, tails = {}, collections.defaultdict(list); out = {}
    for e, v, s in g["e_inc"]:
        if s == HEAD: heads[e] = v
        elif s in TAIL_SLOTS: tails[e].append((v, s))
    for e, h in heads.items():
        out[h] = (e, [v for v, s in tails[e] if s == TAIL_M], [v for v, _ in tails[e]])
    return out


def fill_keys(G, thr=0.9):
    """(mas, phase) keys whose matched-source pattern is not near-deterministic, measured on G."""
    pat = collections.defaultdict(collections.Counter)
    for g in G:
        for h, (_, m, _) in read_edges(g).items():
            if m: pat[(g["mas"], g["steps"][h][1])][tuple(sorted((g["steps"][j][1], h - j) for j in m))] += 1
    return {k for k, c in pat.items() if c.most_common(1)[0][1] / sum(c.values()) < thr}, pat


def shuffled(g, rng):
    """Degree-matched control: every read tail moved to a uniformly random earlier step (slot kept)."""
    g = dict(g); heads = {e: v for e, v, s in g["e_inc"] if s == HEAD}; inc = []
    for e, v, s in g["e_inc"]:
        if s in TAIL_SLOTS and e in heads and heads[e] > 0: v = int(rng.integers(0, heads[e]))
        inc.append((e, v, s))
    g["e_inc"] = inc; return g


# ---------------------------------------------------------------- pretext model
class SSL(nn.Module):
    def __init__(self, enc, d=192):
        super().__init__()
        self.enc = enc
        self.mask_tok = nn.Parameter(torch.zeros(384)); nn.init.normal_(self.mask_tok, 0, 0.02)
        self.rec = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, 384))
        self.ans = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, 4))
        self.fq, self.fk = nn.Linear(d, d), nn.Linear(d, d)

    def states(self, B, mask):
        X = B["X"].clone(); X[mask, :384] = self.mask_tok; X[mask, ANS] = 0
        B = dict(B); B["X"] = X; self.enc(B); return self.enc._h


def batch_targets(gs, rng, keys, p_mask=0.3, p_fill=0.3, drop_fill=True):
    """Chooses masked nodes and fill targets; returns graphs with the fill targets' read edges removed."""
    out, mask, fills, vo = [], [], [], 0
    for g in gs:
        n = g["X"].shape[0]; RE = read_edges(g); drop = set()
        mask += [vo + i for i in range(n) if rng.random() < p_mask]
        for h, (e, m, _) in RE.items():
            if m and (g["mas"], g["steps"][h][1]) in keys and rng.random() < p_fill:
                ph = {g["steps"][j][1] for j in m}
                cand = [j for j in range(h) if g["steps"][j][1] in ph]
                if len(cand) > len(m):                      # otherwise nothing to discriminate
                    fills.append((vo + h, [vo + j for j in cand], [float(j in m) for j in cand])); drop.add(e)
        if drop and drop_fill:
            g = dict(g); g["e_inc"] = [x for x in g["e_inc"] if x[0] not in drop]
        out.append(g); vo += n
    return out, torch.tensor(mask, dtype=torch.long), fills


def ssl_losses(model, gs, rng, keys):
    gs2, mask, fills = batch_targets(gs, rng, keys)
    B = collate(gs2); h = model.states(B, mask); L = {}
    if len(mask):
        tgt = B["X"][mask, :384]; rec = model.rec(h[mask])
        L["rec"] = ((1 - F.cosine_similarity(rec, tgt, dim=1)) ** 2).mean()
        a = B["X"][mask, ANS]; has = a[:, 0] > 0
        t = torch.stack([a[:, 0], a[:, 1], a[:, 2], (a[:, 3] > 0).float()], 1)
        w = torch.stack([torch.ones_like(a[:, 0]), has.float(), has.float(), (a[:, 3] != 0).float()], 1)
        L["ans"] = (F.binary_cross_entropy_with_logits(model.ans(h[mask]), t, reduction="none") * w).sum() / w.sum().clamp(min=1)
    if fills:
        q = model.fq(h); k = model.fk(h); ls = []
        for hd, cand, y in fills:
            s = (k[torch.tensor(cand)] @ q[hd]) / np.sqrt(q.shape[1])
            ls.append(F.binary_cross_entropy_with_logits(s, torch.tensor(y)))
        L["fill"] = torch.stack(ls).mean()
    return L


def pretrain(Gp, d_in, keys, epochs, seed, log):
    torch.manual_seed(seed); rng = np.random.default_rng(seed); random.seed(seed)
    model = SSL(HGFMv02(d_in, len(SLOTS), N_PAIR))
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    idx = list(range(len(Gp)))
    for ep in range(epochs):
        random.shuffle(idx); model.train(); acc = collections.defaultdict(list); t0 = time.time()
        for b in range(0, len(idx), 64):
            L = ssl_losses(model, [Gp[i] for i in idx[b:b + 64]], rng, keys)
            loss = sum(L.values()); opt.zero_grad(); loss.backward(); opt.step()
            for k, v in L.items(): acc[k].append(float(v.detach()))
        log(f"  pre ep{ep} " + " ".join(f"{k}={np.mean(v):.4f}" for k, v in acc.items()) + f" {time.time()-t0:.0f}s")
    return model


@torch.no_grad()
def fill_eval(model, G, keys, seed=1):
    """Pretext sanity on held-out runs: AUROC of fill scores vs a (phase_h, phase_j, offset) prior."""
    model.eval(); rng = np.random.default_rng(seed); ys, ss = [], []
    for b in range(0, len(G), 64):
        gs2, _, fills = batch_targets(G[b:b + 64], rng, keys, p_mask=0, p_fill=1.0)
        if not fills: continue
        B = collate(gs2); h = model.states(B, torch.zeros(0, dtype=torch.long)); q, k = model.fq(h), model.fk(h)
        for hd, cand, y in fills:
            ss += (k[torch.tensor(cand)] @ q[hd]).tolist(); ys += y
    return auc(ys, ss), len(ys)


def prior_fill(Gtr, Gte, keys):
    cnt = collections.defaultdict(lambda: [0, 0]); rng = np.random.default_rng(1)
    def walk(G, fn):
        for g in G:
            for h, (e, m, _) in read_edges(g).items():
                if m and (g["mas"], g["steps"][h][1]) in keys:
                    ph = {g["steps"][j][1] for j in m}; cand = [j for j in range(h) if g["steps"][j][1] in ph]
                    if len(cand) > len(m):
                        for j in cand: fn((g["steps"][h][1], g["steps"][j][1], h - j), float(j in m))
    def add(k, y): cnt[k][0] += y; cnt[k][1] += 1
    walk(Gtr, add); ys, ss = [], []
    def sc(k, y): ys.append(y); ss.append(cnt[k][0] / cnt[k][1] if cnt[k][1] else 0.5)
    walk(Gte, sc); return auc(ys, ss), len(ys)


# ---------------------------------------------------------------- fine-tuning (= train_v02.train + init)
def finetune(G, init, epochs=5, seed=0):
    torch.manual_seed(seed); random.seed(seed)
    m = HGFMv02(G[0]["X"].shape[1], len(SLOTS), N_PAIR)
    if init is not None:
        sd = {k[4:]: v for k, v in init.state_dict().items() if k.startswith("enc.") and k[4:].startswith(ENC_PREFIX)}
        res = m.load_state_dict(sd, strict=False)
        # every encoder tensor must be loaded; only the fresh output heads may be missing
        assert sd and not res.unexpected_keys and all(k.startswith(("step_head.", "run_head.")) for k in res.missing_keys), res
    Y = np.concatenate([g["Y"] for g in G]); pos = np.nanmean(Y, 0)
    pw = torch.tensor(np.clip((1 - pos) / np.maximum(pos, 1e-3), 1, 20), dtype=torch.float32)
    idx = list(range(len(G))); random.shuffle(idx); batches = [collate([G[i] for i in idx[b:b + 64]]) for b in range(0, len(idx), 64)]
    opt = torch.optim.AdamW(m.parameters(), lr=1e-3, weight_decay=1e-4)
    for _ in range(epochs):
        m.train(); random.shuffle(batches)
        for B in batches:
            sl, rl = m(B); mk = ~torch.isnan(B["Y"])
            ls = (F.binary_cross_entropy_with_logits(sl, torch.nan_to_num(B["Y"]), pos_weight=pw, reduction="none") * mk).sum() / mk.sum().clamp(min=1)
            ry = B["run_y"]; rm = ~torch.isnan(ry)
            lr_ = (F.binary_cross_entropy_with_logits(rl, torch.nan_to_num(ry), reduction="none") * rm).sum() / rm.sum().clamp(min=1)
            loss = ls + 0.5 * lr_; opt.zero_grad(); loss.backward(); opt.step()
    return m


@torch.no_grad()
def label_free(model, G):
    """Per run: [n, 2] = (reconstruction error, answer-flow surprise) of each step when it alone is masked."""
    model.eval(); out = []
    for b in range(0, len(G), 64):
        gs = G[b:b + 64]; B = collate(gs); n = [g["X"].shape[0] for g in gs]; off = np.cumsum([0] + n[:-1])
        S = [np.full((k, 2), np.nan, np.float32) for k in n]
        for pos in range(max(n)):
            rows = [o + pos for o, k in zip(off, n) if pos < k]; mask = torch.tensor(rows, dtype=torch.long)
            h = model.states(B, mask)[mask]
            rec = 1 - F.cosine_similarity(model.rec(h), B["X"][mask, :384], dim=1)
            a = B["X"][mask, ANS]; has = a[:, 0] > 0
            t = torch.stack([a[:, 0], a[:, 1], a[:, 2], (a[:, 3] > 0).float()], 1)
            w = torch.stack([torch.ones_like(a[:, 0]), has.float(), has.float(), (a[:, 3] != 0).float()], 1)
            sur = (F.binary_cross_entropy_with_logits(model.ans(h), t, reduction="none") * w).sum(1)
            r = 0
            for k_, (o, k) in enumerate(zip(off, n)):
                if pos < k: S[k_][pos] = (float(rec[r]), float(sur[r])); r += 1
        out += S
    return out


def label_free_human(H, te, S, name, j):
    ids = {g["run_id"]: k for k, g in enumerate(te)}; hs = []
    for h in H:
        if h["run_id"] not in ids or h["mas"] != name.split(":")[1]: continue
        g, s = te[ids[h["run_id"]]], S[ids[h["run_id"]]]
        if h["code"] == "2.1.1": sc = float(np.nanmax(s[:, j]))
        else:
            rows = [i for i, (a, ph) in enumerate(g["steps"]) if a == h["agent_id"] and ph == h["phase"]]
            sc = float(max(s[i, j] for i in rows)) if rows else float("nan")
        hs.append({**{k: h[k] for k in ("run_id", "code", "human", "auditor", "mas")}, "score": sc})
    return hs


# ---------------------------------------------------------------- summary
def macro(hs):
    return float(np.nanmean([auc([h["human"] for h in hs if h["code"] == c], [h["score"] for h in hs if h["code"] == c]) for c in ALLC]))


def summarise(P, ref="scratch", n_boot=1000):
    """P[(variant, seed)] = aligned human instances (same order across variants). Seed-averaged scores per instance."""
    by = collections.defaultdict(list)
    for (v, s), hs in P.items(): by[v].append(hs)
    avg = {}
    for v, runs in by.items():
        base = runs[0]
        for r in runs: assert [(h["run_id"], h["code"]) for h in r] == [(h["run_id"], h["code"]) for h in base]
        avg[v] = [{**h, "score": float(np.nanmean([r[i]["score"] for r in runs]))} for i, h in enumerate(base)]
    keep = [i for i in range(len(avg[ref])) if all(not np.isnan(avg[v][i]["score"]) for v in avg)]
    rng = np.random.default_rng(0); B = [rng.integers(0, len(keep), len(keep)) for _ in range(n_boot)]
    out = {}
    for v, hs in avg.items():
        hs = [hs[i] for i in keep]; r = [avg[ref][i] for i in keep]
        boot = [macro([hs[i] for i in b]) for b in B]; d = [macro([hs[i] for i in b]) - macro([r[i] for i in b]) for b in B]
        out[v] = {"n": len(hs), "n_seeds": len(by[v]), "macro_auroc": macro(hs), "ci95": [float(np.nanpercentile(boot, 2.5)), float(np.nanpercentile(boot, 97.5))],
                  f"diff_vs_{ref}": macro(hs) - macro(r), "diff_ci95": [float(np.nanpercentile(d, 2.5)), float(np.nanpercentile(d, 97.5))],
                  "per_code": {c: auc([h["human"] for h in hs if h["code"] == c], [h["score"] for h in hs if h["code"] == c]) for c in ALLC}}
    return out


def main(src, emb, human, overlap, out, settings="scratch,strict,shuffle,trans", fold_sel="all", pre_epochs="3", seeds="0"):
    os.makedirs(out, exist_ok=True); logf = open(f"{out}/log.txt", "a")
    def log(s): print(s, flush=True); logf.write(s + "\n"); logf.flush()
    settings = settings.split(","); pre_epochs = int(pre_epochs); seeds = [int(s) for s in seeds.split(",")]
    H = [json.loads(l) for l in open(human)]; hq = {h["run_id"].split("|")[3] + "/" + h["qid"] for h in H}
    G = attach_edges(load(src, emb, overlap, False), src, emb, overlap, False); d_in = G[0]["X"].shape[1]
    folds = [f for f in make_folds(G, hq, ("LQD",)) if fold_sel == "all" or f[0] in fold_sel.split(",")]
    P = collections.defaultdict(list); LF = collections.defaultdict(list); info = {}
    ppath = f"{out}/preds.pkl"
    if os.path.exists(ppath): P, LF, info = (lambda d: (collections.defaultdict(list, d["P"]), collections.defaultdict(list, d["LF"]), d["info"]))(pickle.load(open(ppath, "rb")))
    for name, tr, te in folds:
        mas = name.split(":")[1]
        for seed in seeds:
            for st in settings:
                key = f"{name}|{st}|{seed}"
                if key in info: log(f"skip {key}"); continue
                t0 = time.time(); fi = {}
                if st == "scratch": pre = None
                else:
                    Gp = tr if st in ("strict", "shuffle") else G
                    if st == "shuffle":
                        rng = np.random.default_rng(seed); Gp = [shuffled(g, rng) for g in Gp]
                    keys, _ = fill_keys(Gp)
                    log(f"{key}: pretrain on {len(Gp)} runs, fill keys {sorted(keys)}")
                    pre = pretrain(Gp, d_in, keys, pre_epochs, seed, log)
                    # pretext sanity on the held-out MAS runs (true graphs), vs the phase/offset prior
                    tk, _ = fill_keys(te)
                    fi["fill_auc_test"], fi["n_fill_test"] = fill_eval(pre, te, tk)
                    fi["fill_prior_test"], _ = prior_fill(Gp, te, tk)
                    S = label_free(pre, te)
                    for j, nm in enumerate(("lf_rec", "lf_ans")): LF[(st, nm, seed)] += label_free_human(H, te, S, name, j)
                m = finetune(tr, pre, seed=seed); Pr = predict(m, te)
                P[(st, seed)] += human_scores(H, te, Pr, name, tr)
                fi.update({"outcome": auc([g["wrong"] for g in te], [p[1][0] for p in Pr]), "sec": round(time.time() - t0)})
                info[key] = fi; log(f"{key} " + " ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}" for k, v in fi.items()))
                pickle.dump({"P": dict(P), "LF": dict(LF), "info": info}, open(ppath, "wb"))
    res = {"info": info, "finetuned": summarise(P) if "scratch" in settings else {}}
    lfs = {}
    for (st, nm, seed), hs in LF.items():
        hs = [h for h in hs if not np.isnan(h["score"])]; lfs[f"{st}|{nm}|{seed}"] = {"n": len(hs), "macro_auroc": macro(hs)}
    res["label_free"] = lfs
    json.dump(res, open(f"{out}/results.json", "w"), indent=1, default=float)
    for v, r in res["finetuned"].items():
        log(f"HUMAN LQD {v:8s} n={r['n']} seeds={r['n_seeds']} macro={r['macro_auroc']:.3f} [{r['ci95'][0]:.3f},{r['ci95'][1]:.3f}]  diff vs scratch={r['diff_vs_scratch']:+.3f} [{r['diff_ci95'][0]:+.3f},{r['diff_ci95'][1]:+.3f}]")
    for k, r in lfs.items(): log(f"LABEL-FREE {k} n={r['n']} macro={r['macro_auroc']:.3f}")


if __name__ == "__main__":
    main(*sys.argv[1:10])
