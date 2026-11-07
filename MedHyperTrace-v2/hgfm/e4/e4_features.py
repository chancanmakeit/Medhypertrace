"""E4 stage A (round 73): per-step features of a frozen proxy LM, on exactly OAT's serialisation and step boundaries.

  python -m hgfm.e4.e4_features --oat <patched OAT dir> --model <dir> --out <features.pt> \
      --data who_and_when traceelephant_gc dir:<Who&When-format dir>[=name] ...

For every trajectory: OAT's `_build_input_text` (question + "[STEP t] ..." blocks) -> one forward pass -> last hidden
state (after the final norm) -> mean over each step's tokens (OAT's `get_step_token_ranges`; index 0 = question).
Pre-registered length rule (as E1): <= 32,768 tokens native, 32,769-131,072 with YaRN x4, longer ones skipped and
counted. Attention: flash-attn 2 (needed for 131k tokens; hidden states match SDPA to cosine 0.99998, round 68).
Output: {"model", "skipped_over_131072": {...}, "rows": [{"dataset", "id", "feats" fp16 [T+1, H], "step_ntok" [T+1],
"step_is_model" [T+1], "step_has_code" [T+1], "mistake_step", "n_tokens", "yarn"}]}; resumable via <out>.partial.
Round 97 (OutcomeCPT amendment A1, gate G0): --layers 9,18,27,36 writes one file per layer, <out> with "_L<l>.pt";
layer l < n_layers = output of decoder layer l (residual stream, before the final norm, captured by a forward hook);
l = n_layers = the final-norm last hidden state, identical to the default (single-layer) output.
"""
import argparse, os, sys, time
import numpy as np
import torch


def step_token_ranges(offsets, bounds):
    """Vectorised equivalent of OAT's data_pipeline.get_step_token_ranges (same rule, checked against it in main)."""
    o = np.asarray(offsets); st, en = o[:, 0], o[:, 1]; valid = ~((st == 0) & (en == 0)); n = len(o); out = []
    for s, e in bounds:
        idx = np.nonzero(valid & (en >= s) & (st <= e))[0]
        out.append((int(idx[0]), int(idx[-1])) if len(idx) else (n - 1, 0))
    return out


has_code = lambda seg: float("```" in seg or "def " in seg or "import " in seg)


def load(model_dir, yarn):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    kw = {"dtype": torch.bfloat16, "attn_implementation": "flash_attention_2"}
    if yarn:
        kw["rope_scaling"] = {"rope_type": "yarn", "factor": 4.0, "original_max_position_embeddings": 32768}
        kw["max_position_embeddings"] = 131072
    return AutoModelForCausalLM.from_pretrained(model_dir, **kw).cuda().eval(), AutoTokenizer.from_pretrained(model_dir)


CAP = {}


def hook_layers(m, layers):
    nl = m.config.num_hidden_layers
    for l in layers:
        if l < nl:
            def f(mod, inp, out, l=l): CAP[l] = out[0] if isinstance(out, tuple) else out
            m.model.layers[l - 1].register_forward_hook(f)


@torch.inference_mode()
def feats(m, enc, ranges, layers=None):
    ids = enc["input_ids"].cuda(); CAP.clear()
    last = m.model(input_ids=ids, use_cache=False, return_dict=True).last_hidden_state[0]
    hs = {None: last} if layers is None else {l: (last if l >= m.config.num_hidden_layers else CAP[l][0]) for l in layers}
    outs = {}; n = []
    for l, h in hs.items():
        out = torch.zeros(len(ranges), h.shape[-1], dtype=torch.float16)
        for j, (s, e) in enumerate(ranges):
            if e >= s: out[j] = h[s:e + 1].float().mean(0).half().cpu()
        outs[l] = out
    n = [max(e - s + 1, 0) for s, e in ranges]
    return (outs[None] if layers is None else outs), n


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--oat"); ap.add_argument("--model"); ap.add_argument("--out")
    ap.add_argument("--data", nargs="+"); ap.add_argument("--layers", default=None, help="e.g. 9,18,27,36 (round 97)")
    a = ap.parse_args(); layers = [int(x) for x in a.layers.split(",")] if a.layers else None
    sys.path.insert(0, a.oat); cwd = os.getcwd(); os.chdir(a.oat)
    import data_pipeline as dp, extract_states as ex
    T = []
    for spec in a.data:
        if spec.startswith("dir:"):
            path, _, name = spec[4:].partition("="); name = name or os.path.basename(path.rstrip("/"))
            rows = dp.load_who_and_when_trajectories(data_dir=os.path.join(cwd, path) if not os.path.isabs(path) else path)
        else:
            name, rows = spec, dp.load_raw_trajectories(spec)
        for t in rows: t["_ds"] = name; T.append(t)
    os.chdir(cwd)
    part = a.out + ".partial"
    done = {(r["dataset"], r["id"]): r for r in torch.load(part, weights_only=False)["rows"]} if os.path.exists(part) else {}
    skipped = {}; n_checked = 0
    for yarn in (False, True):
        m, tok = load(a.model, yarn); t0 = time.time(); k = 0
        if layers: hook_layers(m, layers)
        for t in T:
            key = (t["_ds"], t["id"])
            if key in done: continue
            text, bounds = ex._build_input_text(t)
            enc = tok(text, return_tensors="pt", return_offsets_mapping=True); L = enc["input_ids"].shape[1]
            if L > 131072:
                skipped[f"{key[0]}:{key[1]}"] = L; continue
            if (L > 32768) != yarn: continue
            offs = enc["offset_mapping"][0].tolist(); ranges = step_token_ranges(offs, bounds)
            if n_checked < 20:   # equivalence with OAT's own (slow) implementation on the first 20 trajectories
                assert ranges == [tuple(x) for x in dp.get_step_token_ranges(offs, bounds)], key; n_checked += 1
            f, n = feats(m, enc, ranges, layers); k += 1
            done[key] = {"dataset": t["_ds"], "id": t["id"], "feats": f, "step_ntok": n, "step_is_model": [True] + list(t["step_is_model"]),
                         "step_has_code": [has_code(text[b:e + 1]) for b, e in bounds],
                         "mistake_step": t["mistake_step"], "n_tokens": L, "yarn": yarn}
            if k % 200 == 0:
                print(f"yarn={yarn} {k} done, {time.time() - t0:.0f}s", flush=True)
                torch.save({"model": a.model, "rows": list(done.values())}, part)
        print(f"yarn={yarn}: {k} trajectories in {time.time() - t0:.0f}s", flush=True)
        del m; torch.cuda.empty_cache(); torch.save({"model": a.model, "rows": list(done.values())}, part)
    if layers:
        for l in layers:
            rows = [{**r, "feats": r["feats"][l]} for r in done.values()]
            torch.save({"model": a.model, "layer": l, "skipped_over_131072": skipped, "rows": rows}, a.out.replace(".pt", f"_L{l}.pt"))
    else:
        torch.save({"model": a.model, "skipped_over_131072": skipped, "rows": list(done.values())}, a.out)
    print(f"{len(done)} / {len(T)} rows, skipped {len(skipped)} -> {a.out} layers={layers}")


if __name__ == "__main__":
    main()
