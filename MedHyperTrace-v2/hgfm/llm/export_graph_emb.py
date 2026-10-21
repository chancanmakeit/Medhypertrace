"""Stage 1 of the LLM layer (C6): train the HGFM v0.2 encoder on a fold's training part and
export graph tokens for every run of that fold (round 38).

For each fold (LQD:<mas> or QD, see hgfm/splits_maa.py) the encoder never sees the fold's
test runs, so the graph tokens of test runs are zero-shot w.r.t. the held-out MAS.
Output <out_dir>/<fold>/graph_tokens.pt:
  {run_id: {"h": fp16 [n_steps, d], "m": fp16 [n_edges, d], "step_prob": fp16 [n_steps, 9],
            "run_prob": fp16 [2], "split": "train" | "test"}}
Edge order equals hgfm.data_v02.edges_of(record) order (deterministic), so build_sft.py can
recompute each edge's instruction text and members from the record.
Usage: python -m hgfm.llm.export_graph_emb <mas_traj.jsonl> <emb_dir> <human400.jsonl> <anchor_overlap.json> <out_dir> [folds] [gold] [max_runs]
       folds: comma list, e.g. "QD,LQD:mac" (default: all LQD folds + QD)
"""
import json, os, sys, torch
from hgfm.train_maa import load
from hgfm.train_v02 import attach_edges, train, collate
from hgfm.splits_maa import folds as make_folds


def main(src, emb, human, overlap, out, which="", gold="0", max_runs="0"):
    gold = gold == "1"; max_runs = int(max_runs)   # max_runs>0: smoke test (subsample train and test)
    H = [json.loads(l) for l in open(human)]; hq = {h["run_id"].split("|")[3] + "/" + h["qid"] for h in H}
    G = attach_edges(load(src, emb, overlap, gold), src, emb, overlap, gold)
    F = make_folds(G, hq, ("LQD", "QD"))
    if which: F = [f for f in F if f[0] in which.split(",")]
    for name, tr, te in F:
        if max_runs: import random; random.seed(0); tr = random.sample(tr, min(len(tr), max_runs)); te = random.sample(te, min(len(te), max_runs // 2))
        d = os.path.join(out, name.replace(":", "_")); os.makedirs(d, exist_ok=True)
        m = train(tr, {}); m.eval(); res = {}
        torch.save(m.state_dict(), os.path.join(d, "encoder.pt"))
        for split, gs in (("train", tr), ("test", te)):
            for b in range(0, len(gs), 128):
                part = gs[b:b + 128]; B = collate(part); h, mm, sl, rl = m.encode(B)
                sl = torch.sigmoid(sl); rl = torch.sigmoid(rl); vo = eo = 0
                for k, g in enumerate(part):
                    n, ne = g["X"].shape[0], len(g["e_rel"])
                    res[g["run_id"]] = {"h": h[vo:vo + n].half(), "m": mm[eo:eo + ne].half(), "step_prob": sl[vo:vo + n].half(),
                                        "run_prob": rl[k].half(), "split": split}
                    vo += n; eo += ne
        torch.save(res, os.path.join(d, "graph_tokens.pt"))
        print(name, "train", len(tr), "test", len(te), "->", d, flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:9])
