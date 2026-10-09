"""
Train + evaluate MedHyperTrace (v2, with improvements A–G).

Flags (CLI or env):
  --features tfidf|emb     node text features: TF-IDF (local) or cached sentence
                           embeddings (build with common/embed_cache.py; improvement B).
                           --emb_model selects the cache: mxbai (384-d, default) | nomic
                           (768-d) | any tag you encoded. 'nomic' is accepted as an alias
                           for --features emb --emb_model nomic (back-compat).
  --struct 0|1             append 7 structural-prior dims to step nodes (improvement C)
  --backbone relation|standard   relation-aware conv vs plain HGNN+ (ablation, item 2)
  --prop W                 propagation-consistency loss weight (improvement D; 0=off)
  --margin W               step margin-ranking weight added to the listwise softmax
                           (improvement G; the base step loss was ALREADY listwise —
                           softmax CE over each trajectory's steps — so G adds a
                           hard-negative margin term rather than replacing anything)
  --joint / --holdout FW   joint training over all frameworks' train tasks; holdout
                           trains on the other two and tests on FW (improvement E)
Threshold calibration (improvement A): 10% of train tasks are held out as val; after
training, per-class decision thresholds are swept on val to maximize F1 and then
applied at test time (replaces the fixed 0.5).
Pair head (improvement F) lives in the model: pair_logit = agent_logit + mode_logit.
"""
import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)

import argparse
import json
import os
import random
from collections import defaultdict

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import f1_score

from common.data import load_jsonl, build_hypergraph, FM_TYPES, FM_INDEX
from common.paths import FILES, SPLITS_JSON
from common.structural_features import structural_features, N_STRUCT
from ours.hypergraph_model import MedHyperTrace, EDGE_TYPES, NODE_TYPES

def pick_device(device="auto"):
    """auto -> cuda when available, else cpu. Same code path on CPU sandbox and CUDA box."""
    if device == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device)


DEVICE = pick_device(os.environ.get("MHT_DEVICE", "auto"))

torch.manual_seed(0)
np.random.seed(0)
random.seed(0)

TFIDF_DIM = 512



def _fixed_split(name):
    d = json.load(open(SPLITS_JSON))[name]
    return set(d["train_task_ids"]), set(d["test_task_ids"])


# ---------------------------------------------------------------- features
class Featurizer:
    """Text features for nodes: 'tfidf' fits on train steps; 'nomic' reads the
    embedding cache (agent/phase vectors = mean of member steps)."""

    def __init__(self, mode, train_steps_text=None, emb_lookup=None):
        self.mode = mode
        if mode == "tfidf":
            self.dim = TFIDF_DIM
            self.tfidf = TfidfVectorizer(max_features=TFIDF_DIM, ngram_range=(1, 2),
                                         min_df=3, sublinear_tf=True)
            self.tfidf.fit(train_steps_text)
        elif mode == "emb":
            self.emb_lookup = emb_lookup  # (dict key->row, np.ndarray emb)
            self.dim = int(emb_lookup[1].shape[1])
        else:
            raise ValueError(mode)

    def steps(self, traj, acting):
        if self.mode == "tfidf":
            return self.tfidf.transform([s.content for s in acting]).toarray().astype(np.float32)
        idx, emb = self.emb_lookup
        from common.embed_cache import key_of
        rows = []
        for s in acting:
            k = key_of(traj.id, s)
            if k not in idx:
                raise KeyError(f"embedding cache missing key for {traj.id} turn {s.turn}; "
                               f"build the cache with common/embed_cache.py")
            rows.append(emb[idx[k]])
        return np.stack(rows).astype(np.float32)

    def agg_text(self, texts):
        """tfidf-mode only: vector for concatenated text."""
        return self.tfidf.transform(texts).toarray().astype(np.float32)


