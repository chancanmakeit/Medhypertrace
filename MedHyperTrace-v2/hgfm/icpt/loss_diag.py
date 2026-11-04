"""Interaction-CPT pre-registration §6.1 (amendment A3): zero-training loss diagnostic, base vs tapt_clean.

  python -m hgfm.icpt.loss_diag run --runs <parents_mastraj/*.jsonl.gz ...> --models base=<dir> tapt_clean=<dir> --out <jsonl>
  python -m hgfm.icpt.loss_diag analyse --inp <jsonl> --out <json>

Estimand (GPT, medical-aegis #4): the conditional NLL of the SAME target tokens (a step's output) under three input
renderings, per model:
  (a) tapt   -- the TAPT corpus format (build_corpus): task header + "[s<k>] role | phase\\n<output>" blocks of the earlier steps
  (b) oat    -- the OAT / E4 read-out format: "Question: <q> Trajectory: " + "[STEP i] [ROLE: assistant] [AGENT: name]\\n<content>\\n\\n"
  (c) recv   -- the receiver-conditioned chat format of the interaction arm (system role line, user = task + read set)
Target ids are tokenised once and appended to each separately tokenised context, so they are identical across formats.
Context = everything before the target (left-truncated to 4,096 - target); target <= 512 tokens. Header tokens of the
target step (the format-specific line right before the target) are scored separately ("template NLL").
Sample (A3): the eval_v3 parents of the four seen frameworks (gemini; in no training corpus; labels unused), 60 runs per
framework (seed 0), up to 6 LLM steps per run with recorded sources.
analyse: per-step mean NLL per token -> per run -> Delta_f = NLL(base, f) - NLL(tapt_clean, f); D = Delta_a - Delta_b;
question-clustered bootstrap (1,000).
"""
import argparse, glob, gzip, json, random
import numpy as np

FW = ("llm_debate", "mdagents", "medagents_mc", "mac_groupchat")


def who(s): return s.get("agent_role") or s.get("agent_id") or "agent"


def sample(paths, per_fw, seed):
    rng = random.Random(seed); runs = {}
    for p in paths:
        for l in gzip.open(p, "rt", encoding="utf-8"):
            r = json.loads(l)
            if r["framework"] in FW and r["run_id"] not in runs: runs[r["run_id"]] = r
    out = []
    for fw in FW:
        rs = sorted((r for r in runs.values() if r["framework"] == fw), key=lambda r: r["run_id"]); rng.shuffle(rs); out += rs[:per_fw]
    return out


def contexts(r, t):
    steps = r["steps"]; s = steps[t]; q = (r["task"].get("query") or "").strip()
    from data_tools.public_to_mas_traj.common import add_phase_canonical
    ph = lambda x: x.get("phase_canonical") or x.get("phase")
    a_prev = "".join(f"[{x['step_id']}] {who(x)} | {ph(x)}\n{(x.get('output') or '').strip()}\n\n" for x in steps[:t])
    a = (f"Task ({r['task'].get('dataset')}, framework {r['framework']}):\n{q}\n\n" + a_prev, f"[{s['step_id']}] {who(s)} | {ph(s)}\n")
    b_prev = "".join(f"[STEP {i}] [ROLE: {'assistant' if x['kind'] == 'llm' else 'user'}] [AGENT: {who(x) if x['kind'] == 'llm' else 'Computer_terminal'}]\n"
                     f"{(x.get('output') or '').strip()}\n\n" for i, x in enumerate(steps[:t]))
    b = (f"Question: {q} Trajectory: " + b_prev, f"[STEP {t}] [ROLE: assistant] [AGENT: {who(s)}]\n")
    src = [x["step_id"] for x in (s.get("sources") or [])]; byid = {x["step_id"]: x for x in steps}
    msgs = "\n\n".join(f"[{k}] {who(byid[k])} | {ph(byid[k])}:\n{(byid[k].get('output') or '').strip()}" for k in src if k in byid)
    sysm = f"You are {who(s)} ({s.get('agent_label') or s.get('agent_id')}) in the {r['framework']} multi-agent system. Phase: {ph(s)}" + \
           (f", round {s['round']}" if s.get("round") is not None else "") + "."
    user = f"Task ({r['task'].get('dataset')}):\n{q}" + ("\n\nMessages visible to you:\n\n" + msgs if msgs else "\n\n(No earlier messages are visible to you.)")
    c = ({"system": sysm, "user": user}, None)
    return {"tapt": a, "oat": b, "recv": c}


