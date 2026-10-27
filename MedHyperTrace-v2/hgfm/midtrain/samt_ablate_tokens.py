"""Ablated copies of a graph-token file for the C6 diagnosis on SAMT checkpoints (round 64).

  python -m hgfm.midtrain.samt_ablate_tokens <graph_tokens.pt> <out_zero.pt> <out_shuf.pt> [--seed 0]

zero : every node / edge state set to 0 (the projector still sees the node/edge flag)
shuf : every node state replaced by a node state drawn uniformly from the pool of ALL runs' node states, every edge
       state by one from the edge pool (seeded): token statistics kept, correspondence to the run destroyed
       (as the "shuffle" mode of hgfm/llm/graph_ablation.py, round 54).
"""
import argparse, torch


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("zero"); ap.add_argument("shuf"); ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(); T = torch.load(a.src); g = torch.Generator().manual_seed(a.seed)
    torch.save({r: {**t, "h": torch.zeros_like(t["h"]), "m": torch.zeros_like(t["m"])} for r, t in T.items()}, a.zero)
    H = torch.cat([t["h"] for t in T.values()]); M = torch.cat([t["m"] for t in T.values() if t["m"].shape[0]])
    out = {}
    for r in sorted(T):
        t = T[r]
        out[r] = {**t, "h": H[torch.randint(len(H), (t["h"].shape[0],), generator=g)].clone(),
                  "m": M[torch.randint(len(M), (t["m"].shape[0],), generator=g)].clone()}
    torch.save(out, a.shuf)
    print(f"{len(T)} runs; node pool {len(H)}, edge pool {len(M)} -> {a.zero}, {a.shuf}")


if __name__ == "__main__":
    main()
