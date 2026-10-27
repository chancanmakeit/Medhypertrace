"""Featurise SAMT runs into HGFM v0.2 encoder inputs (round 64), on GPU with the same MiniLM as the MAA cache.

  python -m hgfm.midtrain.samt_featurise build  <runs.jsonl.gz> <out.pkl> --minilm <dir>
  python -m hgfm.midtrain.samt_featurise verify <maa_mas_traj.jsonl> <graphs_v02_gold0.pkl> --minilm <dir> [--n 300]

`build` writes {run_id: featurised run} (hgfm.midtrain.samt_graph.featurise). Node texts are embedded once, rounded to
fp16 like the MAA table (hgfm.embed_maa: max_seq_length 256, normalised); edge / relation / framework texts in fp32 like
TextEmb. `verify` featurises MAA runs with this code and compares them with the MAA cache the SFT encoder was trained on:
the node features, task vector and edge inputs must agree (up to fp16 rounding of GPU vs CPU MiniLM), otherwise SAMT
would train on a different feature space than the one it is exported to.
"""
import argparse, gzip, json, pickle, sys, time
import numpy as np


class Embedder:
    def __init__(self, path, device="cuda"):
        from sentence_transformers import SentenceTransformer
        self.m = SentenceTransformer(path, device=device); self.m.max_seq_length = 256
        self.node, self.text = {}, {}

    def fit(self, node_texts, other_texts):
        for store, texts, half in ((self.node, node_texts, True), (self.text, other_texts, False)):
            new = sorted({t for t in texts if t not in store}, key=len)
            t0 = time.time()
            for b in range(0, len(new), 4096):
                part = new[b:b + 4096]
                V = self.m.encode(part, batch_size=256, normalize_embeddings=True, show_progress_bar=False)
                V = V.astype(np.float16).astype(np.float32) if half else V.astype(np.float32)
                store.update(zip(part, V))
            print(f"embedded {len(new)} {'node' if half else 'edge/text'} texts in {time.time() - t0:.0f}s", flush=True)

    def node_emb(self, t):
        return self.node[t]

    def text_emb(self, ts):
        return np.stack([self.text[t] for t in ts]) if ts else np.zeros((0, 384), np.float32)


def read(p):
    with (gzip.open if p.endswith(".gz") else open)(p, "rt", encoding="utf-8") as f:
        for l in f:
            if l.strip():
                yield json.loads(l)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("mode", choices=["build", "verify"]); ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--minilm", required=True); ap.add_argument("--n", type=int, default=300); ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    from hgfm.midtrain.samt_graph import featurise, node_texts, edge_texts
    if a.mode == "build":
        runs = list(read(a.src))
    else:
        cache = pickle.load(open(a.out, "rb")); by = {g["run_id"]: g for g in cache}; runs = []
        for r in read(a.src):
            if r["run_id"] in by: runs.append(r)
            if len(runs) >= a.n: break
    E = Embedder(a.minilm, a.device)
    E.fit([t for r in runs for t in node_texts(r)], [t for r in runs for t in edge_texts(r)])
    G = {r["run_id"]: featurise(r, E.node_emb, E.text_emb) for r in runs}
    G = {k: v for k, v in G.items() if v is not None}
    if a.mode == "build":
        pickle.dump(G, open(a.out, "wb"), protocol=4)
        print(f"{len(G)} runs, {sum(g['X'].shape[0] for g in G.values())} steps, "
              f"{sum(len(g['e_rel']) for g in G.values())} hyperedges -> {a.out}")
        return
    worst = {"X_emb": 0.0, "X_scal": 0.0, "q": 0.0, "e_instr": 0.0, "r_txt": 0.0}; struct_bad = 0
    for k, g in G.items():
        o = by[k]
        worst["X_emb"] = max(worst["X_emb"], float(np.abs(g["X"][:, :768] - o["X"][:, :768]).max()))
        worst["X_scal"] = max(worst["X_scal"], float(np.abs(g["X"][:, 768:] - o["X"][:, 768:]).max()))
        worst["q"] = max(worst["q"], float(np.abs(g["q"] - o["q"]).max()))
        if len(g["e_rel"]):
            worst["e_instr"] = max(worst["e_instr"], float(np.abs(g["e_instr"] - o["e_instr"]).max()))
            worst["r_txt"] = max(worst["r_txt"], float(np.abs(g["r_txt"] - o["r_txt"]).max()))
        struct_bad += (g["e_inc"] != o["e_inc"]) or (g["e_rel"] != o["e_rel"]) or (sorted(g["r_links"]) != sorted(o["r_links"])) \
            or g["X"].shape != o["X"].shape
    print(f"verified {len(G)} MAA runs; structural mismatches {struct_bad}; max |diff| {json.dumps({k: round(v, 5) for k, v in worst.items()})}")
    ok = struct_bad == 0 and worst["X_scal"] == 0 and max(worst["X_emb"], worst["q"]) < 5e-3 and max(worst["e_instr"], worst["r_txt"]) < 1e-3
    print("VERIFY", "OK" if ok else "FAIL"); sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
