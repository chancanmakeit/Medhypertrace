"""Interaction-CPT pre-registration §2: the two CPT arms' training files, built from ONE set of runs.

  python -m hgfm.icpt.build_icpt --runtime <mas-traj files with runtime read sets ...> --public_dir <mas_traj dir>
      --eval_parents <eval_v3 dir>/parents_mastraj --out_dir <dir> [--budget_m 40] [--seed 0]

Runs
  * runtime (M-new + M-anchor): mas-traj normal runs whose sources are runtime-collected. Interaction samples only from
    --interaction_frameworks (amendment A2: framework-level read-set gap rate < 1%; dylan is LM text only).
  * public (P): the 7 public datasets, LM text only. Stage-0 `full` rules: drop framework_family groupchat and the
    whole who_and_when dataset (evaluation), MAA exclusion list (exact stem), and any run whose question has word-set
    Jaccard >= 0.3 with a WW / TEgc evaluation question.
  * every run (runtime or public) whose question has Jaccard >= 0.3 with any medical evaluation parent (all eval_v3
    parents: text, multimodal, triage, MAM) is dropped; held-out frameworks (agentverse, triage_agent, mam) are dropped.
Arms (processed tokens = every token the model reads; Qwen3 tokenizer)
  lm.jsonl    {"text"}: rendered runs (build_corpus format: task header + "[s<k>] role | phase" blocks, environment / tool
              outputs truncated head+tail to 2,000 chars, chunks <= 4,096 tokens at step boundaries).
              Medical runtime runs first (all of them), then public chunks in a fixed random order until the budget.
  icpt.jsonl  {"messages"}: (1) receiver-conditioned response, (2) evidence correspondence, sampled per step (seed) to the
              SAME processed tokens as lm.jsonl's medical part (3 : 1 by tokens), then (3) the IDENTICAL public chunks as
              replay ({"user": fixed prompt, "assistant": chunk}).
Outputs also stats.json (tokens per part, effective target tokens, exclusions) and manifest.json (run ids per arm part).
"""
import argparse, glob, gzip, json, os, random, re, sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from data_tools.maa_exclusion import norm_stem   # noqa: E402
from data_tools.public_to_mas_traj.common import add_phase_canonical   # noqa: E402

WORD = re.compile(r"[a-z0-9]+")
HELD_OUT = {"agentverse", "triage_agent", "mam"}
REPLAY_PROMPT = "Continue the multi-agent trajectory."


def read(p):
    with (gzip.open if p.endswith(".gz") else open)(p, "rt", encoding="utf-8") as f:
        for l in f:
            if l.strip(): yield json.loads(l)


def stem(q):
    """Question stem: MedXpertQA-style queries carry '\n\nOptions:' + answer list + instruction; only the stem is compared
    (project rule: stem normalisation + word-set Jaccard >= 0.3). Queries without that marker are used whole."""
    q = q or ""; i = q.find("\n\nOptions:")
    return q[:i] if i > 0 else q


def words(q): return frozenset(WORD.findall(stem(q).lower()))


class JaccardIndex:
    def __init__(self, sets):
        self.sets = [s for s in sets if s]; self.inv = defaultdict(list)
        for i, s in enumerate(self.sets):
            for w in s: self.inv[w].append(i)

    def hit(self, q, thr=0.3):
        if not q: return False
        cnt = Counter(i for w in q for i in self.inv.get(w, ()))
        return any(c / (len(q) + len(self.sets[i]) - c) >= thr for i, c in cnt.items())