def build_sample(traj, fz: Featurizer, use_struct: bool, fact_provider=None):
    hg = build_hypergraph(traj)
    acting = [s for s in traj.steps if not s.is_input]
    step_by_id = {f"s{s.turn}": s for s in acting}
    inst_of = {f"a::{a}#{ri}": (a, ri) for (a, ri) in traj.instances}

    step_vec = fz.steps(traj, acting)                     # [ns, D]
    order = {f"s{s.turn}": i for i, s in enumerate(acting)}

    if fz.mode == "tfidf":
        agent_vec = fz.agg_text([" ".join(s.content for s in acting
                                          if s.instance == inst_of[a])
                                 for a in hg.agent_nodes]) if hg.agent_nodes else \
            np.zeros((0, fz.dim), np.float32)
        phase_vec = fz.agg_text([" ".join(s.content for s in acting
                                          if s.coarse == p[3:]) for p in hg.phase_nodes]) \
            if hg.phase_nodes else np.zeros((0, fz.dim), np.float32)
    else:  # emb: mean of member step vectors
        def mean_of(members):
            rows = [step_vec[order[m]] for m in members if m in order]
            return np.mean(rows, 0) if rows else np.zeros(fz.dim, np.float32)
        agent_vec = np.stack([mean_of([f"s{s.turn}" for s in acting
                                       if s.instance == inst_of[a]])
                              for a in hg.agent_nodes]).astype(np.float32) \
            if hg.agent_nodes else np.zeros((0, fz.dim), np.float32)
        phase_vec = np.stack([mean_of([f"s{s.turn}" for s in acting
                                       if s.coarse == p[3:]])
                              for p in hg.phase_nodes]).astype(np.float32) \
            if hg.phase_nodes else np.zeros((0, fz.dim), np.float32)

    if use_struct:
        # structural priors (7 dims), optionally + 1 factuality dim (S- tier).
        if fact_provider is not None:
            from common.structural_features import structural_features_with_factuality
            sf = structural_features_with_factuality(acting, fact_provider)  # [ns, 8]
        else:
            sf = structural_features(acting)                                 # [ns, 7]
        sdim = sf.shape[1]
        step_vec = np.concatenate([step_vec, sf], 1)
        agent_vec = np.concatenate([agent_vec,
                                    np.zeros((agent_vec.shape[0], sdim), np.float32)], 1)
        phase_vec = np.concatenate([phase_vec,
                                    np.zeros((phase_vec.shape[0], sdim), np.float32)], 1)

    eet = traj.labels.earliest_error_turn
    step_target = next((j for j, i in enumerate(hg.step_nodes)
                        if step_by_id[i].turn == eet), -1)
    agent_target = np.array([int(inst_of[a] in traj.labels.faulty_instances)
                             for a in hg.agent_nodes], np.float32)
    mode_target = np.zeros((len(hg.agent_nodes), len(FM_TYPES)), np.float32)
    for k, aid in enumerate(hg.agent_nodes):
        for fm in traj.labels.instance_fms.get(inst_of[aid], set()):
            if fm in FM_INDEX:
                mode_target[k, FM_INDEX[fm]] = 1.0

    # ctx propagation pairs: (consumer local step idx, [source local idxs])
    prop = []
    for e in hg.hyperedges:
        if e["type"] == "ctx":
            c = order.get(f"s{e['meta']['consumer']}")
            srcs = [order.get(f"s{t}") for t in e["meta"]["sources"]]
            srcs = [x for x in srcs if x is not None]
            if c is not None and srcs:
                prop.append((c, srcs))

    return {"n_step": len(hg.step_nodes), "n_agent": len(hg.agent_nodes),
            "n_phase": len(hg.phase_nodes),
            "step_ids": hg.step_nodes, "agent_ids": hg.agent_nodes,
            "phase_ids": hg.phase_nodes,
            "feats": {"step": step_vec, "agent": agent_vec, "phase": phase_vec},
            "hyperedges": hg.hyperedges, "prop": prop,
            "step_target": step_target, "agent_target": agent_target,
            "mode_target": mode_target}


