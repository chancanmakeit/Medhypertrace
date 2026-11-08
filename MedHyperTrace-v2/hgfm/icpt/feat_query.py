"""Interaction-CPT pre-registration §3 interface (b): full-trajectory post-query step features.

  python -m hgfm.icpt.feat_query --oat <patched OAT dir> --model <dir> --out <features.pt> --data <specs as e4_features>

Same trajectories, serialisation (OAT `_build_input_text`), length rule (<= 32,768 native; <= 131,072 YaRN x4; longer
skipped) and output format as hgfm.e4.e4_features, except the step vector: after the WHOLE trajectory we append, for
every step k = 0..T-1 in order, the string "\n[QUERY STEP k]" and take the final-layer hidden state of the last token of
that query. Each query therefore sees the full trajectory (and the earlier query strings, which carry only step
numbers). Row 0 (question) is zeros, as a placeholder; rows 1..T are the queries. step_ntok / step_has_code keep the
STEP spans' values so that the length control and trivial baselines are identical to interface (a).
Round 101 (layer-18 re-check pre-registration): --layer L takes decoder layer L's output (forward hook, as
hgfm.e4.e4_features --layers) instead of the final-norm state; L = n_layers or no flag = the original behaviour.
"""
import argparse, os, sys, time
import numpy as np
import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from hgfm.e4.e4_features import step_token_ranges, has_code, load, hook_layers, CAP   # noqa: E402


@torch.inference_mode()
def query_feats(m, ids, q_last, H, layer=None):
    h = m.model(input_ids=ids.cuda(), use_cache=False, return_dict=True).last_hidden_state[0]
    if layer is not None and layer < m.config.num_hidden_layers: h = CAP[layer][0]
    out = torch.zeros(len(q_last) + 1, H, dtype=torch.float16)
    out[1:] = h[q_last].float().half().cpu()
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--oat"); ap.add_argument("--model"); ap.add_argument("--out")
    ap.add_argument("--data", nargs="+"); ap.add_argument("--layer", type=int, default=None); a = ap.parse_args()
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
    skipped = {}
    for yarn in (False, True):
        m, tok = load(a.model, yarn); H = m.config.hidden_size; t0 = time.time(); k = 0
        if a.layer is not None: hook_layers(m, [a.layer])
        for t in T:
            key = (t["_ds"], t["id"])
            if key in done: continue
            text, bounds = ex._build_input_text(t)
            nst = len(bounds) - 1
            qs = [f"\n[QUERY STEP {j}]" for j in range(nst)]
            full = text + "".join(qs) + "\n"   # trailing newline: every query's "]" merges into a "]\n" token alike
            enc = tok(full, return_tensors="pt", return_offsets_mapping=True); L = enc["input_ids"].shape[1]
            if L > 131072:
                skipped[f"{key[0]}:{key[1]}"] = L; continue
            if (L > 32768) != yarn: continue
            offs = enc["offset_mapping"][0].tolist()
            # last token of each query string: the token whose span ends at that query's last character
            ends = np.cumsum([len(text)] + [len(q) for q in qs])[1:] - 1
            st = np.array([o[0] for o in offs]); en = np.array([o[1] for o in offs])
            q_last = []
            for e in ends:
                idx = np.nonzero((st <= e) & (en > e))[0]
                q_last.append(int(idx[-1]) if len(idx) else int(np.nonzero(en <= e + 1)[0][-1]))
            ranges = step_token_ranges(offs, bounds)   # STEP spans of the trajectory itself (for ntok / code)
            f = query_feats(m, enc["input_ids"], q_last, H, a.layer); k += 1
            done[key] = {"dataset": t["_ds"], "id": t["id"], "feats": f,
                         "step_ntok": [max(e - s + 1, 0) for s, e in ranges], "step_is_model": [True] + list(t["step_is_model"]),
                         "step_has_code": [has_code(text[b:e + 1]) for b, e in bounds],
                         "mistake_step": t["mistake_step"], "n_tokens": L, "yarn": yarn}
            if k % 200 == 0:
                print(f"yarn={yarn} {k} done, {time.time() - t0:.0f}s", flush=True)
                torch.save({"model": a.model, "rows": list(done.values())}, part)
        print(f"yarn={yarn}: {k} trajectories in {time.time() - t0:.0f}s", flush=True)
        del m; torch.cuda.empty_cache(); torch.save({"model": a.model, "rows": list(done.values())}, part)
    torch.save({"model": a.model, "interface": "full_trajectory_query", "layer": a.layer, "skipped_over_131072": skipped, "rows": list(done.values())}, a.out)
    print(f"{len(done)} / {len(T)} rows, skipped {len(skipped)} -> {a.out}")


if __name__ == "__main__":
    main()
