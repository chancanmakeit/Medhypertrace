"""E4 stage A (pre-registration E4 v1): frozen proxy LM, trained step-scoring head on TracerTraj, evaluated on WW / TEgc.

  python -m hgfm.e4.e4_probe --feats base=<feats_base.pt> tapt=<...> [S=... R=...] --out <dir> [--heads linear mlp]

Head: LayerNorm(H) -> Linear(H, 1)   ("linear")   or   LayerNorm -> Linear(H, 256) -> GELU -> Linear(256, 1)  ("mlp").
Loss: softmax cross-entropy over the candidate (model) steps of a trajectory, label = the mistake step. AdamW lr 1e-3,
weight decay 1e-2, 32 trajectories per step, at most 30 epochs, early stopping on mean validation rank-AUROC
(patience 5), best epoch restored. Seeds 0, 1, 2. Outputs per head type: scores on WW / TEgc / TT test for every proxy
and seed, and the evaluation (hgfm/e4/e4_eval.py) with the pre-registered comparisons (every proxy - base).
"""
import argparse, json, os
import numpy as np
import torch

from hgfm.e4.e4_eval import evaluate

EVAL = ("who_and_when", "traceelephant_gc", "tt_test")


def load(path):
    D = torch.load(path, weights_only=False); rows = {}
    for r in D["rows"]:
        cand = [j for j in range(1, len(r["step_is_model"])) if r["step_is_model"][j]]
        rows[(r["dataset"], r["id"])] = {"x": r["feats"].float(), "cand": cand, "label": r["mistake_step"] + 1,
                                         "ntok": r["step_ntok"], "code": r["step_has_code"], "n_steps": len(r["step_is_model"]) - 1}
    return rows, D.get("skipped_over_131072", {})


def make_head(kind, H):
    if kind == "linear": return torch.nn.Sequential(torch.nn.LayerNorm(H), torch.nn.Linear(H, 1))
    return torch.nn.Sequential(torch.nn.LayerNorm(H), torch.nn.Linear(H, 256), torch.nn.GELU(), torch.nn.Linear(256, 1))


def score(head, rows, keys, dev):
    head.eval(); out = {}
    with torch.no_grad():
        for k in keys:
            r = rows[k]; out[k] = head(r["x"][r["cand"]].to(dev)).squeeze(-1).float().cpu().tolist()
    return out


def val_rauc(sc, rows):
    v = []
    for k, s in sc.items():
        c = rows[k]["cand"]
        if rows[k]["label"] in c and len(c) > 1:
            s = np.asarray(s); mi = c.index(rows[k]["label"]); v.append(((s < s[mi]).sum() + 0.5 * ((s == s[mi]).sum() - 1)) / (len(s) - 1))
    return float(np.mean(v))


