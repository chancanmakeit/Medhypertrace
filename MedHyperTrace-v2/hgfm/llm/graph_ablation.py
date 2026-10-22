"""Graph-token ablation for a trained graph checkpoint (round 54).

Question: does the LoRA-tuned LM actually use the graph tokens? Re-score the same eval prompts
with the graph vectors perturbed and compare against the unperturbed scores (same model, same
prompts, same instances -> paired):
  none        unperturbed (must reproduce eval.py; checked against --ref if given)
  zero_state  HGFM state (first d dims) set to 0, node/edge type flag kept -> proj(0 | flag)
  mean_state  state replaced by the eval-set mean state of its kind (node / hyperedge)
  zero_emb    projector output replaced by the zero vector (placeholder carries no content)
  shuffle_k   each run's graph vectors taken from another run of the eval set
              (derangement over runs, seed k; refs index the donor modulo its size)
Scoring is identical to eval.py: logit(yes) - logit(no), instance score = max over its prompts,
macro AUROC over codes vs the human majority. Paired bootstrap (1000, seed 0) of the
macro-AUROC difference mode - none.
Usage (one fold):  python -m hgfm.llm.graph_ablation --lm <path> --ckpt <fold>/ckpt_<tag>_graph \
                     --data <fold>/sft_graph/eval_human.jsonl --tokens <fold>/graph_tokens.pt \
                     --ref <fold>/eval_<tag>_graph.json --out <fold>/ablate_<tag>_graph.json
       (pooled):   python -m hgfm.llm.graph_ablation --pool <llm_dir> --tag <tag> [--folds LQD_a,LQD_b]
"""
import argparse, collections, json, os, warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)
import numpy as np, torch
from sklearn.metrics import roc_auc_score
from scipy.stats import spearmanr

MODES = ["none", "zero_state", "mean_state", "zero_emb", "shuffle_0", "shuffle_1", "shuffle_2"]


def macro(rows):
    """rows: list of (code, human, score)."""
    out = []
    for c in sorted({r[0] for r in rows}):
        y = [r[1] for r in rows if r[0] == c]; s = [r[2] for r in rows if r[0] == c]
        if len(set(y)) == 2: out.append(roc_auc_score(y, s))
    return float(np.mean(out)) if out else float("nan")


def paired(meta, A, B, n_boot=1000):
    """meta: inst -> (code, human); A, B: inst -> score. Returns (n, aucA, aucB, lo, hi) of A - B."""
    ks = sorted(set(A) & set(B)); rng = np.random.default_rng(0); d = []
    f = lambda kk, S: macro([(meta[k][0], meta[k][1], S[k]) for k in kk])
    for _ in range(n_boot):
        b = [ks[i] for i in rng.integers(0, len(ks), len(ks))]; d.append(f(b, A) - f(b, B))
    return len(ks), f(ks, A), f(ks, B), float(np.nanpercentile(d, 2.5)), float(np.nanpercentile(d, 97.5))


def summarize(meta, scores):
    base = scores["none"]; ks = sorted(base); out = {}
    sd = float(np.std([base[k] for k in ks]))
    for m, S in scores.items():
        n, a, b, lo, hi = paired(meta, S, base)
        dv = np.array([S[k] - base[k] for k in ks])
        out[m] = {"n": n, "macro_auroc": a, "diff_vs_none": a - b, "ci95": [lo, hi],
                  "mean_abs_dscore": float(np.abs(dv).mean()), "mean_dscore": float(dv.mean()),
                  "rel_abs_dscore": float(np.abs(dv).mean() / sd) if sd else float("nan"),
                  "spearman_vs_none": float(spearmanr([S[k] for k in ks], [base[k] for k in ks])[0])}
    return out


