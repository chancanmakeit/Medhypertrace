"""Interaction-CPT pre-registration §3: choose the primary read-out interface with base only, on TracerTraj validation.

  python -m hgfm.icpt.iface_probe --prefix <feats_base.pt> --query <featsq_base.pt> --out <json>

Interfaces: (a) prefix features + linear head; (b) full-trajectory query features + linear head; (c) prefix features +
bidirectional aggregator (LayerNorm -> Linear(H, 256) -> 2-layer TransformerEncoder (4 heads, learned step-position
embedding) -> Linear(256, 1), over all steps of the trajectory). Loss: softmax cross-entropy over candidate (model)
steps, label = mistake step (as E4). Training on tt_train with a fixed 10% trajectory hold-out for early stopping
(patience 5, <= 30 epochs, AdamW lr 1e-3 (linear) / 3e-4 (aggregator), wd 1e-2, 32 trajectories per step); seeds 0-2.
Selection statistic (fixed in the pre-registration): mean over seeds of the CONTROLLED rank-AUROC on tt_val (OLS residual
on [log ntok, relative position, has_code] with trajectory fixed effects, hgfm.e4.e4_eval.residualise). WW / TEgc / TT
test are reported descriptively.
"""
import argparse, json
import numpy as np
import torch

from hgfm.e4.e4_probe import load
from hgfm.e4.e4_eval import residualise, metrics

EVAL = ("tt_val", "who_and_when", "traceelephant_gc", "tt_test")


class Agg(torch.nn.Module):
    def __init__(self, H, d=256, maxpos=1024):
        super().__init__()
        self.inp = torch.nn.Sequential(torch.nn.LayerNorm(H), torch.nn.Linear(H, d)); self.pos = torch.nn.Embedding(maxpos, d)
        self.enc = torch.nn.TransformerEncoder(torch.nn.TransformerEncoderLayer(d, 4, 4 * d, 0.1, batch_first=True, norm_first=True), 2)
        self.out = torch.nn.Linear(d, 1); self.maxpos = maxpos

    def forward(self, x):   # x [T+1, H] -> scores for every row
        p = torch.clamp(torch.arange(x.shape[0], device=x.device), max=self.maxpos - 1)
        return self.out(self.enc((self.inp(x) + self.pos(p))[None]))[0].squeeze(-1)


class Lin(torch.nn.Module):
    def __init__(self, H):
        super().__init__(); self.f = torch.nn.Sequential(torch.nn.LayerNorm(H), torch.nn.Linear(H, 1))

    def forward(self, x): return self.f(x).squeeze(-1)


def scores(head, rows, keys, dev):
    head.eval(); out = {}
    with torch.no_grad():
        for k in keys:
            r = rows[k]; out[k] = head(r["x"].to(dev)).float().cpu()[r["cand"]].tolist()
    return out


def rauc(sc, rows, keys, controlled):
    keys = [k for k in keys if k in sc and rows[k]["label"] in rows[k]["cand"] and len(rows[k]["cand"]) >= 2]
    if not keys: return None, 0
    sl = [sc[k] for k in keys]
    if controlled: sl = residualise(sl, [rows[k] for k in keys])
    v = [metrics(s, rows[k]["cand"].index(rows[k]["label"]))["rauc"] for k, s in zip(keys, sl)]
    return float(np.mean(v)), len(v)


def train(rows, kind, seed, dev):
    torch.manual_seed(seed); rng = np.random.default_rng(seed)
    tr_all = sorted(k for k in rows if k[0] == "tt_train" and rows[k]["label"] in rows[k]["cand"])
    hold = set(np.random.default_rng(12345).permutation(len(tr_all))[: len(tr_all) // 10].tolist())
    tr = [k for i, k in enumerate(tr_all) if i not in hold]; es = [k for i, k in enumerate(tr_all) if i in hold]
    H = next(iter(rows.values()))["x"].shape[1]
    head = (Agg(H) if kind == "agg" else Lin(H)).to(dev)
    opt = torch.optim.AdamW(head.parameters(), lr=3e-4 if kind == "agg" else 1e-3, weight_decay=1e-2)
    best, state, bad = -1, None, 0
    for ep in range(30):
        head.train(); perm = rng.permutation(len(tr))
        for b in range(0, len(perm), 32):
            opt.zero_grad(); loss = 0.0
            for i in perm[b:b + 32]:
                r = rows[tr[i]]; s = head(r["x"].to(dev))[r["cand"]]
                loss = loss + torch.nn.functional.cross_entropy(s[None], torch.tensor([r["cand"].index(r["label"])], device=dev))
            (loss / len(perm[b:b + 32])).backward(); opt.step()
        v, _ = rauc(scores(head, rows, es, dev), rows, es, False)
        if v > best: best, state, bad = v, {k: t.detach().clone() for k, t in head.state_dict().items()}, 0
        else:
            bad += 1
            if bad >= 5: break
    head.load_state_dict(state); return head, best, ep


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--prefix"); ap.add_argument("--query"); ap.add_argument("--out")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2]); a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    P, _ = load(a.prefix); Q, _ = load(a.query)
    common = set(P) & set(Q)   # identical trajectory set for every interface
    P = {k: v for k, v in P.items() if k in common}; Q = {k: v for k, v in Q.items() if k in common}
    res = {}
    for name, rows, kind in (("a_prefix_linear", P, "lin"), ("b_query_linear", Q, "lin"), ("c_prefix_aggregator", P, "agg")):
        res[name] = {"seeds": []}
        for sd in a.seeds:
            head, es_best, ep = train(rows, kind, sd, dev); rec = {"seed": sd, "earlystop_rauc": es_best, "epochs": ep + 1}
            for ds in EVAL:
                keys = [k for k in rows if k[0] == ds]; sc = scores(head, rows, keys, dev)
                for c in (False, True):
                    v, n = rauc(sc, rows, keys, c); rec[f"{ds}/{'resid' if c else 'raw'}"] = v; rec[f"{ds}/n"] = n
            res[name]["seeds"].append(rec); print(name, rec, flush=True)
        for key in res[name]["seeds"][0]:
            if "/" in key and not key.endswith("/n"):
                vals = [s[key] for s in res[name]["seeds"] if s[key] is not None]
                res[name][key] = float(np.mean(vals)) if vals else None
    sel = max(res, key=lambda n: res[n]["tt_val/resid"])
    res["selected_primary_interface"] = sel
    res["rule"] = "max mean controlled rank-AUROC on tt_val over seeds (pre-registration InteractionCPT v1 §3)"
    res["n_common_trajectories"] = len(common)
    json.dump(res, open(a.out, "w"), indent=1)
    for n in ("a_prefix_linear", "b_query_linear", "c_prefix_aggregator"):
        print(f"{n:22s} " + "  ".join(f"{ds} raw {res[n][ds + '/raw']:.3f} resid {res[n][ds + '/resid']:.3f}" for ds in EVAL))
    print("SELECTED", sel)


if __name__ == "__main__":
    main()
