import os, json, re, glob, zipfile, collections, hashlib, time, sys
import numpy as np, pandas as pd
os.environ["TOKENIZERS_PARALLELISM"] = "true"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
from transformers import AutoTokenizer

R = "/home/claude/public_mas/raw"
OUT = "/home/claude/public_mas"
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-8B")
T0 = time.time()
def log(*a):
    print(f"[{time.time()-T0:7.1f}s]", *a, flush=True)

# ---------------- token cache ----------------
CACHE = {}
def h(s): return hashlib.blake2b(s.encode("utf-8", "surrogatepass"), digest_size=12).digest()
def count_tokens(strings):
    todo = {}
    for s in strings:
        k = h(s)
        if k not in CACHE and k not in todo: todo[k] = s
    items = list(todo.items())
    B = 512
    for i in range(0, len(items), B):
        chunk = items[i:i+B]
        enc = tok._tokenizer.encode_batch([s for _, s in chunk], add_special_tokens=False)
        for (k, _), e in zip(chunk, enc): CACHE[k] = len(e.ids)
def ntok(s): return CACHE[h(s)]

def strs_from_args(a):
    """natural-language values of a tool-call arguments JSON string (no keys)."""
    out = []
    if a is None: return out
    if isinstance(a, str):
        try: a = json.loads(a)
        except Exception: return [a] if a.strip() else []
    def rec(x):
        if isinstance(x, str):
            if x.strip(): out.append(x)
        elif isinstance(x, dict):
            for v in x.values(): rec(v)
        elif isinstance(x, list):
            for v in x: rec(v)
    rec(a); return out

def content_text(c):
    """returns (list of text strings, n_images)"""
    if c is None: return [], 0
    if isinstance(c, str): return ([c] if c.strip() else []), 0
    if isinstance(c, list):
        t, n = [], 0
        for p in c:
            if isinstance(p, dict):
                if p.get("type") == "text" and isinstance(p.get("text"), str): t.append(p["text"])
                elif "image" in str(p.get("type")): n += 1
            elif isinstance(p, str): t.append(p)
        return [x for x in t if x.strip()], n
    return [str(c)], 0

def norm(s): return re.sub(r"\s+", " ", s).strip().lower()

# Each trajectory: dict(ds, group..., steps, segs=[(text, part)], question, raw_extra_tokens?)
TRAJ = []

# ---------------- AEGIS ----------------
for sp in ["train", "validation", "test"]:
    df = pd.read_parquet(f"{R}/Fancylalala__AEGIS/default/{sp}/0000.parquet")
    for _, r in df.iterrows():
        md = r["metadata"]; o = json.loads(r["input"]); gt = r["ground_truth"]
        inj = gt.get("injected_agents"); ninj = len(inj) if inj is not None else 0
        segs = [(o["query"], "task")]
        for t in o.get("conversation_history", []):
            c = t.get("content")
            for x in content_text(c)[0]:
                segs.append((x, "injected_turn" if t.get("is_injected") else "turn"))
        if o.get("final_output"):
            for x in content_text(o["final_output"])[0]: segs.append((x, "final"))
        TRAJ.append(dict(ds="AEGIS", split=sp, framework=md["framework"], benchmark=md["benchmark"],
                         task_type=md["task_type"], model=md["model"],
                         clean="clean" if (md["num_injected_agents"] == 0 or ninj == 0) else "injected",
                         steps=len(o.get("conversation_history", [])), segs=segs, question=o["query"], id=r["id"]))
log("AEGIS loaded", sum(t["ds"] == "AEGIS" for t in TRAJ))

# ---------------- MAST ----------------
df = pd.read_parquet(f"{R}/mcemri__MAST-Data/default/train/0000.parquet")
def mast_question(mas, s):
    pats = [r"problem_statement:\s*\n?(.*?)\n\S[^\n]*?:", r"\*\*task_prompt\*\*:\s*(.*?)\n\n", r"CONTENT:\n(.*?)\n-{10,}",
            r"\*{10,} Task \d+/\d+ \([^)]*\)\s*\*{10,}\n(.*?)\n"]
    for p in pats:
        m = re.search(p, s[:200000], re.S)
        if m and len(m.group(1).strip()) > 10: return m.group(1).strip()
    return None
