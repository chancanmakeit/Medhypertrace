"""Encode every acting step's content with a sentence-embedding model and cache to
data/emb_cache/{model_tag}/{framework}.npz keyed by (traj_id, turn, content-hash).
Run once per model; the HGNN then loads vectors from the cache instead of TF-IDF.

Models (--model):
  mxbai   mixedbread-ai/mxbai-embed-xsmall-v1  (384-d, fast on CPU, ~22 texts/s)
  nomic   nomic-ai/nomic-embed-text-v1.5       (768-d, needs trust_remote_code)
  <path or HF id>                              (any SentenceTransformer)

Device: defaults to 'auto' -> cuda if available else cpu. Override with --device.
Chunked with resume: rerun to continue an interrupted encode (EMB_CHUNK env var).
"""
import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)

import argparse
import hashlib
import os

import numpy as np

from common.data import load_jsonl
from common.paths import FILES, REPO_ROOT

# model tag -> (hf id or path, needs_trust_remote_code, doc prefix, dim)
MODELS = {
    "mxbai": ("mixedbread-ai/mxbai-embed-xsmall-v1", False, "", 384),
    "nomic": (os.environ.get("NOMIC_PATH", "nomic-ai/nomic-embed-text-v1.5"),
              True, "search_document: ", 768),
}
DEFAULT_MODEL = "mxbai"


def resolve_model(tag):
    if tag in MODELS:
        return (tag,) + MODELS[tag]
    safe = tag.rstrip("/").split("/")[-1].replace(".", "_")
    return (safe, tag, True, "", None)


def pick_device(device="auto"):
    if device != "auto":
        return device
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def cache_dir(model_tag):
    return os.path.join(REPO_ROOT, "data", "emb_cache", model_tag)


def cache_path(model_tag, name):
    return os.path.join(cache_dir(model_tag), f"{name}.npz")


def key_of(traj_id, step):
    h = hashlib.md5(step.content.encode()).hexdigest()[:12]
    return f"{traj_id}||{step.turn}||{h}"


def build(name, path, model_tag="mxbai", device="auto", maxlen=512, batch=32):
    tag, mid, trc, prefix, _ = resolve_model(model_tag)
    os.makedirs(cache_dir(tag), exist_ok=True)
    out = cache_path(tag, name)
    if os.path.exists(out):
        print(f"[{name}] cache exists: {out}")
        return
    dev = pick_device(device)
    from sentence_transformers import SentenceTransformer
    kw = {"trust_remote_code": True} if trc else {}
    model = SentenceTransformer(mid, device=dev, **kw)
    model.max_seq_length = maxlen

    trajs = load_jsonl(path)
    keys, texts = [], []
    for t in trajs:
        for s in t.steps:
            if s.is_input:
                continue
            keys.append(key_of(t.id, s))
            texts.append(prefix + s.content)

    part = out + ".part.npy"
    done, prev = 0, None
    if os.path.exists(part):
        prev = np.load(part)
        done = prev.shape[0]
        print(f"[{name}] resuming from {done}/{len(texts)}")
    CHUNK = int(os.environ.get("EMB_CHUNK", "1000000"))
    todo = texts[done:done + CHUNK]
    print(f"[{name}] encoding {len(todo)} of {len(texts)} on {dev} (model={tag}) ...")
    new = model.encode(todo, batch_size=batch, normalize_embeddings=True,
                       show_progress_bar=False).astype(np.float32)
    emb = new if prev is None else np.concatenate([prev, new], 0)
    if emb.shape[0] < len(texts):
        np.save(part, emb)
        print(f"[{name}] partial {emb.shape[0]}/{len(texts)} — rerun to continue")
    else:
        np.savez_compressed(out, keys=np.array(keys), emb=emb)
        if os.path.exists(part):
            os.remove(part)
        print(f"[{name}] COMPLETE {out} shape={emb.shape}")


def load_cache(name, model_tag=DEFAULT_MODEL):
    tag = resolve_model(model_tag)[0]
    d = np.load(cache_path(tag, name), allow_pickle=False)
    return {k: i for i, k in enumerate(d["keys"])}, d["emb"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", default="all")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--maxlen", type=int, default=512)
    ap.add_argument("--batch", type=int, default=32)
    args = ap.parse_args()
    targets = FILES if args.target == "all" else {args.target: FILES[args.target]}
    for n, p in targets.items():
        build(n, p, args.model, args.device, args.maxlen, args.batch)