# ---------------------------------------------------------------- batching
def collate(samples, feat_dim):
    order = ["step", "agent", "phase"]
    counts = {t: sum(s[f"n_{t}"] for s in samples) for t in order}
    off, slices, offsets = 0, {}, {}
    for t in order:
        slices[t] = slice(off, off + counts[t]); offsets[t] = off; off += counts[t]
    N = off
    feats = {t: np.zeros((counts[t], feat_dim), np.float32) for t in order}
    type_ids = np.zeros(N, np.int64)
    for ti, t in enumerate(order):
        type_ids[slices[t]] = ti

    incidence_cols = {r: [] for r in EDGE_TYPES}
    step_targets, step_group, prop_pairs = [], [], []
    agent_targets, mode_targets = [], []
    cur = {t: offsets[t] for t in order}
    for s in samples:
        for t in order:
            n = s[f"n_{t}"]
            feats[t][cur[t]-offsets[t]:cur[t]-offsets[t]+n] = s["feats"][t]
        gid = {}
        for j, sid in enumerate(s["step_ids"]): gid[sid] = cur["step"] + j
        for j, aid in enumerate(s["agent_ids"]): gid[aid] = cur["agent"] + j
        for j, pid in enumerate(s["phase_ids"]): gid[pid] = cur["phase"] + j
        for e in s["hyperedges"]:
            rows = [gid[n_] for n_ in e["nodes"] if n_ in gid]
            if rows:
                incidence_cols[e["type"]].append(rows)
        if s["step_target"] >= 0:
            step_targets.append(cur["step"] + s["step_target"])
            step_group.append((cur["step"], cur["step"] + s["n_step"]))
        for c, srcs in s["prop"]:
            prop_pairs.append((cur["step"] + c, [cur["step"] + x for x in srcs]))
        agent_targets.append(s["agent_target"]); mode_targets.append(s["mode_target"])
        for t in order: cur[t] += s[f"n_{t}"]

    incidence = {}
    for r in EDGE_TYPES:
        cols = incidence_cols[r]
        H = torch.zeros(N, len(cols))
        for ei, rows in enumerate(cols):
            for ridx in rows: H[ridx, ei] = 1.0
        incidence[r] = H.to(DEVICE)
    return {"feats": {t: torch.from_numpy(feats[t]).to(DEVICE) for t in order},
            "type_ids": torch.from_numpy(type_ids).to(DEVICE), "type_slices": slices,
            "incidence": incidence, "step_targets": step_targets,
            "step_group": step_group, "prop_pairs": prop_pairs,
            "agent_target": (torch.from_numpy(np.concatenate(agent_targets)).to(DEVICE)
                             if agent_targets else torch.zeros(0, device=DEVICE)),
            "mode_target": (torch.from_numpy(np.concatenate(mode_targets)).to(DEVICE)
                            if mode_targets else torch.zeros(0, len(FM_TYPES), device=DEVICE))}


def iterate(samples, bs, feat_dim, shuffle=True):
    idx = np.arange(len(samples))
    if shuffle: np.random.shuffle(idx)
    for i in range(0, len(idx), bs):
        yield collate([samples[j] for j in idx[i:i+bs]], feat_dim)