for _, r in df.iterrows():
    s = r["trace"]["trajectory"]
    paras = [p for p in re.split(r"\n\s*\n", s) if p.strip()]
    TRAJ.append(dict(ds="MAST", framework=r["mas_name"], benchmark=r["benchmark_name"], model=r["llm_name"],
                     steps=None, segs=[(p, "log_paragraph") for p in paras], question=mast_question(r["mas_name"], s),
                     id=f'{r["mas_name"]}/{r["benchmark_name"]}/{r["trace_id"]}'))
log("MAST loaded")

# ---------------- Who&When ----------------
for cfg in ["Algorithm-Generated", "Hand-Crafted"]:
    df = pd.read_parquet(f"{R}/Kevin355__Who_and_When/{cfg}/train/0000.parquet")
    for _, r in df.iterrows():
        qid = r["question_ID"]
        bench = "GAIA" if re.fullmatch(r"[0-9a-f-]{36}", qid) else ("AssistantBench" if re.fullmatch(r"[0-9a-f]{64}", qid) else "unknown")
        hist = list(r["history"])
        segs = []
        if not any(norm(x.get("content") or "") == norm(r["question"]) for x in hist[:2]):
            segs.append((r["question"], "task"))
        for m in hist:
            for x in content_text(m.get("content"))[0]: segs.append((x, "turn"))
        TRAJ.append(dict(ds="Who&When", split=cfg, framework=("Magentic-One" if cfg == "Hand-Crafted" else "CaptainAgent"),
                         benchmark=bench, steps=len(hist), segs=segs, question=r["question"], id=f"{cfg}/{qid}"))
log("W&W loaded")

# ---------------- TraceElephant ----------------
z = zipfile.ZipFile(f"{R}/TraceElephant__TraceElephant/data.zip")
names = z.namelist()
te_img_steps = collections.Counter()
for n in names:
    if not n.endswith("step_records.json"): continue
    d = n.rsplit("/", 1)[0]; sub = n.split("/")[1]
    meta = json.loads(z.read(d + "/trace_metadata.json")) if (d + "/trace_metadata.json") in names else {}
    steps = json.loads(z.read(n))
    raw = []; nimg = 0
    if meta.get("task_instruction"): raw.append((meta["task_instruction"], "task"))
    for s in steps:
        for m in s.get("input", {}).get("messages", []):
            t, k = content_text(m.get("content")); nimg += k
            raw += [(x, "input_context") for x in t]
            for tb in (m.get("thinking_blocks") or []):
                if isinstance(tb, dict) and isinstance(tb.get("thinking"), str) and tb["thinking"].strip(): raw.append((tb["thinking"], "input_context"))
            for tc in (m.get("tool_calls") or []):
                if isinstance(tc, dict): raw += [(x, "input_context") for x in strs_from_args((tc.get("function") or {}).get("arguments"))]
        for ch in (s.get("output") or {}).get("choices", []):
            msg = ch.get("message") or {}
            raw += [(x, "output") for x in content_text(msg.get("content"))[0]]
            for tc in (msg.get("tool_calls") or []):
                if isinstance(tc, dict): raw += [(x, "output_toolcall") for x in strs_from_args((tc.get("function") or {}).get("arguments"))]
        for tc in (s.get("tool_logs") or []):
            if isinstance(tc, dict): raw += [(x, "tool_log") for x in strs_from_args((tc.get("function") or {}).get("arguments"))]
    system = sub.split("-runs-")[0]; bench = sub.split("-runs-")[1]
    bench = {"assistantbench": "AssistantBench", "assistant-bench": "AssistantBench", "gaia": "GAIA", "swe-bench": "SWE-bench"}[bench]
    TRAJ.append(dict(ds="TraceElephant", framework=system, benchmark=bench, steps=len(steps), segs=raw, raw_is_cumulative=True,
                     question=meta.get("task_instruction"), id=sub + "/" + d.split("/")[-1], n_images_in_inputs=nimg))
