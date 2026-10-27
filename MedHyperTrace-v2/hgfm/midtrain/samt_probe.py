"""Pre-SFT check of SAMT (round 64): does the frozen LLM read the graph tokens?

  python -m hgfm.midtrain.samt_probe --lm <Qwen3-8B dir> --ckpt <samt ckpt dir> --cache <graph cache pkl>
         --probe probe.jsonl --out probe_result.json [--conds real,shuffle,zero,untrained] [--bs 8] [--max_len 3072]

On held-out runs (never trained on), per objective: teacher-forced exact match of the answer (every answer token incl.
eos is the argmax = greedy decoding reproduces the answer) and mean answer NLL, under
  real       the run's own graph tokens (as in training)
  shuffle    every placeholder gets the state of a random node / edge of ANOTHER held-out run (same kind): the text is
             unchanged, so this is what the model can do from the text alone once trained with graph tokens
  zero       graph state set to 0 (flag kept)
  untrained  freshly initialised encoder + projector (seed 0): text + uninformative tokens before SAMT
Paired bootstrap (1000) of real - shuffle per objective and per dataset (data-source identifiability, round 61).
"""
import argparse, json, pickle, random, collections
import numpy as np, torch


def main():
    ap = argparse.ArgumentParser()
    for k in ("lm", "ckpt", "cache", "probe", "out"): ap.add_argument("--" + k)
    ap.add_argument("--conds", default="real,shuffle,zero,untrained"); ap.add_argument("--bs", type=int, default=8); ap.add_argument("--max_len", type=int, default=3072); ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from hgfm.llm.model import GRAPH_TOKEN
    from hgfm.midtrain.samt_model import GraphEncoder, graph_states, batch_graph
    from hgfm.midtrain.samt_graph import to_device
    tok = AutoTokenizer.from_pretrained(a.lm)
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    tok.add_special_tokens({"additional_special_tokens": [GRAPH_TOKEN]}); gid = tok.convert_tokens_to_ids(GRAPH_TOKEN)
    dt = torch.bfloat16 if a.device != "cpu" else torch.float32; D = a.device
    lm = AutoModelForCausalLM.from_pretrained(a.lm, dtype=dt).to(D).eval(); lm.resize_token_embeddings(len(tok))
    H = lm.config.hidden_size
    def modules(trained):
        torch.manual_seed(0)
        enc = GraphEncoder(); proj = torch.nn.Sequential(torch.nn.Linear(194, H), torch.nn.ReLU(), torch.nn.Linear(H, H)).to(dt)
        if trained:
            enc.load_state_dict(torch.load(f"{a.ckpt}/encoder.pt", map_location="cpu")); proj.load_state_dict(torch.load(f"{a.ckpt}/projector.pt", map_location="cpu"))
        return enc.to(D).eval(), proj.to(D).eval()
    cache = pickle.load(open(a.cache, "rb"))
    P = [json.loads(l) for l in open(a.probe)]
    rows = []
    for p in P:
        m = p["messages"]; refs = json.loads(p["graph_refs"])
        prompt = tok.apply_chat_template(m[:2], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        pi = tok(prompt, add_special_tokens=False)["input_ids"]; ai = tok(m[2]["content"] + tok.eos_token, add_special_tokens=False)["input_ids"]
        if len(pi) + len(ai) > a.max_len: pi = pi[-(a.max_len - len(ai)):]
        n_ph = sum(t == gid for t in pi); refs = refs[-n_ph:] if n_ph else []
        rows.append({"obj": p["obj"], "dataset": p["dataset"], "run": p["run_id"], "pi": pi, "ai": ai, "refs": refs})
    runs = sorted({r["run"] for r in rows}); rng = random.Random(0)
    def refs_for(r, cond):
        if cond in ("real", "zero", "untrained"): return r["run"], r["refs"]
        other = rng.choice([x for x in runs if x != r["run"] and len(cache[x]["e_rel"]) > 0])
        g = cache[other]; n, ne = g["X"].shape[0], len(g["e_rel"])
        return other, [[k, rng.randrange(n) if k == "node" else rng.randrange(ne)] for k, _ in r["refs"]]
    res = collections.defaultdict(dict)
    for cond in a.conds.split(","):
        enc, proj = modules(cond != "untrained"); rng.seed(0)
        for b in range(0, len(rows), a.bs):
            part = rows[b:b + a.bs]; L = max(len(r["pi"]) + len(r["ai"]) for r in part)
            ids = torch.full((len(part), L), tok.pad_token_id); att = torch.zeros(len(part), L, dtype=torch.long)
            for i, r in enumerate(part):
                s = r["pi"] + r["ai"]; ids[i, :len(s)] = torch.tensor(s); att[i, :len(s)] = 1
            ids, att = ids.to(D), att.to(D)
            with torch.no_grad():
                emb = lm.get_input_embeddings()(ids)
                rr = [refs_for(r, cond) for r in part]; keep = [i for i, (_, f) in enumerate(rr) if f]
                if keep:
                    gb = batch_graph([rr[i][0] for i in keep], [rr[i][1] for i in keep], cache)
                    vec = graph_states(enc, to_device(gb["samt_graph"], D), gb["samt_kind"].to(D), gb["samt_idx"].to(D))
                    if cond == "zero": vec[:, :-2] = 0
                    emb = emb.clone(); emb[ids == gid] = proj(vec.to(dt))
                hid = lm.model(inputs_embeds=emb, attention_mask=att).last_hidden_state   # logits only at answer positions (memory)
            for i, r in enumerate(part):
                s0 = len(r["pi"]); tgt = torch.tensor(r["ai"]).to(D)
                with torch.no_grad(): lg = lm.lm_head(hid[i, s0 - 1:s0 - 1 + len(r["ai"])]).float()
                nll = torch.nn.functional.cross_entropy(lg, tgt).item(); em = bool((lg.argmax(-1) == tgt).all())
                res[cond][b + i] = (em, nll)
        print(cond, "EM", round(np.mean([v[0] for v in res[cond].values()]), 3), flush=True)
    out = {"n": len(rows), "per_obj": {}, "per_dataset": {}}
    bs_rng = np.random.default_rng(0)
    def summ(idx):
        d = {c: {"em": float(np.mean([res[c][i][0] for i in idx])), "nll": float(np.mean([res[c][i][1] for i in idx]))} for c in res}
        if "real" in res and "shuffle" in res:
            diff = np.array([res["real"][i][0] - res["shuffle"][i][0] for i in idx], dtype=float)
            boots = [diff[bs_rng.integers(0, len(diff), len(diff))].mean() for _ in range(1000)]
            d["real_minus_shuffle_em"] = [float(diff.mean()), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
        d["n"] = len(idx); return d
    for o in sorted({r["obj"] for r in rows}):
        out["per_obj"][o] = summ([i for i, r in enumerate(rows) if r["obj"] == o])
    for o, ds in sorted({(r["obj"], r["dataset"]) for r in rows}):
        idx = [i for i, r in enumerate(rows) if r["obj"] == o and r["dataset"] == ds]
        if len(idx) >= 10: out["per_dataset"][f"{o}/{ds}"] = summ(idx)
    out["rows"] = [{"obj": r["obj"], "dataset": r["dataset"], "run": r["run"], **{c: res[c][i] for c in res}} for i, r in enumerate(rows)]
    json.dump(out, open(a.out, "w"), indent=1)
    for o, d in out["per_obj"].items():
        print(o, "n", d["n"], " ".join(f"{c}={d[c]['em']:.3f}" for c in res), "real-shuffle", [round(x, 3) for x in d.get("real_minus_shuffle_em", [])])


if __name__ == "__main__":
    main()