# ---------------------------------------------------------------- loss
def loss_fn(step_logit, agent_logit, pair_logit, batch, pos_w,
            w_prop=0.1, w_margin=0.5):
    # step: listwise softmax over each trajectory's steps (this IS a listwise loss)
    l_step = torch.tensor(0.0, device=step_logit.device)
    l_margin = torch.tensor(0.0, device=step_logit.device)
    if batch["step_group"]:
        ls, lm = [], []
        for (a, b), tgt in zip(batch["step_group"], batch["step_targets"]):
            logits = step_logit[a:b]
            g = tgt - a
            ls.append(F.cross_entropy(logits.unsqueeze(0), torch.tensor([g], device=logits.device)))
            if w_margin > 0 and logits.numel() > 1:            # improvement G
                neg = torch.cat([logits[:g], logits[g+1:]])
                lm.append(F.relu(1.0 - (logits[g] - neg.max())))
        l_step = torch.stack(ls).mean()
        if lm: l_margin = torch.stack(lm).mean()
    l_agent = F.binary_cross_entropy_with_logits(
        agent_logit, batch["agent_target"], pos_weight=pos_w["agent"])
    l_pair = F.binary_cross_entropy_with_logits(
        pair_logit, batch["mode_target"], pos_weight=pos_w["mode"])
    # improvement D: propagation consistency — a consumer should not be root
    # if any of its sources already is
    l_prop = torch.tensor(0.0, device=step_logit.device)
    if w_prop > 0 and batch["prop_pairs"]:
        r = torch.sigmoid(step_logit)
        vals = [r[c] * torch.max(r[torch.tensor(srcs, device=r.device)]) for c, srcs in batch["prop_pairs"]]
        l_prop = torch.stack(vals).mean()
    return (l_step + l_agent + l_pair + w_margin * l_margin + w_prop * l_prop)


# ---------------------------------------------------------------- eval helpers
@torch.no_grad()
def pair_probs(model, samples, feat_dim):
    model.eval()
    out = []
    for s in samples:
        b = collate([s], feat_dim)
        _, _, pl = model(b["feats"], b["type_ids"], b["type_slices"], b["incidence"])
        out.append(torch.sigmoid(pl).numpy())
    return out


def calibrate_thresholds(model, val_samples, feat_dim):
    """Improvement A: per-class thresholds maximizing F1 on val."""
    probs = pair_probs(model, val_samples, feat_dim)
    P = np.concatenate(probs, 0) if probs else np.zeros((0, len(FM_TYPES)))
    Y = np.concatenate([s["mode_target"] for s in val_samples], 0) \
        if val_samples else np.zeros_like(P)
    thr = np.full(len(FM_TYPES), 0.5)
    for k in range(len(FM_TYPES)):
        if Y[:, k].sum() == 0: continue
        best, bt = -1, 0.5
        for t in np.arange(0.1, 0.91, 0.05):
            f = f1_score(Y[:, k], (P[:, k] > t).astype(int), zero_division=0)
            if f > best: best, bt = f, t
        thr[k] = bt
    return thr


@torch.no_grad()
def evaluate_steps(model, samples, feat_dim):
    model.eval()
    top1 = top3 = tot = 0
    for s in samples:
        if s["step_target"] < 0: continue
        b = collate([s], feat_dim)
        sl, _, _ = model(b["feats"], b["type_ids"], b["type_slices"], b["incidence"])
        order = torch.argsort(sl, descending=True)
        tot += 1
        if order[0].item() == s["step_target"]: top1 += 1
        if s["step_target"] in order[:3].tolist(): top3 += 1
    return top1 / max(tot, 1), top3 / max(tot, 1)


# ---------------------------------------------------------------- training
def make_featurizer(mode, train_trajs, names, emb_model="mxbai"):
    if mode == "tfidf":
        texts = [s.content for t in train_trajs for s in t.steps if not s.is_input]
        return Featurizer("tfidf", train_steps_text=texts)
    # emb: merge cached vectors of all frameworks involved
    from common.embed_cache import load_cache
    idx_all, emb_list, off = {}, [], 0
    for n in names:
        idx, emb = load_cache(n, emb_model)
        for k, i in idx.items(): idx_all[k] = off + i
        emb_list.append(emb); off += emb.shape[0]
    return Featurizer("emb", emb_lookup=(idx_all, np.concatenate(emb_list, 0)))


def _make_fact_provider(args):
    """Return a factuality provider, or None for 'null' (keeps the 7-dim path exactly).
    Non-null providers append one factuality feature dim (S- tier)."""
    name = getattr(args, "factuality", "null")
    if name == "null":
        return None
    from common.factuality_provider import get_provider
    if name == "nli":
        return get_provider("nli",
                            model=getattr(args, "factuality_model",
                                          "cross-encoder/nli-deberta-v3-small"),
                            reference=getattr(args, "factuality_ref", "prior-steps"),
                            device=getattr(args, "device", "auto"))
    return get_provider(name)