def trunc(t, n):
    t = t or ""
    return t if len(t) <= n else t[: n // 2] + "\n[...]\n" + t[-n // 2:]


def step_text(s, env_chars):
    out = s.get("output") or ""
    if s["kind"] != "llm": out = trunc(out, env_chars)
    if not out.strip() and s.get("tool_calls"):
        out = json.dumps([{"name": t.get("name"), "arguments": t.get("arguments")} for t in s["tool_calls"]], ensure_ascii=False)[:env_chars]
    return out.strip()


def who(s): return s.get("agent_role") or s.get("agent_id") or "agent"


def render_chunks(r, ntok, tok, max_tokens, env_chars):
    head = f"Task ({r['task'].get('dataset')}, framework {r['framework']}):\n{(r['task'].get('query') or '').strip()}\n"
    ht = ntok(head); budget = max_tokens - ht - 8; chunks, cur, ct = [], [], 0
    for s in r["steps"]:
        b = f"[{s['step_id']}] {who(s)} | {s.get('phase_canonical')}\n{step_text(s, env_chars)}\n"; bt = ntok(b)
        if bt > budget: b = tok.decode(tok(b, add_special_tokens=False)["input_ids"][:budget]); bt = budget
        if ct + bt > budget and cur: chunks.append(head + "\n" + "\n".join(cur)); cur, ct = [], 0
        cur.append(b); ct += bt
    if cur: chunks.append(head + "\n" + "\n".join(cur))
    return chunks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime", nargs="+"); ap.add_argument("--public_dir"); ap.add_argument("--eval_parents"); ap.add_argument("--out_dir")
    ap.add_argument("--budget_m", type=float, default=40.0); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--interaction_frameworks", nargs="*", default=["llm_debate", "mdagents", "medagents_mc", "mac_groupchat"],
                    help="amendment A2: frameworks whose known read-set gap rate is < 1%% (medical-aegis v3 branch evidence); "
                         "dylan (221/350) is LM text only")
    ap.add_argument("--max_tokens", type=int, default=4096)
    ap.add_argument("--env_chars", type=int, default=2000); ap.add_argument("--tokenizer", default="Qwen/Qwen3-8B")
    ap.add_argument("--maa_exclusion", default=os.path.join(os.path.dirname(__file__), "..", "..", "docs", "interfaces", "maa_exclusion_v1.json"))
    a = ap.parse_args(); os.makedirs(a.out_dir, exist_ok=True); rng = random.Random(a.seed)
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.tokenizer); ntok = lambda s: len(tok(s, add_special_tokens=False)["input_ids"])
    chat_ntok = lambda msgs: ntok(tok.apply_chat_template(msgs, tokenize=False))
    st = defaultdict(Counter)

    # ---- exclusion sets
    med_eval = [words(r["task"].get("query")) for p in glob.glob(os.path.join(a.eval_parents, "*.jsonl.gz")) for r in read(p)]
    pub_eval = [words(r["task"].get("query")) for p in glob.glob(os.path.join(a.public_dir, "who_and_when.jsonl.gz")) for r in read(p)]
    pub_eval += [words(r["task"].get("query")) for p in glob.glob(os.path.join(a.public_dir, "traceelephant.jsonl.gz")) for r in read(p)
                 if r["framework_family"] == "groupchat"]
    J_med, J_pub = JaccardIndex(med_eval), JaccardIndex(pub_eval)
    maa = {e["norm_stem"] for e in json.load(open(a.maa_exclusion))["entries"]}

    def keep(r, ds, public):
        q = r["task"].get("query") or ""; w = words(q)
        if r.get("run_mode") != "normal": st[ds]["not_normal"] += 1; return False
        if r["framework"] in HELD_OUT: st[ds]["held_out_framework"] += 1; return False
        if norm_stem(q) in maa: st[ds]["maa"] += 1; return False
        if J_med.hit(w): st[ds]["medical_eval_overlap"] += 1; return False
        if public and (ds == "who_and_when" or r["framework_family"] == "groupchat"): st[ds]["eval_dataset_or_groupchat"] += 1; return False
        if public and J_pub.hit(w): st[ds]["public_eval_overlap"] += 1; return False
        return True

    # ---- runtime (medical) runs
    med, seen = [], set()
    for p in a.runtime:
        for r in read(p):
            ds = "med_" + r["framework"]; st[ds]["runs_in"] += 1
            if r["run_id"] in seen: st[ds]["duplicate"] += 1; continue
            seen.add(r["run_id"])
            if keep(r, ds, False): med.append(add_phase_canonical(r)); st[ds]["runs_kept"] += 1
    lm_med = []
    for r in med:
        for c in render_chunks(r, ntok, tok, a.max_tokens, a.env_chars): lm_med.append({"text": c, "run_id": r["run_id"], "part": "med"})
    M = sum(ntok(x["text"]) for x in lm_med)

    # ---- interaction samples (candidates for every eligible step), then sampled to M tokens (3 : 1)
    by_q = defaultdict(list)
    for r in med: by_q[r["question_id"]].append(r)
    cond, evid = [], []
    for r in med:
        ds = "med_" + r["framework"]
        if r["framework"] not in a.interaction_frameworks: st[ds]["runs_lm_only_framework"] += 1; continue
        if not (r.get("provenance") or {}).get("sources_complete"): st[ds]["runs_flagged_incomplete_but_used"] += 1
        steps = {s["step_id"]: s for s in r["steps"]}; order = [s["step_id"] for s in r["steps"]]
        task = f"Task ({r['task'].get('dataset')}):\n{(r['task'].get('query') or '').strip()}"
        for t_i, s in enumerate(r["steps"]):
            if s["kind"] != "llm" or not (s.get("output") or "").strip() or s.get("sources") is None: continue
            src = [x["step_id"] for x in s["sources"] if x.get("step_id") in steps]
            if any(x.get("collection", "runtime") != "runtime" for x in s["sources"]): st[ds]["non_runtime_sources"] += 1; continue
            sysm = f"You are {who(s)} ({s.get('agent_label') or s.get('agent_id')}) in the {r['framework']} multi-agent system. " \
                   f"Phase: {s.get('phase_canonical')}" + (f", round {s['round']}" if s.get("round") is not None else "") + "."
            msgs = "\n\n".join(f"[{k}] {who(steps[k])} | {steps[k].get('phase_canonical')}:\n{step_text(steps[k], a.env_chars)}"
                               for k in sorted(src, key=order.index))
            user = task + ("\n\nMessages visible to you:\n\n" + msgs if msgs else "\n\n(No earlier messages are visible to you.)")
            tgt = s["output"].strip()
            tt = ntok(tgt)
            if tt > 3000: tgt = tok.decode(tok(tgt, add_special_tokens=False)["input_ids"][:3000]); tt = 3000
            room = a.max_tokens - tt - ntok(sysm) - 40
            ut = tok(user, add_special_tokens=False)["input_ids"]
            if len(ut) > room: user = task[:400] + "\n[...]\n" + tok.decode(ut[-(room - 120):]); st[ds]["cond_context_cut"] += 1
            cond.append({"messages": [{"role": "system", "content": sysm}, {"role": "user", "content": user}, {"role": "assistant", "content": tgt}],
                         "run_id": r["run_id"], "step_id": s["step_id"], "kind": "cond", "target_tokens": tt})
            # evidence correspondence
            earlier = order[:t_i]; neg = [k for k in earlier if k not in src]
            if not src: continue
            if not neg:   # same question, other runs, same phase (retrieval negatives, not fault negatives)
                pool = [(o, x) for o in by_q[r["question_id"]] if o["run_id"] != r["run_id"] for x in o["steps"]
                        if x["kind"] == "llm" and x.get("phase_canonical") == s.get("phase_canonical") and (x.get("output") or "").strip()]
                if not pool: st[ds]["evidence_no_negative"] += 1; continue
                negc = [("x", o, x) for o, x in rng.sample(pool, min(3, len(pool)))]
            else:
                negc = [("in", r, steps[k]) for k in rng.sample(neg, min(3, len(neg)))]
            posc = [("in", r, steps[k]) for k in rng.sample(src, min(3, len(src)))]
            cands = posc + negc; rng.shuffle(cands); letters = "ABCDEF"
            body = "\n\n".join(f"({letters[i]}) {who(x)} | {x.get('phase_canonical')}:\n{trunc(step_text(x, a.env_chars), 600)}" for i, (_, _, x) in enumerate(cands))
            ans = ", ".join(letters[i] for i, c in enumerate(cands) if c in posc)
            user = (f"{task[:1500]}\n\nMessage written by {who(s)} | {s.get('phase_canonical')}:\n{trunc(tgt, 1500)}\n\n"
                    f"Candidate earlier messages:\n\n{body}\n\nWhich candidate messages were visible to the writer when this message was written? "
                    f"Answer with the letters.")
            evid.append({"messages": [{"role": "system", "content": "You audit information flow in multi-agent systems."},
                                      {"role": "user", "content": user}, {"role": "assistant", "content": ans}],
                         "run_id": r["run_id"], "step_id": s["step_id"], "kind": "evidence", "target_tokens": ntok(ans)})
    rng.shuffle(cond); rng.shuffle(evid)

    def take(pool, budget):
        out, used = [], 0
        for x in pool:
            n = chat_ntok(x["messages"])
            if used + n > budget: continue
            x["processed_tokens"] = n; out.append(x); used += n
            if used >= budget * 0.995: break
        return out, used
    ic_cond, uc = take(cond, 0.75 * M); ic_evid, ue = take(evid, M - uc)
    if uc + ue < 0.95 * M: print(f"WARNING interaction samples cover only {(uc + ue) / M:.3f} of the medical LM tokens (pool exhausted)")

    # ---- public part, identical chunks in both arms
    pub = []
    for p in sorted(glob.glob(os.path.join(a.public_dir, "*.jsonl.gz"))):
        ds = os.path.basename(p).split(".")[0]
        for r in read(p):
            st[ds]["runs_in"] += 1
            if keep(r, ds, True): pub.append(add_phase_canonical(r)); st[ds]["runs_kept"] += 1
    rng.shuffle(pub); left = a.budget_m * 1e6 - M; lm_pub = []; P = 0
    for r in pub:
        if P >= left: break
        for c in render_chunks(r, ntok, tok, a.max_tokens, a.env_chars):
            n = ntok(c); lm_pub.append({"text": c, "run_id": r["run_id"], "part": "public"}); P += n
    replay = [{"messages": [{"role": "user", "content": REPLAY_PROMPT}, {"role": "assistant", "content": x["text"]}], "run_id": x["run_id"], "kind": "replay"} for x in lm_pub]
    R = sum(chat_ntok(x["messages"]) for x in replay)

    lm = lm_med + lm_pub; ic = ic_cond + ic_evid + replay; rng.shuffle(lm); rng.shuffle(ic)
    with open(os.path.join(a.out_dir, "lm.jsonl"), "w") as f:
        for x in lm: f.write(json.dumps({"text": x["text"]}, ensure_ascii=False) + "\n")
    with open(os.path.join(a.out_dir, "icpt.jsonl"), "w") as f:
        for x in ic: f.write(json.dumps({"messages": x["messages"]}, ensure_ascii=False) + "\n")
    stats = {"lm": {"medical_tokens": M, "public_tokens": P, "total": M + P, "chunks": len(lm)},
             "icpt": {"cond_tokens": uc, "evidence_tokens": ue, "replay_tokens": R, "total": uc + ue + R,
                      "n_cond": len(ic_cond), "n_evidence": len(ic_evid), "n_replay": len(replay),
                      "target_tokens_cond": sum(x["target_tokens"] for x in ic_cond), "target_tokens_evidence": sum(x["target_tokens"] for x in ic_evid),
                      "pool_cond": len(cond), "pool_evidence": len(evid)},
             "ratio_total_icpt_over_lm": (uc + ue + R) / (M + P), "datasets": {k: dict(v) for k, v in st.items()}, "args": vars(a)}
    json.dump(stats, open(os.path.join(a.out_dir, "stats.json"), "w"), indent=1)
    json.dump({"lm_medical_runs": sorted({x["run_id"] for x in lm_med}), "public_runs": sorted({x["run_id"] for x in lm_pub}),
               "icpt_steps": [[x["run_id"], x["step_id"], x["kind"]] for x in ic_cond + ic_evid]}, open(os.path.join(a.out_dir, "manifest.json"), "w"))
    print(json.dumps({k: v for k, v in stats.items() if k != "datasets" and k != "args"}, indent=1))
    for k in sorted(st): print(f"{k:24s} {dict(st[k])}")


if __name__ == "__main__":
    main()