log("TE loaded")

# ---------------- Who&When Pro (only real files) ----------------
inv = json.load(open(f"{OUT}/wwp_inventory.json"))
for rec in inv["inventory"]:
    if rec["kind"] != "file": continue
    o = json.load(open(rec["local"]))
    fn = os.path.basename(rec["local"])[:-5].split("__")  # modality,bench,fw,mode,task,ts
    task_key = f'{fn[1]}/{fn[4]}/{fn[5] if fn[2]=="alfagent" else ""}'
    gstep = (o.get("ground_truth") or {}).get("step")
    segs = []; q = (o.get("task") or {}).get("query")
    traj = o.get("trajectory") or []
    turn_texts = []  # (text, rel)
    for i, t in enumerate(traj):
        if "step_number" in t:  # alfagent action turns
            sn = t["step_number"]
            txt = "\n".join(x for x in [t.get("reasoning"), t.get("action"), t.get("observation")] if isinstance(x, str) and x.strip())
        else:
            sn = i if fn[2] != "alfagent" else 0
            parts = content_text(t.get("content"))[0]
            for tc in (t.get("tool_calls") or []):
                if isinstance(tc, dict): parts += strs_from_args((tc.get("function") or {}).get("arguments", tc.get("arguments")))
            txt = "\n".join(parts)
        rel = "prefix" if (gstep is None or sn < gstep) else ("injected_step" if sn == gstep else "post")
        if txt.strip(): turn_texts.append((txt, rel))
    if q and not any(norm(q) == norm(x) for x, _ in turn_texts[:3]):
        turn_texts.insert(0, (q if isinstance(q, str) else json.dumps(q), "prefix"))
    TRAJ.append(dict(ds="Who&When-Pro", modality=rec["modality"], framework=rec["framework"], benchmark=rec["benchmark"],
                     mode=(o.get("ground_truth") or {}).get("mode"), task_key=task_key, steps=len(traj), segs=turn_texts,
                     question=q if isinstance(q, str) else None, id=o.get("id")))
log("WWP loaded")

# ---------------- tokenize ----------------
allsegs = [s for t in TRAJ for s, _ in t["segs"]]
log("segments", len(allsegs), "chars", sum(map(len, allsegs)))
del allsegs
for ds in ["AEGIS", "Who&When", "Who&When-Pro", "TraceElephant", "MAST"]:
    count_tokens(s for t in TRAJ if t["ds"] == ds for s, _ in t["segs"])
    log("tokenized", ds, "cache", len(CACHE))

for t in TRAJ:
    toks = [ntok(s) for s, _ in t["segs"]]
    t["tok_raw"] = int(sum(toks))
    seen = set(); u = 0
    for (s, _), n in zip(t["segs"], toks):
        k = h(s)
        if k not in seen: seen.add(k); u += n
    t["tok_uniq_in_traj"] = int(u)
    t["tok_primary"] = t["tok_uniq_in_traj"] if t.get("raw_is_cumulative") else t["tok_raw"]
    pc = collections.Counter()
    for (s, p), n in zip(t["segs"], toks): pc[p] += n
    t["tok_by_part"] = dict(pc)

def pct(a, q): return int(np.percentile(a, q)) if len(a) else None
def summarize(ts):
    a = np.array([t["tok_primary"] for t in ts])
    st = [t["steps"] for t in ts if t["steps"] is not None]
    seen = set(); g = 0
    for t in ts:
        for s, _ in t["segs"]:
            k = h(s)
            if k not in seen: seen.add(k); g += ntok(s)
    parts = collections.Counter()
    for t in ts: parts.update(t["tok_by_part"])
    return dict(n=len(ts), steps_total=(int(sum(st)) if st else None), steps_p50=(pct(st, 50) if st else None),
                tokens_total=int(a.sum()), tokens_raw_as_stored=int(sum(t["tok_raw"] for t in ts)),
                tokens_global_exact_dedup=int(g), p50=pct(a, 50), p90=pct(a, 90), p99=pct(a, 99), max=int(a.max()) if len(a) else None,
                n_gt_8k=int((a > 8192).sum()), n_gt_32k=int((a > 32768).sum()), tokens_by_part=dict(parts))