@torch.no_grad()
def run_fold(a):
    from hgfm.llm.model import GraphTokenLM
    from hgfm.llm.train import encode
    dtype = {"bf16": torch.bfloat16, "fp32": torch.float32}[a.dtype]
    model = GraphTokenLM(a.lm, dtype=dtype, use_graph=True, ckpt=a.ckpt); model.to(a.device).eval()
    tokens = torch.load(a.tokens); data = [json.loads(l) for l in open(a.data)]
    if a.limit: data = data[: a.limit]
    tid = lambda w: model.tok(w, add_special_tokens=False)["input_ids"][0]
    yes, no = tid("yes"), tid("no")
    d = next(iter(tokens.values()))["h"].shape[1]
    # eval-set mean state per kind
    runs = sorted({s["run_id"] for s in data})
    em = [tokens[r]["m"].float() for r in runs if tokens[r]["m"].numel()]
    mean = {"node": torch.cat([tokens[r]["h"].float() for r in runs]).mean(0),
            "edge": torch.cat(em).mean(0) if em else torch.zeros(d)}

    def vecs(s, mode, donor=None):
        t = tokens[donor or s["run_id"]]; out = []
        for kind, i in s["graph_refs"]:
            arr = t["h"] if kind == "node" else t["m"]
            if mode == "zero_state": v = torch.zeros(d)
            elif mode == "mean_state": v = mean["node" if kind == "node" else "edge"]
            elif arr.shape[0] == 0: v = torch.zeros(d)
            else: v = arr[i % arr.shape[0]].float()   # donor may be smaller than the original run
            flag = torch.tensor([1.0, 0.0]) if kind == "node" else torch.tensor([0.0, 1.0])
            out.append(torch.cat([v.float(), flag]))
        return torch.stack(out) if out else torch.zeros(0, d + 2)

    real_proj = model.proj
    class ZeroProj(torch.nn.Module):
        def __init__(self, hid): super().__init__(); self.hid = hid
        def forward(self, x): return torch.zeros(x.shape[0], self.hid, dtype=x.dtype, device=x.device)
    zero_proj = ZeroProj(model.lm.get_input_embeddings().weight.shape[1])

    prompts = []   # encode once
    n_ph_all = []
    for s in data:
        p, _ = encode(model, {**s, "answer": ""}, a.max_len, with_answer=False)
        n_ph = sum(1 for t in p if t == model.graph_id); n_ph_all.append(n_ph); prompts.append((s, p, n_ph))
    meta = {s["inst"]: (s["code"], s["label"]) for s in data}
    scores = {}
    for mode in MODES:
        donor = {}
        if mode.startswith("shuffle"):
            rng = np.random.default_rng(int(mode.split("_")[1]))
            while True:
                perm = rng.permutation(len(runs))
                if len(runs) < 2 or not np.any(perm == np.arange(len(runs))): break
            donor = {runs[i]: runs[perm[i]] for i in range(len(runs))}
        model.proj = zero_proj if mode == "zero_emb" else real_proj
        inst = collections.defaultdict(list)
        for s, p, n_ph in prompts:
            vm = mode if mode in ("zero_state", "mean_state") else "real"
            g = vecs(s, vm, donor.get(s["run_id"])); g = g[-n_ph:] if n_ph else g[:0]
            ids = torch.tensor([p], device=a.device)
            lg = model(ids, torch.ones_like(ids), g.to(a.device))[0]
            inst[s["inst"]].append(float(lg[yes] - lg[no]))
        scores[mode] = {k: max(v) for k, v in inst.items()}
        print(f"{mode:11s} macro AUROC={macro([(meta[k][0], meta[k][1], v) for k, v in scores[mode].items()]):.3f}", flush=True)
    model.proj = real_proj
    check = None
    if a.ref and os.path.exists(a.ref):
        ref = {r["inst"]: r["score"] for r in json.load(open(a.ref))["rows"]}
        common = set(ref) & set(scores["none"])
        check = {"n_common": len(common), "max_abs_diff_vs_eval_py": float(max(abs(ref[k] - scores["none"][k]) for k in common)) if common else None}
        print("reproduction check:", check, flush=True)
    out = {"summary": summarize(meta, scores), "check": check,
           "placeholders": {"mean": float(np.mean(n_ph_all)), "min": int(min(n_ph_all)), "max": int(max(n_ph_all))},
           "meta": {k: list(v) for k, v in meta.items()}, "scores": scores, "args": vars(a)}
    json.dump(out, open(a.out, "w"), indent=1)
    for m, r in out["summary"].items():
        print(f"{m:11s} {r['macro_auroc']:.3f} diff {r['diff_vs_none']:+.3f} [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}]  |dscore| {r['mean_abs_dscore']:.3f} ({r['rel_abs_dscore']:.2f} sd)  rho {r['spearman_vs_none']:.3f}")


def run_pool(a):
    folds = a.folds.split(",") if a.folds else sorted(f for f in os.listdir(a.pool) if f.startswith("LQD_"))
    meta, scores, used = {}, collections.defaultdict(dict), []
    for f in folds:
        p = f"{a.pool}/{f}/ablate_{a.tag}_graph.json"
        if not os.path.exists(p): print(f, "missing"); continue
        j = json.load(open(p)); used.append(f)
        meta.update({k: tuple(v) for k, v in j["meta"].items()})
        for m, S in j["scores"].items(): scores[m].update(S)
    summ = summarize(meta, dict(scores))
    print(f"POOLED over {used}")
    for m, r in summ.items():
        print(f"{m:11s} n={r['n']} {r['macro_auroc']:.3f} diff {r['diff_vs_none']:+.3f} [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}]  |dscore| {r['mean_abs_dscore']:.3f} ({r['rel_abs_dscore']:.2f} sd)  rho {r['spearman_vs_none']:.3f}")
    if a.out: json.dump({"folds": used, "summary": summ}, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lm"); ap.add_argument("--ckpt"); ap.add_argument("--data"); ap.add_argument("--tokens"); ap.add_argument("--ref", default="")
    ap.add_argument("--out", default=""); ap.add_argument("--max_len", type=int, default=2048); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu"); ap.add_argument("--dtype", default="bf16")
    ap.add_argument("--pool", default=""); ap.add_argument("--tag", default="models--Qwen--Qwen3-8B"); ap.add_argument("--folds", default="")
    a = ap.parse_args()
    run_pool(a) if a.pool else run_fold(a)
