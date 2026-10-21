"""Stage 4: score the 400 human instances with the trained graph-token LM (round 38).

Score of a prompt = logit("yes") - logit("no") at the first answer position (the answer is
constrained to {yes, no}: C7 in its simplest form). Instance score = max over the prompts of
that instance (one per matching step), as in train_maa.py. Reports per-code AUROC against the
human majority and the macro AUROC with a bootstrap CI; writes per-instance scores so folds
can be pooled exactly like the encoder results (results/phase1_maa).
Usage: python -m hgfm.llm.eval --lm Qwen/Qwen3-8B --ckpt <fold>/ckpt --data <fold>/sft/eval_human.jsonl --tokens <fold>/graph_tokens.pt --out <fold>/eval.json [--no_graph] [--zero_shot]
  --zero_shot: no LoRA / projector (graph placeholders removed by building the data with --no_graph) = untrained LLM baseline
"""
import argparse, json, collections, warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)
import numpy as np, torch
from sklearn.metrics import roc_auc_score
from hgfm.llm.model import GraphTokenLM, graph_vectors
from hgfm.llm.train import encode


def first_token_id(tok, word):
    return tok(word, add_special_tokens=False)["input_ids"][0]


@torch.no_grad()
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lm", default="Qwen/Qwen3-8B"); ap.add_argument("--ckpt", default=""); ap.add_argument("--data"); ap.add_argument("--tokens"); ap.add_argument("--out")
    ap.add_argument("--no_graph", action="store_true"); ap.add_argument("--zero_shot", action="store_true"); ap.add_argument("--max_len", type=int, default=2048)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu"); ap.add_argument("--dtype", default="bf16"); ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(); dtype = {"bf16": torch.bfloat16, "fp32": torch.float32}[a.dtype]
    model = GraphTokenLM(a.lm, dtype=dtype, use_graph=not (a.no_graph or a.zero_shot), ckpt=(a.ckpt or None) if not a.zero_shot else None)
    model.to(a.device).eval()
    tokens = torch.load(a.tokens); data = [json.loads(l) for l in open(a.data)]
    if a.limit: data = data[: a.limit]
    yes, no = first_token_id(model.tok, "yes"), first_token_id(model.tok, "no")
    inst = collections.defaultdict(list); meta = {}
    for s in data:
        p, _ = encode(model, {**s, "answer": ""}, a.max_len, with_answer=False)
        g = graph_vectors(s, tokens); n_ph = sum(1 for t in p if t == model.graph_id); g = g[-n_ph:] if n_ph else g[:0]
        ids = torch.tensor([p], device=a.device)
        logits = model(ids, torch.ones_like(ids), g.to(a.device))[0]
        inst[s["inst"]].append(float(logits[yes] - logits[no])); meta[s["inst"]] = (s["code"], s["label"], s["auditor"])
    rows = [{"inst": k, "code": meta[k][0], "human": meta[k][1], "auditor": meta[k][2], "score": max(v)} for k, v in inst.items()]
    def auc(y, sc): return roc_auc_score(y, sc) if len(set(y)) == 2 else float("nan")
    codes = sorted({r["code"] for r in rows})
    per = {c: auc([r["human"] for r in rows if r["code"] == c], [r["score"] for r in rows if r["code"] == c]) for c in codes}
    rng = np.random.default_rng(0); boots = []
    for _ in range(500):
        b = [rows[i] for i in rng.integers(0, len(rows), len(rows))]
        boots.append(np.nanmean([auc([r["human"] for r in b if r["code"] == c], [r["score"] for r in b if r["code"] == c]) for c in codes]))
    out = {"n": len(rows), "macro_auroc": float(np.nanmean(list(per.values()))), "ci95": [float(np.nanpercentile(boots, 2.5)), float(np.nanpercentile(boots, 97.5))],
           "per_code": per, "rows": rows, "args": vars(a)}
    json.dump(out, open(a.out, "w"), indent=1); print(f"n={out['n']} macro AUROC={out['macro_auroc']:.3f} {out['ci95']}")


if __name__ == "__main__":
    main()