def by(ts, key):
    g = collections.defaultdict(list)
    for t in ts: g[t.get(key) if not callable(key) else key(t)].append(t)
    return {str(k): summarize(v) for k, v in sorted(g.items(), key=lambda kv: -sum(x["tok_primary"] for x in kv[1]))}

DOMAIN = {"GSM8K": "math", "MATH": "math", "GSM": "math", "Olympiad": "math", "SciBench": "science-reasoning", "MMLU": "knowledge-QA",
          "HumanEval": "code", "ProgramDev": "software-dev", "ProgramDev-v2": "software-dev", "SWE-Bench-Lite": "SWE", "SWE-bench": "SWE",
          "GAIA": "web/agentic-QA", "AssistantBench": "web/agentic-QA", "smol+gaia": "web/agentic-QA", "magentic+gaia": "web/agentic-QA",
          "Test-C": "app-agent (AppWorld)", "alfworld": "embodied-text (ALFWorld)"}
for t in TRAJ: t["domain"] = DOMAIN.get(t["benchmark"], t["benchmark"])

stats = {}
for ds in ["AEGIS", "MAST", "Who&When", "TraceElephant", "Who&When-Pro"]:
    ts = [t for t in TRAJ if t["ds"] == ds]
    if ds == "Who&When-Pro":
        txt = [t for t in ts if t["modality"] == "text"]
        e = dict(text_modality=summarize(txt), text_by_benchmark_framework=by(txt, lambda t: f'{t["benchmark"]}/{t["framework"]}'),
                 video_json_extra_text_tokens=summarize([t for t in ts if t["modality"] == "video"]),
                 video_by_benchmark_framework=by([t for t in ts if t["modality"] == "video"], lambda t: f'{t["benchmark"]}/{t["framework"]}'))
        # prefix / injected / post + dedup of prefix by (task, exact turn text)
        for name, sub in [("text", txt), ("video", [t for t in ts if t["modality"] == "video"])]:
            pr = collections.Counter(); seen = set(); dedup_prefix = 0; uniq_turn_all = set(); dedup_all = 0
            for t in sub:
                for s, p in t["segs"]:
                    n = ntok(s); pr[p] += n
                    if p == "prefix":
                        k = (t["task_key"], h(s))
                        if k not in seen: seen.add(k); dedup_prefix += n
                    k2 = (t["task_key"], h(s))
                    if k2 not in uniq_turn_all: uniq_turn_all.add(k2); dedup_all += n
            e[f"{name}_prefix_injected_post"] = dict(pr, prefix_dedup_by_task_exact_turn=dedup_prefix,
                                                     all_turns_dedup_by_task_exact_turn=dedup_all,
                                                     n_tasks=len({t["task_key"] for t in sub}))
        # inventory counts
        invc = collections.Counter((r["modality"], r["kind"]) for r in inv["inventory"])
        e["archive_inventory"] = {f"{a}/{b}": v for (a, b), v in invc.items()}
        e["dangling_by_modality_benchmark_framework"] = {f'{k[0]}/{k[1]}/{k[2]}': v for k, v in sorted(collections.Counter(
            (r["modality"], r["benchmark"], r["framework"]) for r in inv["inventory"] if r["kind"] == "symlink").items())}
        e["media_files"] = inv["media"]
        e["n_traces_listed"] = len(inv["inventory"])
        stats[ds] = e
        continue
    e = dict(overall=summarize(ts), by_framework=by(ts, "framework"), by_benchmark=by(ts, "benchmark"), by_domain=by(ts, "domain"))
    if ds == "AEGIS":
        e["by_split"] = by(ts, "split"); e["by_clean_vs_injected"] = by(ts, "clean")
        e["unique_queries"] = len({norm(t["question"]) for t in ts})
    if ds == "Who&When": e["by_config"] = by(ts, "split")
    if ds == "MAST": e["question_extracted"] = sum(1 for t in ts if t["question"]); e["unit_note"] = "segments = blank-line-separated paragraphs of raw log; tokens = sum over paragraphs"
    if ds == "TraceElephant":
        e["note"] = "tokens_total = unique message texts within each trace (input contexts are cumulative); tokens_raw_as_stored = sum over all per-step inputs+outputs"
        e["images_in_inputs"] = sum(t["n_images_in_inputs"] for t in ts)
    stats[ds] = e