def train(rows, kind, seed, dev, log, allow=None):
    """allow: optional set of tt_train ids (Stage 0 label-efficiency subsets); None = all (E4 v1 behaviour)."""
    torch.manual_seed(seed); rng = np.random.default_rng(seed)
    tr = [k for k in rows if k[0] == "tt_train" and rows[k]["label"] in rows[k]["cand"] and (allow is None or k[1] in allow)]
    va = [k for k in rows if k[0] == "tt_val"]
    H = next(iter(rows.values()))["x"].shape[1]; head = make_head(kind, H).to(dev)
    opt = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-2); best, best_state, bad = -1, None, 0
    for ep in range(30):
        head.train(); perm = rng.permutation(len(tr))
        for b in range(0, len(perm), 32):
            loss = 0
            for i in perm[b:b + 32]:
                r = rows[tr[i]]; lg = head(r["x"][r["cand"]].to(dev)).squeeze(-1)
                loss = loss + torch.nn.functional.cross_entropy(lg.view(1, -1), torch.tensor([r["cand"].index(r["label"])], device=dev))
            opt.zero_grad(); (loss / len(perm[b:b + 32])).backward(); opt.step()
        v = val_rauc(score(head, rows, va, dev), rows); log.append({"seed": seed, "epoch": ep, "val_rauc": v})
        if v > best: best, bad, best_state = v, 0, {n: p.detach().clone() for n, p in head.state_dict().items()}
        else:
            bad += 1
            if bad >= 5: break
    head.load_state_dict(best_state); return head, best


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--feats", nargs="+"); ap.add_argument("--out")
    ap.add_argument("--heads", nargs="*", default=["linear", "mlp"]); ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--subsets", default=None, help="Stage 0 label efficiency: subsets.json from hgfm.stage0.le_subsets")
    ap.add_argument("--sizes", nargs="*", default=None, help="subset sizes to run (default: all in the file)")
    a = ap.parse_args()
    if a.subsets: return main_le(a); os.makedirs(a.out, exist_ok=True); dev = "cuda" if torch.cuda.is_available() else "cpu"
    F = {}; meta = {}; skipped = {}
    for spec in a.feats:
        name, path = spec.split("="); F[name], skipped[name] = load(path)
    common = set.intersection(*[{k for k in rows if k[0] in EVAL} for rows in F.values()])   # same eval trajectories for all proxies
    for k in common:
        r = F["base"][k]; meta[k] = {kk: r[kk] for kk in ("cand", "label", "ntok", "code", "n_steps")}
    for kind in a.heads:
        scores, log = {}, []
        for name, rows in F.items():
            scores[f"{kind}_{name}"] = {k: [] for k in common}
            for sd in range(a.seeds):
                head, best = train(rows, kind, sd, dev, log); print(kind, name, sd, "best val rauc", round(best, 4), flush=True)
                sc = score(head, rows, sorted(common), dev)
                for k in common: scores[f"{kind}_{name}"][k].append(sc[k])
        pairs = [(f"{kind}_{n}", f"{kind}_base") for n in F if n != "base"]
        res = evaluate(scores, meta, pairs)
        res["train_log"] = log; res["skipped_over_131072"] = {n: len(s) for n, s in skipped.items()}; res["n_eval"] = len(common)
        json.dump(res, open(os.path.join(a.out, f"e4a_{kind}.json"), "w"), indent=1)
        json.dump({st: {f"{k[0]}|{k[1]}": v for k, v in d.items()} for st, d in scores.items()}, open(os.path.join(a.out, f"e4a_{kind}_scores.json"), "w"))
        for kind2 in ("raw", "resid"):
            for st, v in res["summary"][kind2].items():
                print(kind2, f"{st:16s}", "  ".join(f"{sn} a1 {x['acc1']:.3f} r {x['rauc']:.3f} (n={x['n']})" for sn, x in v.items()), flush=True)
        for p in pairs:
            for kind2 in ("raw", "resid"):
                q = res["paired"].get(f"{p[0]} - {p[1]} / pooled / {kind2} / rauc", {})
                print("DECISION-INPUT", p, kind2, q, flush=True)


def main_le(a):
    """Stage 0 Q1: for every proxy, head type, size n and draw d, train on subset (d, n) with head seed d. Saves scores
    {"<kind>_<proxy>_n<n>": {"dataset|id": [per-draw score lists]}} + meta; the pre-registered statistics (incl. the
    label-efficiency area) are computed by hgfm.stage0.le_analyze."""
    os.makedirs(a.out, exist_ok=True); dev = "cuda" if torch.cuda.is_available() else "cpu"
    SUB = json.load(open(a.subsets)); draws = sorted(SUB["draws"], key=int); sizes = a.sizes or sorted(SUB["draws"][draws[0]], key=int)
    F = {}
    for spec in a.feats:
        name, path = spec.split("="); F[name], _ = load(path)
    base = F.get("base") or next(iter(F.values()))
    common = set.intersection(*[{k for k in rows if k[0] in EVAL} for rows in F.values()])
    meta = {f"{k[0]}|{k[1]}": {kk: base[k][kk] for kk in ("cand", "label", "ntok", "code", "n_steps")} for k in common}
    json.dump(meta, open(os.path.join(a.out, "meta.json"), "w"))
    for name, rows in F.items():
        for kind in a.heads:
            fn = os.path.join(a.out, f"le_{kind}_{name}.json")
            if os.path.exists(fn): print("skip", fn, flush=True); continue
            scores, log = {}, []
            for n in sizes:
                st = f"{kind}_{name}_n{n}"; scores[st] = {f"{k[0]}|{k[1]}": [] for k in common}
                for d in draws:
                    allow = set(SUB["draws"][d][str(n)]); head, best = train(rows, kind, int(d), dev, log, allow)
                    print(kind, name, "n", n, "draw", d, "n_train", sum(1 for k in rows if k[0] == "tt_train" and k[1] in allow), "best val rauc", round(best, 4), flush=True)
                    sc = score(head, rows, sorted(common), dev)
                    for k in common: scores[st][f"{k[0]}|{k[1]}"].append(sc[k])
            json.dump({"scores": scores, "train_log": log}, open(fn, "w"))


if __name__ == "__main__":
    main()