def train_model(train_trajs, val_trajs, fz, args):
    fp = _make_fact_provider(args)
    fact_dim = 1 if (args.struct and fp is not None) else 0
    feat_dim = fz.dim + (N_STRUCT if args.struct else 0) + fact_dim
    tr = [build_sample(t, fz, args.struct, fp) for t in train_trajs]
    va = [build_sample(t, fz, args.struct, fp) for t in val_trajs]
    if getattr(args, "no_hyperedges", False):
        for s_ in tr + va:
            s_["hyperedges"] = []; s_["prop"] = []

    ay = np.concatenate([s["agent_target"] for s in tr])
    agent_w = torch.tensor(float((1 - ay.mean()) / max(ay.mean(), 1e-3)), device=DEVICE)
    my = np.concatenate([s["mode_target"] for s in tr])
    m_pos = my.mean(0).clip(1e-3, 1)
    mode_w = torch.tensor(((1 - m_pos) / m_pos).astype(np.float32), device=DEVICE).clamp(max=50.0)
    pos_w = {"agent": agent_w, "mode": mode_w}

    model = MedHyperTrace({t: feat_dim for t in NODE_TYPES}, hidden=args.hidden,
                          layers=2, attention=(args.backbone == "relation"),
                          backbone=args.backbone).to(DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=1e-5)
    for ep in range(args.epochs):
        model.train(); tot = 0.0
        for b in iterate(tr, args.bs, feat_dim):
            opt.zero_grad()
            sl, al, pl = model(b["feats"], b["type_ids"], b["type_slices"], b["incidence"])
            loss = loss_fn(sl, al, pl, b, pos_w, w_prop=args.prop, w_margin=args.margin)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            opt.step(); tot += loss.item()
        if ep == 0 or (ep + 1) % 4 == 0:
            t1, t3 = evaluate_steps(model, va or tr[:64], feat_dim)
            print(f"  ep{ep+1:02d} loss={tot/max(1,len(tr)//args.bs):.3f} "
                  f"val stepTop1={t1:.3f} Top3={t3:.3f}")
    thr = calibrate_thresholds(model, va, feat_dim)
    return model, thr, feat_dim


def split_val(train_trajs, frac=0.1, seed=0):
    tasks = sorted({t.id for t in train_trajs})
    rng = random.Random(seed); rng.shuffle(tasks)
    vt = set(tasks[:max(1, int(len(tasks) * frac))])
    return [t for t in train_trajs if t.id not in vt], \
           [t for t in train_trajs if t.id in vt]


def run(name=None, joint=False, holdout=None, args=None):
    """name: single-framework; joint: union training; holdout: OOD (train others).
    args.frameworks (optional): restrict the framework universe to a subset."""
    if holdout: joint = True
    universe = list(FILES)
    subset = getattr(args, "frameworks", None) if args else None
    if subset:
        bad = [f for f in subset if f not in FILES]
        if bad:
            raise ValueError(f"unknown framework(s) {bad}; valid: {list(FILES)}")
        universe = [f for f in FILES if f in subset]   # preserve canonical order
    names = universe if joint else [name]
    train_trajs, eval_sets = [], {}
    for n in names:
        trajs = load_jsonl(FILES[n])
        tr_ids, te_ids = _fixed_split(n)
        if holdout and n == holdout:
            eval_sets[n] = [t for t in trajs if t.id in te_ids]
            continue
        train_trajs += [t for t in trajs if t.id in tr_ids]
        eval_sets[n] = [t for t in trajs if t.id in te_ids]
    if holdout:
        eval_sets = {holdout: eval_sets[holdout]}
    feat_mode, emb_model = args.features, getattr(args, "emb_model", "mxbai")
    if feat_mode == "nomic":                 # back-compat alias
        feat_mode, emb_model = "emb", "nomic"
    fz = make_featurizer(feat_mode, train_trajs,
                         [n for n in names if not (holdout and n == holdout)],
                         emb_model)
    tr, va = split_val(train_trajs)
    model, thr, feat_dim = train_model(tr, va, fz, args)

    results = {}
    for n, te_trajs in eval_sets.items():
        te = [build_sample(t, fz, args.struct, _make_fact_provider(args)) for t in te_trajs]
        if getattr(args, "no_hyperedges", False):
            for s_ in te:
                s_["hyperedges"] = []; s_["prop"] = []
        t1, t3 = evaluate_steps(model, te, feat_dim)
        results[n] = {"step_top1": t1, "step_top3": t3,
                      "te_samples": te, "te_trajs": te_trajs}
    return model, fz, thr, feat_dim, results