def cmd_run(a):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    runs = sample(a.runs, a.per_fw, a.seed); models = dict(x.split("=", 1) for x in a.models)
    tok = AutoTokenizer.from_pretrained(next(iter(models.values()))); rng = random.Random(a.seed)
    from data_tools.public_to_mas_traj.common import add_phase_canonical
    items = []
    for r in runs:
        r = add_phase_canonical(r)
        ts = [i for i, s in enumerate(r["steps"]) if s["kind"] == "llm" and (s.get("output") or "").strip() and s.get("sources") is not None]
        for t in sorted(rng.sample(ts, min(a.steps, len(ts)))):
            tgt = tok(r["steps"][t]["output"].strip(), add_special_tokens=False)["input_ids"][: a.max_target]
            ctx = {}
            for f, (pre, head) in contexts(r, t).items():
                if f == "recv":
                    s = tok.apply_chat_template([{"role": "system", "content": pre["system"]}, {"role": "user", "content": pre["user"]}],
                                                tokenize=False, add_generation_prompt=True, enable_thinking=False)
                    hid = tok(s, add_special_tokens=False)["input_ids"]; n_head = len(tok("<think>\n\n</think>\n\n", add_special_tokens=False)["input_ids"]) + 3
                else:
                    pid = tok(pre, add_special_tokens=False)["input_ids"]; h = tok(head, add_special_tokens=False)["input_ids"]
                    hid = pid + h; n_head = len(h)
                room = a.max_len - len(tgt)
                if len(hid) > room: hid = hid[-room:]
                ctx[f] = (hid, n_head)
            items.append({"run_id": r["run_id"], "q": r["question_id"], "fw": r["framework"], "step_id": r["steps"][t]["step_id"], "tgt": tgt, "ctx": ctx})
    print(f"{len(runs)} runs, {len(items)} target steps", flush=True)
    res = {i: {"run_id": it["run_id"], "q": it["q"], "fw": it["fw"], "step_id": it["step_id"], "n_tgt": len(it["tgt"])} for i, it in enumerate(items)}
    for name, path in models.items():
        m = AutoModelForCausalLM.from_pretrained(path, dtype=torch.bfloat16, attn_implementation="flash_attention_2").cuda().eval()
        with torch.inference_mode():
            for i, it in enumerate(items):
                for f, (hid, n_head) in it["ctx"].items():
                    ids = torch.tensor([hid + it["tgt"]], device="cuda")
                    lp = torch.log_softmax(m(input_ids=ids).logits[0, :-1].float(), -1)
                    nll = -lp.gather(1, ids[0, 1:, None])[:, 0]
                    L = len(hid); res[i][f"{name}/{f}/tgt"] = float(nll[L - 1:].mean()); res[i][f"{name}/{f}/head"] = float(nll[L - 1 - n_head:L - 1].mean())
                if i % 200 == 0: print(name, i, flush=True)
        del m; torch.cuda.empty_cache()
    with open(a.out, "w") as fo:
        for v in res.values(): fo.write(json.dumps(v) + "\n")


def boot(d, q, B=1000):
    d = np.asarray(d); q = np.asarray(q); u = np.unique(q); idx = [np.nonzero(q == x)[0] for x in u]; rng = np.random.default_rng(0)
    s = np.array([d[i].sum() for i in idx]); c = np.array([len(i) for i in idx])
    bs = [s[p].sum() / c[p].sum() for p in (rng.integers(0, len(u), len(u)) for _ in range(B))]
    return {"mean": float(d.mean()), "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], "n": int(len(d)), "n_q": int(len(u))}


def cmd_analyse(a):
    rows = [json.loads(l) for l in open(a.inp)]; models = sorted({k.split("/")[0] for k in rows[0] if k.count("/") == 2}); out = {}
    b, t = ("base", "tapt_clean") if "tapt_clean" in models else models[:2]
    per_run = {}
    for r in rows: per_run.setdefault(r["run_id"], []).append(r)
    runs = list(per_run); q = [per_run[k][0]["q"] for k in runs]
    m = lambda key: [float(np.mean([x[key] for x in per_run[k]])) for k in runs]
    for f in ("tapt", "oat", "recv"):
        for part in ("tgt", "head"):
            out[f"nll/{b}/{f}/{part}"] = boot(m(f"{b}/{f}/{part}"), q); out[f"nll/{t}/{f}/{part}"] = boot(m(f"{t}/{f}/{part}"), q)
            out[f"Delta/{f}/{part}"] = boot(np.array(m(f"{b}/{f}/{part}")) - np.array(m(f"{t}/{f}/{part}")), q)
    for x, y in (("tapt", "oat"), ("tapt", "recv"), ("oat", "recv")):
        d = (np.array(m(f"{b}/{x}/tgt")) - np.array(m(f"{t}/{x}/tgt"))) - (np.array(m(f"{b}/{y}/tgt")) - np.array(m(f"{t}/{y}/tgt")))
        out[f"D/{x}-{y}"] = boot(d, q)
    json.dump(out, open(a.out, "w"), indent=1)
    for k, v in out.items(): print(f"{k:28s} {v['mean']:+.4f} [{v['ci95'][0]:+.4f}, {v['ci95'][1]:+.4f}] n={v['n']} q={v['n_q']}")


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run"); r.add_argument("--runs", nargs="+"); r.add_argument("--models", nargs="+"); r.add_argument("--out")
    r.add_argument("--per_fw", type=int, default=60); r.add_argument("--steps", type=int, default=6); r.add_argument("--seed", type=int, default=0)
    r.add_argument("--max_target", type=int, default=512); r.add_argument("--max_len", type=int, default=4096)
    s = sp.add_parser("analyse"); s.add_argument("--inp"); s.add_argument("--out")
    a = ap.parse_args(); cmd_run(a) if a.cmd == "run" else cmd_analyse(a)


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    main()
