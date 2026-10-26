"""Mid-training (TAPT) pilot corpus (round 62).

Sources (mas-traj/1): the 7 converted public datasets (data_tools/public_to_mas_traj) + medical-aegis anchor exports
(normal runs only: injected runs are excluded from the main version, round 50). No MedAgentAudit (MAA) data at all, so
one mid-training run serves every MAA split as strict zero-shot at the question level.
Exclusions:
  * framework_family in --exclude_families (pilot: "groupchat", so LQD_mac -- MAC is an AutoGen-GroupChat design -- is
    also zero-shot at the ARCHITECTURE level; medical-aegis issue round 38 family rule);
  * any run whose question matches the MAA exclusion list (data_tools/maa_exclusion; exact rule).
Serialisation (only fields every source has, medical-aegis round 42 (C)): task query, then per step
  "[s<k>] <agent_role> | <phase_canonical>" + output; environment / tool outputs truncated head+tail to --env_chars
  (the same rule for every source); llm outputs are never shortened.
Chunking: a run longer than --max_tokens is split at step boundaries; every chunk repeats the task header; a single step
  longer than the budget is cut at the token level.
Balancing: per dataset token cap (--cap dataset=millions), runs sampled in a fixed random order (seed 0).
Output: jsonl {"text", "dataset", "framework", "family", "run_id", "chunk"} + a stats json.
Usage: python -m hgfm.midtrain.build_corpus --public_dir /home/claude/public_mas/mas_traj --anchor f1.jsonl.gz [f2 ...]
         --out corpus.jsonl --stats stats.json [--exclude_families groupchat] [--cap aria=8 ...] [--max_tokens 4096]
"""
import argparse, glob, gzip, json, os, random, sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from data_tools.maa_exclusion import norm_stem   # noqa: E402
from data_tools.public_to_mas_traj.common import add_phase_canonical   # noqa: E402


def read(p):
    with (gzip.open if p.endswith(".gz") else open)(p, "rt", encoding="utf-8") as f:
        for l in f:
            if l.strip():
                yield json.loads(l)


def trunc(t, n):
    t = t or ""
    return t if len(t) <= n else t[: n // 2] + "\n[...]\n" + t[-n // 2:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--public_dir"); ap.add_argument("--anchor", nargs="*", default=[]); ap.add_argument("--out"); ap.add_argument("--stats")
    ap.add_argument("--exclude_families", nargs="*", default=["groupchat"]); ap.add_argument("--cap", nargs="*", default=[])
    ap.add_argument("--max_tokens", type=int, default=4096); ap.add_argument("--env_chars", type=int, default=2000)
    ap.add_argument("--maa_exclusion", default=os.path.join(os.path.dirname(__file__), "..", "..", "docs", "interfaces", "maa_exclusion_v1.json"))
    ap.add_argument("--tokenizer", default="Qwen/Qwen3-8B")
    a = ap.parse_args()
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.tokenizer)
    ntok = lambda s: len(tok(s, add_special_tokens=False)["input_ids"])
    caps = {k: float(v) * 1e6 for k, v in (x.split("=") for x in a.cap)}
    excl = json.load(open(a.maa_exclusion)); maa = {e["norm_stem"]: e for e in excl["entries"]}

    runs = []   # (dataset, rec)
    for p in sorted(glob.glob(os.path.join(a.public_dir, "*.jsonl.gz"))):
        ds = os.path.basename(p).split(".")[0]
        runs += [(ds, r) for r in read(p)]
    seen = set()
    for p in a.anchor:
        for r in read(p):
            if r["run_mode"] != "normal" or r["run_id"] in seen:
                continue
            seen.add(r["run_id"]); runs.append(("anchor_" + r["framework"], add_phase_canonical(r)))
    st = defaultdict(Counter)
    kept = defaultdict(list)
    for ds, r in runs:
        st[ds]["runs_in"] += 1
        if r["framework_family"] in a.exclude_families:
            st[ds]["excluded_family"] += 1; continue
        e = maa.get(norm_stem(r["task"].get("query") or ""))
        if e and (not e["images"] or set(e["images"]) & set(r["task"].get("images") or [])):
            st[ds]["excluded_maa"] += 1; continue
        kept[ds].append(r)
    rng = random.Random(0)
    n_out = 0
    with open(a.out, "w", encoding="utf-8") as fo:
        for ds in sorted(kept):
            rs = kept[ds][:]; rng.shuffle(rs); used = 0
            for r in rs:
                if ds in caps and used >= caps[ds]:
                    st[ds]["dropped_by_cap"] += 1; continue
                head = f"Task ({r['task'].get('dataset')}, framework {r['framework']}):\n{(r['task'].get('query') or '').strip()}\n"
                blocks = []
                for s in r["steps"]:
                    out = s.get("output") or ""
                    if s["kind"] != "llm":
                        out = trunc(out, a.env_chars)
                    if not out.strip() and s.get("tool_calls"):
                        out = json.dumps([{"name": t.get("name"), "arguments": t.get("arguments")} for t in s["tool_calls"]], ensure_ascii=False)[: a.env_chars]
                    blocks.append(f"[{s['step_id']}] {s.get('agent_role') or s.get('agent_id')} | {s.get('phase_canonical')}\n{out.strip()}\n")
                ht = ntok(head); budget = a.max_tokens - ht - 8
                chunk, ct, k = [], 0, 0
                def flush():
                    nonlocal chunk, ct, k, n_out, used
                    if chunk:
                        txt = head + "\n" + "\n".join(chunk)
                        fo.write(json.dumps({"text": txt, "dataset": ds, "framework": r["framework"], "family": r["framework_family"],
                                             "run_id": r["run_id"], "chunk": k}, ensure_ascii=False) + "\n")
                        used += ct + ht; st[ds]["tokens"] += ct + ht; st[ds]["chunks"] += 1; n_out += 1; k += 1
                    chunk, ct = [], 0
                for b in blocks:
                    bt = ntok(b)
                    if bt > budget:
                        ids = tok(b, add_special_tokens=False)["input_ids"][:budget]
                        b, bt = tok.decode(ids), len(ids); st[ds]["steps_cut"] += 1
                    if ct + bt > budget:
                        flush()
                    chunk.append(b); ct += bt
                flush()
                st[ds]["runs_kept"] += 1
    tot = Counter()
    for c in st.values():
        tot.update(c)
    json.dump({"datasets": {k: dict(v) for k, v in st.items()}, "total": dict(tot), "args": vars(a)}, open(a.stats, "w"), indent=1)
    for k in sorted(st):
        print(f"{k:28s} {dict(st[k])}")
    print("TOTAL", dict(tot))


if __name__ == "__main__":
    main()