log("stats done")

# ---------------- overlap vs MAA ----------------
maa_q = []
with open("/home/claude/data_maa_v2/maa_mas_traj.jsonl") as f:
    for line in f:
        try: q = json.loads(line)["task"]["query"]
        except Exception: continue
        if isinstance(q, str) and q.strip(): maa_q.append(norm(q))
maa_set = set(maa_q)
W = 12
first = {}
for q in maa_set:
    w = q.split()
    if len(w) >= W: first.setdefault(tuple(w[:W]), []).append(q)
ov = {}
for ds in ["AEGIS", "MAST", "Who&When", "TraceElephant", "Who&When-Pro"]:
    ts = [t for t in TRAJ if t["ds"] == ds]
    qs = [norm(t["question"]) for t in ts if t.get("question")]
    exact = sum(1 for q in qs if q in maa_set)
    # containment: any MAA query (>=12 words) whose full text appears inside any segment
    hits = set(); done = set(); hitsegs = set()
    for t in ts:
        for s, _ in t["segs"]:
            k = h(s)
            if k in done: continue
            done.add(k)
            ns = norm(s); w = ns.split()
            if len(w) < W: continue
            for i in range(len(w) - W + 1):
                c = first.get(tuple(w[i:i+W]))
                if c:
                    for q in c:
                        if q in ns: hits.add(q); hitsegs.add(k)
    traj_hits = sum(1 for t in ts if any(h(s) in hitsegs for s, _ in t["segs"]))
    ov[ds] = dict(questions_checked=len(qs), exact_question_matches=exact, maa_queries_contained_in_any_segment=len(hits),
                  trajectories_containing_a_maa_query=traj_hits, examples=[x[:200] for x in list(hits)[:3]])
    log("overlap", ds, ov[ds])
stats["overlap_vs_MAA"] = dict(maa_rows=len(maa_q), maa_unique_queries=len(maa_set), maa_queries_ge12_words=sum(len(v) for v in first.values()),
                               method="exact = normalized (lowercase, whitespace-collapsed) question equality; contained = full normalized MAA query found inside a normalized public segment (candidate via first-12-word window)",
                               per_dataset=ov)
stats["download_local"] = json.load(open(f"{OUT}/download_log.json"))
stats["tokenizer"] = "Qwen/Qwen3-8B (HF), add_special_tokens=False, per-segment counts summed"
json.dump(stats, open(f"{OUT}/stats.json", "w"), indent=1, ensure_ascii=False)

# ---------------- samples ----------------
with open(f"{OUT}/samples.txt", "w") as f:
    for ds in ["AEGIS", "MAST", "Who&When", "TraceElephant", "Who&When-Pro"]:
        ts = [t for t in TRAJ if t["ds"] == ds and t.get("modality", "text") == "text"]
        idx = np.linspace(0, len(ts) - 1, 3).astype(int)
        for i in idx:
            t = ts[i]
            body = "\n---\n".join(f"[{p}] {s}" for s, p in t["segs"])
            f.write(f"===== {ds} | id={t['id']} | framework={t['framework']} | benchmark={t['benchmark']} | steps={t['steps']} | tokens={t['tok_primary']}\n")
            f.write(body[:1500] + ("\n...[truncated]" if len(body) > 1500 else "") + "\n\n")
log("DONE")
