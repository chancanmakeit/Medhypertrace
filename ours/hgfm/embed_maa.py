"""Embed step outputs, role strings and task queries of the converted MAA corpus (round 33).
Model: sentence-transformers/all-MiniLM-L6-v2 (384-d), max_seq_length 256, CPU.
Excludes mdagents complexity 'basic' runs (single-agent routing, no collaboration).
Outputs <out_dir>/emb.npy (float16) and <out_dir>/index.json {text_sha1: row}.
Usage: python -m ours.hgfm.embed_maa <mas_traj.jsonl> <out_dir>
"""
import json, sys, os, hashlib, time
import numpy as np
def sha(t): return hashlib.sha1(t.encode("utf-8")).hexdigest()
def texts_of(r):
    yield r["task"]["query"][:2000]
    for s in r["steps"]:
        yield (s["output"] or "")[:2000]
        yield f"{s['phase']} | {s['agent_role']}"
def main(src, out):
    os.makedirs(out, exist_ok=True)
    seen, order = set(), []
    for l in open(src):
        r = json.loads(l)
        if r["labels"].get("complexity_level") == "basic": continue
        for t in texts_of(r):
            h = sha(t)
            if h not in seen: seen.add(h); order.append(t)
    print("unique texts", len(order), flush=True)
    from sentence_transformers import SentenceTransformer
    import torch; torch.set_num_threads(2)
    m = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu"); m.max_seq_length = 256
    # sort by length for efficient batching
    idx = sorted(range(len(order)), key=lambda i: len(order[i]))
    E = np.zeros((len(order), 384), dtype=np.float16); t0 = time.time()
    B = 128
    for b in range(0, len(idx), B):
        ii = idx[b:b + B]
        E[ii] = m.encode([order[i] for i in ii], batch_size=B, normalize_embeddings=True, show_progress_bar=False).astype(np.float16)
        if (b // B) % 50 == 0: print(f"{b+len(ii)}/{len(idx)} {time.time()-t0:.0f}s", flush=True)
    np.save(os.path.join(out, "emb.npy"), E)
    json.dump({sha(t): i for i, t in enumerate(order)}, open(os.path.join(out, "index.json"), "w"))
    print("done", time.time() - t0, flush=True)
if __name__ == "__main__": main(sys.argv[1], sys.argv[2])
