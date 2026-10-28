"""E2 (round 67): per-step mean NLL of a causal LM on the held-out trajectories, on exactly OAT's text and step boundaries.

  python e2_score.py --oat <patched OAT dir> --model <dir> --out <scores.json> [--datasets who_and_when traceelephant_gc] [--device cuda]

For every trajectory: text and step char boundaries from OAT's own `extract_states._build_input_text` (index 0 = the
question, then one entry per history step); token ranges from OAT's `get_step_token_ranges`; NLL of token i =
-log p(token_i | tokens < i); step NLL = mean over the step's tokens (the first token of the text has no NLL and is
skipped). Logits are computed in 2,048-position slices (a 76k-token run would not fit as one [L, vocab] matrix).
Pre-registered length rule: sequences > 32,768 tokens are scored in a second pass with YaRN x4 (both passes, every model).
Rows are also written to <out>.partial after each pass; a rerun resumes from it.
Output: {"model", "rows": [{"id", "dataset", "step_indices", "step_is_model", "step_nll", "mistake_step"}]}.
"""
import argparse, json, os, sys, time
import torch


def load(model_dir, yarn, device):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    kw = {"dtype": torch.bfloat16}
    if yarn:
        kw["rope_scaling"] = {"rope_type": "yarn", "factor": 4.0, "original_max_position_embeddings": 32768}
        kw["max_position_embeddings"] = 131072
    tok = AutoTokenizer.from_pretrained(model_dir)
    m = AutoModelForCausalLM.from_pretrained(model_dir, **kw).to(device).eval()
    return m, tok


@torch.inference_mode()
def step_nll(m, tok, text, bounds, dp, device):
    enc = tok(text, return_tensors="pt", return_offsets_mapping=True)
    ids = enc["input_ids"].to(device); offs = enc["offset_mapping"][0].tolist()
    ranges = dp.get_step_token_ranges(offs, bounds)
    # attention_mask passed exactly as OAT's extraction does: without it SDPA took the math kernel at 76k tokens
    # (an [L, L] matrix, 10.8 GiB) and the YaRN pass ran out of memory (round 67, first run)
    h = m.model(input_ids=ids, attention_mask=enc["attention_mask"].to(device), use_cache=False, return_dict=True).last_hidden_state[0]
    L = ids.shape[1]; nll = torch.zeros(L, dtype=torch.float32, device=device)
    for a in range(0, L - 1, 2048):
        b = min(L - 1, a + 2048)
        lg = m.lm_head(h[a:b]).float()
        nll[a + 1:b + 1] = torch.nn.functional.cross_entropy(lg, ids[0, a + 1:b + 1], reduction="none")
    out = []
    for s, e in ranges:
        s = max(s, 1)
        out.append(float(nll[s:e + 1].mean()) if e >= s else float("nan"))
    return out, L


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--oat"); ap.add_argument("--model"); ap.add_argument("--out")
    ap.add_argument("--datasets", nargs="*", default=["who_and_when", "traceelephant_gc"]); ap.add_argument("--device", default="cuda")
    ap.add_argument("--only_longest", action="store_true", help="smoke test: score only the longest trajectory, write nothing")
    a = ap.parse_args(); sys.path.insert(0, a.oat)
    import data_pipeline as dp, extract_states as ex
    T = []
    for ds in a.datasets:
        for t in dp.load_raw_trajectories(ds):
            t["_ds"] = ds; T.append(t)
    part = a.out + ".partial"
    rows = {} if a.only_longest or not os.path.exists(part) else {r["id"] + r["dataset"]: r for r in json.load(open(part))["rows"]}
    if rows: print(f"resumed {len(rows)} rows from {part}", flush=True)
    if a.only_longest:
        T = [max(T, key=lambda t: len(ex._build_input_text(t)[0]))]
    for yarn in (False, True):
        if a.only_longest is False and all(t["id"] + t["_ds"] in rows for t in T): break
        m, tok = load(a.model, yarn, a.device); t0 = time.time(); n = 0
        for t in T:
            if t["id"] + t["_ds"] in rows: continue
            text, bounds = ex._build_input_text(t)
            L = len(tok(text)["input_ids"])
            if (L > 32768) != yarn: continue
            sn, _ = step_nll(m, tok, text, bounds, dp, a.device); n += 1
            rows[t["id"] + t["_ds"]] = {"id": t["id"], "dataset": t["_ds"], "step_indices": [-1] + list(range(t["num_steps"])),
                                         "step_is_model": [True] + t["step_is_model"], "step_nll": sn,
                                         "mistake_step": t["mistake_step"], "n_tokens": L, "yarn": yarn}
        print(f"yarn={yarn}: scored {n} trajectories in {time.time() - t0:.0f}s, peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)
        del m; torch.cuda.empty_cache()
        if a.only_longest: continue
        json.dump({"model": a.model, "rows": list(rows.values())}, open(part, "w"))   # resume point after each pass
    if a.only_longest:
        print("smoke test ok:", {k: (v["n_tokens"], v["yarn"]) for k, v in rows.items()}); return
    json.dump({"model": a.model, "rows": list(rows.values())}, open(a.out, "w"))
    print(f"{len(rows)} / {len(T)} trajectories -> {a.out}")


if __name__ == "__main__":
    main()