def get_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("target", nargs="?", default="all",
                   help="framework name | all | joint")
    p.add_argument("--features", choices=["tfidf", "emb", "nomic"], default="tfidf")
    p.add_argument("--emb_model", default="mxbai",
                   help="embedding cache tag when --features emb (mxbai|nomic|...)")
    p.add_argument("--device", default="auto",
                   help="torch device: auto (cuda if available) | cuda | cpu")
    p.add_argument("--struct", type=int, default=1)
    p.add_argument("--factuality", default="null",
                   choices=["null", "heuristic", "nli", "medical"],
                   help="S- tier: pluggable external factuality feature. 'null' (default) "
                        "= no change; 'heuristic' = CPU placeholder; 'nli' = real "
                        "RefChecker-style NLI detector (needs transformers+torch); "
                        "'medical' needs a judge wired in (see common/factuality_provider.py).")
    p.add_argument("--factuality_model", default="cross-encoder/nli-deberta-v3-small",
                   help="HF NLI model for --factuality nli (small, open, offline).")
    p.add_argument("--factuality_ref", default="prior-steps",
                   choices=["prior-steps", "gold-answer", "none"],
                   help="what each claim is checked against for --factuality nli.")
    p.add_argument("--backbone", choices=["relation", "standard"], default="relation")
    p.add_argument("--prop", type=float, default=0.1)
    p.add_argument("--margin", type=float, default=0.5)
    p.add_argument("--holdout", default=None)
    p.add_argument("--frameworks", nargs="+", default=None,
                   help="restrict to a subset of frameworks (e.g. --frameworks dylan "
                        "mdagents clinical_agent clinical_agent5). Applies to joint "
                        "(union over the subset) and to 'all' (loops the subset). "
                        "Default: all five.")
    p.add_argument("--no_hyperedges", action="store_true",
                   help="ablation: drop ALL hyperedges (self-loop only)")
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--bs", type=int, default=16)
    p.add_argument("--hidden", type=int, default=128)
    p.add_argument("--lr", type=float, default=2e-3)
    # parse_known_args (not parse_args): hgnn_unified_eval.py passes through its own
    # flags (--report_gran / --json_out / --pooled_out) that it parses manually; a strict
    # parse_args would reject them as 'unrecognized arguments'. Ignore unknowns here.
    args, _unknown = p.parse_known_args(argv)
    return args


if __name__ == "__main__":
    args = get_args()
    if args.holdout:
        print(f"[OOD holdout={args.holdout}] features={args.features} struct={args.struct} "
              f"backbone={args.backbone}")
        _, _, _, _, res = run(holdout=args.holdout, args=args)
    elif args.target == "joint":
        print(f"[JOINT] features={args.features} struct={args.struct} backbone={args.backbone}")
        _, _, _, _, res = run(joint=True, args=args)
    else:
        targets = list(FILES) if args.target == "all" else [args.target]
        res = {}
        for n in targets:
            print(f"[{n}] features={args.features} struct={args.struct} "
                  f"backbone={args.backbone} prop={args.prop} margin={args.margin}")
            _, _, _, _, r = run(name=n, args=args)
            res.update(r)
    for n, m in res.items():
        print(f"  >>> {n}: step Top-1={m['step_top1']:.3f} Top-3={m['step_top3']:.3f}")
