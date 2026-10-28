"""E2 (round 67, pre-registration E1-E3 v1): matched success-only (S) and all-outcome (R) continued-pretraining corpora.

  python -m hgfm.e1e3.e2_corpus --public_dir /home/claude/public_mas/mas_traj --anchor a.jsonl.gz ... --out DIR [--aria_cap_tokens 3e6]

Corpus rules = TAPT pilot (hgfm/midtrain/build_corpus.py): public mas-traj/1 + medical-aegis anchor NORMAL runs (deduplicated),
no MAA, family groupchat excluded, MAA exclusion list v1; same serialisation and chunking (<= --max_tokens, split at step
boundaries, task header repeated, environment / tool outputs truncated to --env_chars).
Success labels (only these four sources; datasets without an outcome label are used by neither corpus):
  aria      labels.external.outcome.source_success          aftraj  labels.external.split == "safe"
  mast_data labels.external.any_failure == False             anchors final answer == gold
S = all success runs per dataset (ARIA capped at --aria_cap_tokens, runs in a fixed random order).
R = per dataset, runs drawn in a fixed random order from ALL outcomes until the dataset's S token count is reached, so S and
R differ only in outcome composition, not in dataset mix or size.
Outputs: S.jsonl, R.jsonl ({"text", "dataset", "run_id", "chunk", "success"}), stats.json.
"""
import argparse, ast, glob, gzip, json, os, random, sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from data_tools.maa_exclusion import norm_stem   # noqa: E402
from data_tools.public_to_mas_traj.common import add_phase_canonical   # noqa: E402
from hgfm.midtrain.build_corpus import read, trunc   # noqa: E402


def success(ds, r):
    ext = (r.get("labels") or {}).get("external") or {}
    if ds == "aria":
        o = ext.get("outcome")
        if isinstance(o, str):
            try: o = ast.literal_eval(o)
            except Exception: o = None
        return bool(o.get("source_success")) if isinstance(o, dict) and "source_success" in o else None
    if ds == "aftraj": return ext.get("split") == "safe" if ext.get("split") else None
    if ds == "mast_data": return {"False": True, "True": False}.get(str(ext.get("any_failure")))
    if ds.startswith("anchor_"):
        g, f = r["labels"].get("gold"), (r.get("final") or {}).get("answer")
        return None if g is None or f is None else str(g).strip() == str(f).strip()
    return None


def chunks(r, ntok, tok, max_tokens, env_chars):
    """Exactly build_corpus.py's serialisation + chunking; yields (text, n_tokens)."""
    head = f"Task ({r['task'].get('dataset')}, framework {r['framework']}):\n{(r['task'].get('query') or '').strip()}\n"
    blocks = []
    for s in r["steps"]:
        out = s.get("output") or ""
        if s["kind"] != "llm": out = trunc(out, env_chars)
        if not out.strip() and s.get("tool_calls"):
            out = json.dumps([{"name": t.get("name"), "arguments": t.get("arguments")} for t in s["tool_calls"]], ensure_ascii=False)[:env_chars]
        blocks.append(f"[{s['step_id']}] {s.get('agent_role') or s.get('agent_id')} | {s.get('phase_canonical')}\n{out.strip()}\n")
    ht = ntok(head); budget = max_tokens - ht - 8; ch, ct = [], 0
    for b in blocks:
        bt = ntok(b)
        if bt > budget:
            ids = tok(b, add_special_tokens=False)["input_ids"][:budget]; b, bt = tok.decode(ids), len(ids)
        if ct + bt > budget and ch:
            yield head + "\n" + "\n".join(ch), ct + ht; ch, ct = [], 0
        ch.append(b); ct += bt
    if ch: yield head + "\n" + "\n".join(ch), ct + ht


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--public_dir"); ap.add_argument("--anchor", nargs="*", default=[]); ap.add_argument("--out")
    ap.add_argument("--aria_cap_tokens", type=float, default=3e6); ap.add_argument("--max_tokens", type=int, default=4096)
    ap.add_argument("--env_chars", type=int, default=2000); ap.add_argument("--tokenizer", default="Qwen/Qwen3-8B")
    ap.add_argument("--maa_exclusion", default=os.path.join(os.path.dirname(__file__), "..", "..", "docs", "interfaces", "maa_exclusion_v1.json"))
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.tokenizer); ntok = lambda s: len(tok(s, add_special_tokens=False)["input_ids"])
    maa = {e["norm_stem"]: e for e in json.load(open(a.maa_exclusion))["entries"]}
    runs, seen, st = defaultdict(list), set(), defaultdict(Counter)
    srcs = [(os.path.basename(p).split(".")[0], p) for p in sorted(glob.glob(os.path.join(a.public_dir, "*.jsonl.gz")))] + [("anchor", p) for p in a.anchor]
    for ds0, p in srcs:
        for r in read(p):
            if ds0 == "anchor":
                if r["run_mode"] != "normal": continue
                r = add_phase_canonical(r); ds = "anchor_" + r["framework"]
            else: ds = ds0
            if r["run_id"] in seen: continue
            seen.add(r["run_id"])
            if r["framework_family"] == "groupchat": continue
            e = maa.get(norm_stem(r["task"].get("query") or ""))
            if e and (not e["images"] or set(e["images"]) & set(r["task"].get("images") or [])): continue
            s = success(ds, r)
            if s is None: st[ds]["no_outcome_label"] += 1; continue
            runs[ds].append((r, s)); st[ds]["success" if s else "failure"] += 1
    rng = random.Random(0); fS, fR = open(os.path.join(a.out, "S.jsonl"), "w"), open(os.path.join(a.out, "R.jsonl"), "w")
    for ds in sorted(runs):
        pool = runs[ds][:]; rng.shuffle(pool)
        cap = a.aria_cap_tokens if ds == "aria" else float("inf"); sT = 0
        for r, s in pool:
            if not s: continue
            if sT >= cap: st[ds]["S_dropped_by_cap"] += 1; continue
            for k, (txt, n) in enumerate(chunks(r, ntok, tok, a.max_tokens, a.env_chars)):
                fS.write(json.dumps({"text": txt, "dataset": ds, "run_id": r["run_id"], "chunk": k, "success": True}, ensure_ascii=False) + "\n"); sT += n
            st[ds]["S_runs"] += 1
        st[ds]["S_tokens"] = sT
        pool2 = runs[ds][:]; rng.shuffle(pool2); rT = 0
        for r, s in pool2:
            if rT >= sT: break
            for k, (txt, n) in enumerate(chunks(r, ntok, tok, a.max_tokens, a.env_chars)):
                fR.write(json.dumps({"text": txt, "dataset": ds, "run_id": r["run_id"], "chunk": k, "success": s}, ensure_ascii=False) + "\n"); rT += n
            st[ds]["R_runs"] += 1; st[ds]["R_success_runs"] += int(s)
        st[ds]["R_tokens"] = rT
        print(ds, dict(st[ds]), flush=True)
    fS.close(); fR.close()
    tot = Counter()
    for c in st.values(): tot.update({k: v for k, v in c.items()})
    json.dump({"datasets": {k: dict(v) for k, v in st.items()}, "total": dict(tot), "args": vars(a)}, open(os.path.join(a.out, "stats.json"), "w"), indent=1)
    print("TOTAL", dict(tot))


if __name__ == "__main__":
    main()
