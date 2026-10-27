"""Export MAA graph tokens with a SAMT encoder (round 64).

  python -m hgfm.midtrain.samt_export <samt_ckpt_dir> <maa graphs_v02_gold0.pkl> <out graph_tokens_samt.pt> [--check F.pt ...]

The SAMT encoder never saw MedAgentAudit data, so ONE token file serves every fold (strict zero-shot for all of them).
Output has the graph_tokens.pt layout read by hgfm.llm.model.graph_vectors / the swift plugin:
{run_id: {"h": fp16 [n_steps, 192], "m": fp16 [n_edges, 192], "split": "all"}}. Node order = steps, edge order =
hgfm.data_v02.edges_of (the order the existing sft_graph prompts reference). --check compares, for every run of an
existing per-fold graph_tokens.pt, the number of node and edge vectors (the prompts' graph_refs index into them).
"""
import argparse, pickle, torch
from hgfm.midtrain.samt_model import GraphEncoder
from hgfm.midtrain.samt_graph import collate_graphs, to_device


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ckpt"); ap.add_argument("graphs"); ap.add_argument("out")
    ap.add_argument("--check", nargs="*", default=[]); ap.add_argument("--device", default="cuda"); ap.add_argument("--bs", type=int, default=256)
    a = ap.parse_args()
    enc = GraphEncoder(); enc.load_state_dict(torch.load(f"{a.ckpt}/encoder.pt", map_location="cpu")); enc.to(a.device).eval()
    G = pickle.load(open(a.graphs, "rb")); G = list(G.values()) if isinstance(G, dict) else G
    out = {}
    with torch.no_grad():
        for b in range(0, len(G), a.bs):
            part = G[b:b + a.bs]; B, vo, eo = collate_graphs(part); h, m = enc(to_device(B, a.device))
            h, m = h.float().cpu(), m.float().cpu()
            for k, g in enumerate(part):
                n, ne = g["X"].shape[0], len(g["e_rel"])
                out[g["run_id"]] = {"h": h[vo[k]:vo[k] + n].half(), "m": m[eo[k]:eo[k] + ne].half(), "split": "all"}
    torch.save(out, a.out)
    print(f"{len(out)} runs -> {a.out}")
    for p in a.check:
        T = torch.load(p); bad = [r for r, t in T.items() if r not in out or out[r]["h"].shape[0] != t["h"].shape[0] or out[r]["m"].shape[0] != t["m"].shape[0]]
        print(f"check {p}: {len(T)} runs, shape mismatches {len(bad)}")
        if bad: raise SystemExit(f"mismatch, e.g. {bad[:3]}")


if __name__ == "__main__":
    main()
