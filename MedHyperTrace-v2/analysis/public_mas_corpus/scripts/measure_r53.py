# r53: token statistics for 9 additional public MAS failure-attribution datasets.
# Same protocol as measure.py (Qwen3-8B tokenizer, add_special_tokens=False; natural-language trajectory content only).
# Run with: python -I measure_r53.py   (downloaded data is untrusted; script lives outside the data dir)
import os, json, re, zipfile, collections, hashlib, time, gc, glob
import numpy as np, pandas as pd
os.environ["TOKENIZERS_PARALLELISM"] = "true"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ.pop("HF_TOKEN", None)
from transformers import AutoTokenizer

R = "/home/claude/public_mas/raw"
OUT = "/home/claude/public_mas"
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-8B")
T0 = time.time()
def log(*a): print(f"[{time.time()-T0:7.1f}s]", *a, flush=True)

CACHE = {}
def h(s): return hashlib.blake2b(s.encode("utf-8", "surrogatepass"), digest_size=12).digest()
def count_tokens(strings):
    todo = {}
    for s in strings:
        k = h(s)
        if k not in CACHE and k not in todo: todo[k] = s
    items = list(todo.items()); B = 256
    for i in range(0, len(items), B):
        chunk = items[i:i+B]
        enc = tok._tokenizer.encode_batch([s for _, s in chunk], add_special_tokens=False)
        for (k, _), e in zip(chunk, enc): CACHE[k] = len(e.ids)
def norm(s): return re.sub(r"\s+", " ", s).strip().lower()
def J(x):
    if isinstance(x, str) and x[:1] in "[{":
        try: return json.loads(x)
        except Exception: return x
    return x
def truthy(x): return x is True or str(x).lower() == "true"
def nonnull(x): return isinstance(x, str) and x.strip() and x.strip().lower() not in ("null", "none")
def L(x): return list(x) if x is not None else []

def strs_from_args(a):
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
        elif isinstance(x, (list, tuple, np.ndarray)):
            for v in x: rec(v)
    rec(a); return out

def content_text(c):
    if c is None: return []
    if isinstance(c, str): return [c] if c.strip() else []
    if isinstance(c, (list, np.ndarray)):
        t = []
        for p in c:
            if isinstance(p, dict) and p.get("type") == "text" and isinstance(p.get("text"), str): t.append(p["text"])
            elif isinstance(p, str): t.append(p)
        return [x for x in t if x.strip()]
    return [str(c)]

def add_task(segs, q, first_texts):
    """prepend task question unless already contained in the first messages"""
    if isinstance(q, str) and q.strip() and not any(norm(q) in norm(x) for x in first_texts):
        segs.insert(0, (q, "task"))

# ---------------- medical detection ----------------
MED_CORE = {"clinical_knowledge", "college_medicine", "medical_genetics", "professional_medicine", "anatomy", "virology",
            "nutrition", "college_biology", "high_school_biology", "human_aging"}
MED_BORDER = {"high_school_psychology", "professional_psychology", "human_sexuality"}
MED_RE = re.compile(r"\b(patients?|clinical(?:ly)?|clinic|diagnos\w*|physicians?|medications?|medicines?|medical(?:ly)?|pharmac\w*|symptoms?|"
                    r"diseases?|syndromes?|hospital\w*|surg(?:ery|ical|eon)\w*|therap(?:y|ies|eutic)\w*|tumou?rs?|cancers?|carcinoma\w*|infections?|"
                    r"antibiotics?|vaccin\w*|nurs(?:e|es|ing)|dosages?|prescri\w*|pathogens?|patholog\w*|epidemiolog\w*|physiolog\w*|anatom\w*|"
                    r"health\s?care|disorders?|chronic|acute|mg/kg|blood pressure|insulin|diabet\w*|cardiac|renal|hepatic|neurolog\w*|"
                    r"oncolog\w*|psychiatr\w*|biops\w*|pregnan\w*|fetal|placebo|dementia|alzheimer\w*)\b", re.I)
def med_heuristic(q):
    if not isinstance(q, str): return False
    hits = {m.group(1).lower() for m in MED_RE.finditer(q)}
    return len(hits) >= 2

TRAJ = []   # compact records after tokenization
SEGSTORE = {}  # ds -> list of (traj_idx, hash, ntok, part)

def finalize(ds, trajs):
    """tokenize segments of a dataset, compute per-trajectory numbers, drop strings."""
    count_tokens(s for t in trajs for s, _ in t["segs"])
    for t in trajs:
        toks = [CACHE[h(s)] for s, _ in t["segs"]]
        hs = [h(s) for s, _ in t["segs"]]
        excl = t.get("exclude_parts", set())
        t["tok_raw"] = int(sum(n for (s, p), n in zip(t["segs"], toks) if p not in excl))
        t["tok_raw_incl_excluded"] = int(sum(toks))
        seen = set(); u = 0
        for (s, p), n, k in zip(t["segs"], toks, hs):
            if p in excl: continue
            if k not in seen: seen.add(k); u += n
        t["tok_uniq_in_traj"] = int(u)
        t["tok_primary"] = t["tok_uniq_in_traj"] if t.get("cumulative") else t["tok_raw"]
        pc = collections.Counter()
        for (s, p), n in zip(t["segs"], toks): pc[p] += n
        t["tok_by_part"] = dict(pc)
        t["seghashes"] = [(k, n, p) for (s, p), n, k in zip(t["segs"], toks, hs) if p not in excl]
        if t.get("question") and isinstance(t["question"], str): t["question"] = t["question"][:3000]
        del t["segs"]
    TRAJ.extend(trajs)
    log("finalized", ds, len(trajs), "cache", len(CACHE))

# =====================================================================
# 2. CORRECT-Error
df = pd.read_parquet(f"{R}/yifanyu__CORRECT-Error/data/test-00000-of-00001.parquet")
trajs = []
for _, r in df.iterrows():
    hist = L(r["history"]); ms = int(r["mistake_step"]); segs = []
    for i, m in enumerate(hist):
        rel = "prefix" if i < ms else ("injected_step" if i == ms else "post")
        for x in content_text(m.get("content")): segs.append((x, rel))
    add_task(segs, r["question"], [s for s, _ in segs[:2]])
    q = r["question"]
    trajs.append(dict(ds="CORRECT-Error", cls="injected", framework="Magentic-One", benchmark=r["dataset"], model=r["generator_model"],
                      steps=len(hist), segs=segs, question=q, id=r["trajectory_id"], med=med_heuristic(q), med_source="heuristic"))
finalize("CORRECT-Error", trajs); del df, trajs; gc.collect()

# =====================================================================
# 3. AFTraj
def aftraj_bench(cid, dom):
    p = cid.split("_")
    if p[0] in ("math", "gaia", "hotpotqa"): return {"math": "MATH", "gaia": "GAIA", "hotpotqa": "HotpotQA"}[p[0]]
    if p[0] == "coding": return "coding/" + p[1]
    if p[0] == "safe": return "agentic/" + "_".join(p[1:3])
    return dom + "/" + "_".join(p[:2])
def turn_texts(t):
    out = []
    for k in ("thought", "content"):
        if nonnull(t.get(k)): out.append(t[k])
    a = t.get("action")
    if nonnull(a):
        j = J(a)
        if isinstance(j, list):
            for c in j:
                if isinstance(c, dict): out += strs_from_args(c.get("arguments", c.get("args")))
                elif isinstance(c, str): out.append(c)
        elif isinstance(j, dict): out += strs_from_args(j.get("arguments", j.get("args", j)))
        else: out.append(a)
    return out
trajs = []
for split in ["safe", "unsafe"]:
    df = pd.read_parquet(f"{R}/ZBox008003__AFTraj/aftraj_{split}.parquet")
    for _, r in df.iterrows():
        turns = L(r["turns"]); segs = []
        if split == "safe": cls = "clean"; ms = None
        else:
            cls = "injected" if r["unsafe_source"] == "injected" else "natural_fail"; ms = int(r["mistake_step"])
        for i, t in enumerate(turns):
            rel = "turn" if ms is None or cls != "injected" else ("prefix" if i < ms else ("injected_step" if i == ms else "post"))
            for x in turn_texts(t): segs.append((x, rel))
        add_task(segs, r["task"], [s for s, _ in segs[:2]])
        trajs.append(dict(ds="AFTraj", cls=cls, framework="AFTraj-MAS", benchmark=aftraj_bench(r["conv_id"], r["domain"]), domain=r["domain"],
                          steps=len(turns), segs=segs, question=r["task"], id=r["conv_id"], med=med_heuristic(r["task"]), med_source="heuristic",
                          unsafe_source=(r.get("unsafe_source") if split == "unsafe" else None)))
finalize("AFTraj", trajs); del df, trajs; gc.collect()

# =====================================================================
# 4. ARIA
SUBJ_RE = re.compile(r"^Subject:\s*([A-Za-z_]+)", re.M)
aria_rollup = collections.Counter()
for split in ["train", "validation", "test"]:
    df = pd.read_parquet(f"{R}/Edlison__ARIA/data/{split}.parquet")
    trajs = []
    for _, r in df.iterrows():
        segs = []; nsteps = 0
        evs = L(r["trajectory"])
        acts = [e["content"] for e in evs if e.get("kind") == "after_act" and nonnull(e.get("content"))]
        for e in evs:
            c = e.get("content") or ""; tcs = L(e.get("tool_calls")); trs = [x for x in L(e.get("tool_results")) if isinstance(x, str) and x.strip()]
            if not (c.strip() or tcs or trs): continue
            nsteps += 1
            kind = e.get("kind")
            if kind == "agent_run_completed":
                cov = sum(len(a) for a in set(acts) if a in c)
                part = "rollup_dup" if c and cov >= 0.8 * len(c) else "final"
                aria_rollup[part] += 1
                if c.strip(): segs.append((c, part))
                continue
            if kind == "workspace_artifact":
                if c.strip(): segs.append((c, "artifact"))
                continue
            if trs:
                if c == "\n".join(trs) or (c.strip() and all(x in c for x in trs)):
                    segs.append((c, "tool_result"))
                else:
                    if c.strip(): segs.append((c, "turn"))
                    for x in trs: segs.append((x, "tool_result"))
            elif c.strip(): segs.append((c, "turn"))
            for tc in tcs:
                if isinstance(tc, dict):
                    for x in strs_from_args(tc.get("arguments")): segs.append((x, "toolcall_arg"))
        add_task(segs, r["task"], [s for s, _ in segs[:2]])
        o = r["outcome"]; ok = bool(o.get("source_success")) if isinstance(o, dict) else False
        m = SUBJ_RE.search(r["task"] or "") if r["benchmark"] == "mmlu" else None
        subj = m.group(1) if m else None
        if r["benchmark"] == "mmlu":
            med = subj in MED_CORE; msrc = "mmlu_subject"
        else:
            med = med_heuristic(r["task"]); msrc = "heuristic"
        trajs.append(dict(ds="ARIA", cls=("clean" if ok else "natural_fail"), split=split, framework=r["mas"], benchmark=r["benchmark"], model=r["host_model"],
                          steps=nsteps, segs=segs, question=r["task"], id=r["id"], task_id=r["task_id"], mmlu_subject=subj, med=med, med_source=msrc,
                          med_border=(subj in MED_BORDER), exclude_parts={"rollup_dup"}))
    finalize("ARIA/" + split, trajs); del df, trajs; gc.collect()
log("ARIA rollup classification", dict(aria_rollup))

# =====================================================================
# 5. Who&When Pro mirror (Leoxx/whowhen_pro): text + video
def wwp_event_texts(e, fw):
    k = e.get("kind")
    if k == "action":
        parts = [e.get(x) for x in ("reasoning", "action", "code", "observation", "error")]
        return ["\n".join(x for x in parts if nonnull(x))]
    if k == "planning": return [e["plan"]] if nonnull(e.get("plan")) else []
    if k == "agent":
        out = [e["output"]] if nonnull(e.get("output")) else []
        led = J(e.get("ledger"))
        if led: out += strs_from_args(led)
        for ta in L(J(e.get("tool_actions"))):
            if isinstance(ta, dict): out += strs_from_args(ta.get("args"))
        return out
    if "output" in e and k is None: return [e["output"]] if nonnull(e.get("output")) else []
    out = content_text(e.get("content"))
    for tc in L(J(e.get("tool_calls"))):
        if isinstance(tc, dict): out += strs_from_args((tc.get("function") or {}).get("arguments", tc.get("arguments")))
    return out
def wwp_flag(e, fw):
    if "is_injected" in e: return truthy(e["is_injected"])
    if "injected" in e: return truthy(e["injected"])
    ph = J(e.get("phase"))
    if ph is not None: return ("injected" in ph) or ("injection_via" in e)
    return None
wwp_loc = collections.Counter()
for modality in ["text", "video"]:
    trajs = []
    with open(f"{R}/Leoxx__whowhen_pro/data/{modality}.jsonl") as f:
        for line in f:
            r = json.loads(line); fw = r["framework"]; task = J(r["task"]) or {}; gt = J(r["ground_truth"]) or {}
            traj = J(r["trajectory"]) or []
            q = task.get("query") if isinstance(task, dict) else None
            segs = []; seen_inj = False; located = False; nsteps = 0
            gstep = gt.get("step") if fw in ("alfagent", "smolagents") else None
            last_sn = 0
            for e in traj:
                k = e.get("kind")
                if k == "round":
                    for t in L(e.get("turns")):
                        nsteps += 1
                        fl = truthy(t.get("is_injected"))
                        if fl: seen_inj = located = True; rel = "injected_step"
                        else: rel = "post" if seen_inj else "prefix"
                        if nonnull(t.get("output")): segs.append((t["output"], rel))
                    continue
                texts = [x for x in wwp_event_texts(e, fw) if isinstance(x, str) and x.strip()]
                if k not in ("user", "system", "final_answer"): nsteps += 1
                if k in ("user", "system"): rel = "prefix"
                elif gstep is not None:
                    if "step_number" in e:
                        sn = int(e["step_number"]); last_sn = sn
                        rel = "prefix" if sn < gstep else ("injected_step" if sn == gstep else "post")
                        if sn == gstep: located = True
                    else:
                        rel = "prefix" if (last_sn + 1) <= gstep else "post"
                        if k == "final_answer": rel = "post"
                else:
                    fl = wwp_flag(e, fw)
                    if fl: seen_inj = located = True; rel = "injected_step"
                    else: rel = "post" if seen_inj else "prefix"
                for x in texts: segs.append((x, rel))
            if not located: segs = [(s, "unlocated") for s, _ in segs]
            wwp_loc[(modality, fw, located)] += 1
            add_task(segs, q if isinstance(q, str) else None, [s for s, _ in segs[:3]])
            trajs.append(dict(ds="WhoWhenPro-mirror", modality=modality, cls="injected", framework=fw, benchmark=r["benchmark"], steps=nsteps,
                              segs=segs, question=q if isinstance(q, str) else None, id=r["id"], mode=gt.get("mode"),
                              med=med_heuristic(q), med_source="heuristic"))
    finalize("WhoWhenPro-mirror/" + modality, trajs); del trajs; gc.collect()
log("WWP injection located", {f"{a}/{b}/{c}": v for (a, b, c), v in wwp_loc.items()})

# =====================================================================
# 6. AgentErrorBench (single-agent; user prompts re-embed history -> within-trace unique lines as primary)
for split in ["train", "validation", "test"]:
    df = pd.read_parquet(f"{R}/davide221__agenterrorbench/data/{split}-00000-of-00001.parquet")
    trajs = []
    for _, r in df.iterrows():
        ft = json.loads(r["full_trajectory"]); msgs = ft.get("messages", [])
        segs = []
        for m in msgs:
            for x in content_text(m.get("content")):
                for ln in x.split("\n"):
                    if ln.strip(): segs.append((ln, "user_prompt" if m.get("role") == "user" else "assistant"))
        first = msgs[0]["content"] if msgs and isinstance(msgs[0].get("content"), str) else ""
        mq = re.search(r"Task:\s*(.*?)\n\s*\n", first, re.S) or re.search(r"[Yy]our task is:?\s*(?:to:?)?\s*(.*?)\n", first)
        q = mq.group(1).strip() if mq else None
        trajs.append(dict(ds="AgentErrorBench", cls="natural_fail", split=split, framework="single-agent (AgentDebug)", benchmark=r["task_type"],
                          model=r["llm_model"], steps=int(r["num_steps"]), segs=segs, question=q, id=r["trajectory_id"], cumulative=True,
                          med=med_heuristic(q), med_source="heuristic", raw_chars=int(r["trajectory_length"])))
    finalize("AgentErrorBench/" + split, trajs); del df, trajs; gc.collect()

# =====================================================================
# 7. MAScope bench (raw string traces -> blank-line paragraphs, same as MAST in measure.py)
def mast_question(s):
    pats = [r"problem_statement:\s*\n?(.*?)\n\S[^\n]*?:", r"\*\*task_prompt\*\*:\s*(.*?)\n\n", r"CONTENT:\n(.*?)\n-{10,}",
            r"\*{10,} Task \d+/\d+ \([^)]*\)\s*\*{10,}\n(.*?)\n"]
    for p in pats:
        m = re.search(p, s[:200000], re.S)
        if m and len(m.group(1).strip()) > 10: return m.group(1).strip()
    return None
HDR = re.compile(r"^\[[^\]\n]{1,80}\]\s*$", re.M)
for cfg in ["MAST-clean", "LG-Ctrl", "Inject-Mix"]:
    trajs = []
    with open(f"{R}/mascope__mascope-bench/{cfg}.jsonl") as f:
        for line in f:
            r = json.loads(line); s = r["trajectory"] or ""
            paras = [p for p in re.split(r"\n\s*\n", s) if p.strip()]
            segs = [(p, "log_paragraph") for p in paras]
            q = r.get("task_description") or mast_question(s)
            if cfg != "MAST-clean": add_task(segs, r.get("task_description"), [s[:20000]])
            if cfg == "MAST-clean": cls = "natural_fail"
            elif cfg == "LG-Ctrl": cls = "injected" if r.get("anomaly_injected") else "clean"
            else: cls = "clean" if r.get("anomaly_type") in (None, "None", "") else "injected"
            trajs.append(dict(ds="MAScope/" + cfg, cls=cls, framework=r["framework"], benchmark=r["benchmark_name"], model=r["llm_name"],
                              steps=(None if cfg == "MAST-clean" else len(HDR.findall(s))), segs=segs, question=q, id=r["trace_id"],
                              topology=r["guo_topology"], anomaly=str(r.get("anomaly_type")), med=med_heuristic(q), med_source="heuristic",
                              any_mast_label=any(v for v in (r.get("mast_annotation") or {}).values())))
    finalize("MAScope/" + cfg, trajs); del trajs; gc.collect()

# =====================================================================
# 9. ATBench (single-agent safety trajectories)
for cfg, key, idk in [("ATBench", "contents", "id"), ("ATBench500", "content", "conv_id")]:
    d = json.load(open(f"{R}/AI45Research__ATBench/{cfg}/test.json"))
    trajs = []
    for r in d:
        segs = []; n = 0
        for conv in r[key]:
            for m in conv:
                n += 1
                if m.get("role") == "agent":
                    if nonnull(m.get("thought")): segs.append((m["thought"], "turn"))
                    a = J(m.get("action"))
                    if isinstance(a, dict): segs += [(x, "toolcall_arg") for x in strs_from_args(a.get("arguments"))]
                    elif nonnull(m.get("action")): segs.append((m["action"], "turn"))
                else:
                    for x in content_text(m.get("content")): segs.append((x, "tool_result" if m.get("role") == "environment" else "turn"))
        q = next((m.get("content") for conv in r[key] for m in conv if m.get("role") == "user"), None)
        trajs.append(dict(ds="ATBench/" + cfg, cls=("injected" if r["label"] == 1 else "clean"), framework="single-agent (synthetic)",
                          benchmark=r.get("risk_source") if r["label"] == 1 else "safe", steps=n, segs=segs, question=q, id=str(r[idk]),
                          med=med_heuristic(q), med_source="heuristic"))
    finalize("ATBench/" + cfg, trajs); del trajs, d; gc.collect()

# =====================================================================
# Old-dataset segment hashes + questions (same segmentation as measure.py) for cross-dataset dedup
OLD_SEG = {}; OLD_Q = collections.defaultdict(set)
def addold(ds, s):
    if isinstance(s, str) and s.strip(): OLD_SEG.setdefault(h(s), ds)
for sp in ["train", "validation", "test"]:
    df = pd.read_parquet(f"{R}/Fancylalala__AEGIS/default/{sp}/0000.parquet")
    for inp in df["input"]:
        o = json.loads(inp); addold("AEGIS", o["query"]); OLD_Q["AEGIS"].add(norm(o["query"]))
        for t in o.get("conversation_history", []):
            for x in content_text(t.get("content")): addold("AEGIS", x)
        if o.get("final_output"):
            for x in content_text(o["final_output"]): addold("AEGIS", x)
df = pd.read_parquet(f"{R}/mcemri__MAST-Data/default/train/0000.parquet")
MAST_ROWS = []
for _, r in df.iterrows():
    s = r["trace"]["trajectory"]
    for p in re.split(r"\n\s*\n", s):
        if p.strip(): addold("MAST", p)
    q = mast_question(s)
    if q: OLD_Q["MAST"].add(norm(q))
    MAST_ROWS.append((r["mas_name"], r["benchmark_name"], r["llm_name"], str(r["trace_id"]), s))
for cfg in ["Algorithm-Generated", "Hand-Crafted"]:
    df = pd.read_parquet(f"{R}/Kevin355__Who_and_When/{cfg}/train/0000.parquet")
    for _, r in df.iterrows():
        OLD_Q["Who&When"].add(norm(r["question"])); addold("Who&When", r["question"])
        for m in r["history"]:
            for x in content_text(m.get("content")): addold("Who&When", x)
z = zipfile.ZipFile(f"{R}/TraceElephant__TraceElephant/data.zip")
for n in z.namelist():
    if n.endswith("trace_metadata.json"):
        meta = json.loads(z.read(n))
        if meta.get("task_instruction"): OLD_Q["TraceElephant"].add(norm(meta["task_instruction"])); addold("TraceElephant", meta["task_instruction"])
    if n.endswith("step_records.json"):
        for s in json.loads(z.read(n)):
            for m in s.get("input", {}).get("messages", []):
                for x in content_text(m.get("content")): addold("TraceElephant", x)
            for ch in (s.get("output") or {}).get("choices", []):
                for x in content_text((ch.get("message") or {}).get("content")): addold("TraceElephant", x)
inv = json.load(open(f"{OUT}/wwp_inventory.json"))
OLD_WWP_TEXT = {}
for rec in inv["inventory"]:
    if rec["kind"] != "file": continue
    o = json.load(open(rec["local"]))
    q = (o.get("task") or {}).get("query")
    if isinstance(q, str): OLD_Q["Who&When-Pro(tmpxv7)"].add(norm(q)); addold("Who&When-Pro(tmpxv7)", q)
    txts = []
    for t in (o.get("trajectory") or []):
        if "step_number" in t:
            txt = "\n".join(x for x in [t.get("reasoning"), t.get("action"), t.get("observation")] if isinstance(x, str) and x.strip())
        else:
            parts = content_text(t.get("content"))
            for tc in (t.get("tool_calls") or []):
                if isinstance(tc, dict): parts += strs_from_args((tc.get("function") or {}).get("arguments", tc.get("arguments")))
            txt = "\n".join(parts)
        if txt.strip(): addold("Who&When-Pro(tmpxv7)", txt); txts.append(txt)
    OLD_WWP_TEXT[o.get("id")] = (rec["modality"], rec["benchmark"], h("\x00".join(txts)), h(norm(q)) if isinstance(q, str) else None)
del df, z; gc.collect()
log("old segments", len(OLD_SEG), {k: len(v) for k, v in OLD_Q.items()})

# =====================================================================
# Summaries
def pct(a, q): return int(np.percentile(a, q)) if len(a) else None
def summarize(ts):
    a = np.array([t["tok_primary"] for t in ts])
    st = [t["steps"] for t in ts if t.get("steps") is not None]
    seen = set(); g = 0; old = 0; oldby = collections.Counter()
    for t in ts:
        for k, n, p in t["seghashes"]:
            if k not in seen:
                seen.add(k); g += n
                if k in OLD_SEG: old += n; oldby[OLD_SEG[k]] += n
    parts = collections.Counter()
    for t in ts: parts.update(t["tok_by_part"])
    return dict(n=len(ts), steps_total=(int(sum(st)) if st else None), steps_p50=(pct(st, 50) if st else None),
                tokens_total=int(a.sum()) if len(a) else 0, tokens_raw_as_stored=int(sum(t["tok_raw_incl_excluded"] for t in ts)),
                tokens_global_exact_dedup=int(g), dedup_tokens_also_in_old_sets=int(old), dedup_tokens_in_old_by_ds=dict(oldby),
                p50=pct(a, 50), p90=pct(a, 90), p99=pct(a, 99), max=int(a.max()) if len(a) else None,
                n_gt_8k=int((a > 8192).sum()), n_gt_32k=int((a > 32768).sum()), tokens_by_part=dict(parts))
def by(ts, key):
    g = collections.defaultdict(list)
    for t in ts: g[key(t) if callable(key) else t.get(key)].append(t)
    return {str(k): summarize(v) for k, v in sorted(g.items(), key=lambda kv: -sum(x["tok_primary"] for x in kv[1]))}

GROUPS = collections.OrderedDict([
    ("CORRECT-Error", lambda t: t["ds"] == "CORRECT-Error"),
    ("AFTraj", lambda t: t["ds"] == "AFTraj"),
    ("ARIA", lambda t: t["ds"] == "ARIA"),
    ("WhoWhenPro-mirror (text)", lambda t: t["ds"] == "WhoWhenPro-mirror" and t["modality"] == "text"),
    ("WhoWhenPro-mirror (video)", lambda t: t["ds"] == "WhoWhenPro-mirror" and t["modality"] == "video"),
    ("AgentErrorBench", lambda t: t["ds"] == "AgentErrorBench"),
    ("MAScope/MAST-clean", lambda t: t["ds"] == "MAScope/MAST-clean"),
    ("MAScope/LG-Ctrl", lambda t: t["ds"] == "MAScope/LG-Ctrl"),
    ("MAScope/Inject-Mix", lambda t: t["ds"] == "MAScope/Inject-Mix"),
    ("ATBench/ATBench", lambda t: t["ds"] == "ATBench/ATBench"),
    ("ATBench/ATBench500", lambda t: t["ds"] == "ATBench/ATBench500"),
])
stats = {}
for name, f in GROUPS.items():
    ts = [t for t in TRAJ if f(t)]
    e = dict(overall=summarize(ts), by_class=by(ts, "cls"), by_benchmark=by(ts, "benchmark"), by_framework=by(ts, "framework"))
    if any("model" in t for t in ts): e["by_model"] = by(ts, "model")
    if any("split" in t for t in ts): e["by_split"] = by(ts, "split")
    if name == "AFTraj": e["by_domain_class"] = by(ts, lambda t: f'{t["domain"]}/{t["cls"]}')
    if name.startswith("WhoWhenPro"): e["by_benchmark_framework"] = by(ts, lambda t: f'{t["benchmark"]}/{t["framework"]}')
    if name.startswith("MAScope"): e["by_topology"] = by(ts, "topology"); e["by_anomaly"] = by(ts, "anomaly"); e["n_with_any_mast_label"] = sum(t["any_mast_label"] for t in ts)
    e["unique_questions"] = len({norm(t["question"]) for t in ts if t.get("question")})
    e["medical"] = dict(n=sum(t["med"] for t in ts), tokens=int(sum(t["tok_primary"] for t in ts if t["med"])),
                        sources=dict(collections.Counter(t["med_source"] for t in ts if t["med"])),
                        examples=[t["question"][:160] for t in ts if t["med"]][:5])
    # injected-set prefix/injected/post split + prefix dedup by (task, exact segment)
    pr = collections.Counter(); seen = set(); dp = 0
    for t in ts:
        if t["cls"] != "injected": continue
        for k, n, p in t["seghashes"]:
            pr[p] += n
            if p in ("prefix", "task"):
                kk = (norm(t["question"] or "")[:200], k)
                if kk not in seen: seen.add(kk); dp += n
    if pr: e["injected_parts"] = dict(pr, prefix_dedup_by_task_exact_segment=dp)
    stats[name] = e
    log("summary", name, e["overall"]["n"], e["overall"]["tokens_total"])

# ---------- ARIA MMLU medical subjects ----------
aria = [t for t in TRAJ if t["ds"] == "ARIA"]
mm = [t for t in aria if t["benchmark"] == "mmlu"]
subj = collections.defaultdict(list)
for t in mm: subj[t["mmlu_subject"]].append(t)
stats["ARIA"]["mmlu"] = dict(
    n=len(mm), n_subject_detected=sum(1 for t in mm if t["mmlu_subject"]), tokens=int(sum(t["tok_primary"] for t in mm)),
    medical_core_subjects=sorted(MED_CORE), borderline_subjects=sorted(MED_BORDER),
    medical_core=dict(n=sum(1 for t in mm if t["mmlu_subject"] in MED_CORE), tokens=int(sum(t["tok_primary"] for t in mm if t["mmlu_subject"] in MED_CORE)),
                      dedup_tokens=summarize([t for t in mm if t["mmlu_subject"] in MED_CORE])["tokens_global_exact_dedup"] if any(t["mmlu_subject"] in MED_CORE for t in mm) else 0),
    borderline=dict(n=sum(1 for t in mm if t["mmlu_subject"] in MED_BORDER), tokens=int(sum(t["tok_primary"] for t in mm if t["mmlu_subject"] in MED_BORDER))),
    per_subject={k: dict(n=len(v), tokens=int(sum(t["tok_primary"] for t in v))) for k, v in sorted(subj.items(), key=lambda kv: -len(kv[1]))},
    per_medical_subject_by_split={k: dict(collections.Counter(t["split"] for t in v)) for k, v in subj.items() if k in MED_CORE},
    unique_mmlu_questions=len({norm(t["question"]) for t in mm}))
stats["ARIA"]["rollup_classification"] = dict(aria_rollup)
stats["ARIA"]["note_tool_results"] = "tool_result part = after_act contents equal to/containing tool_results (counted once); OpenManus agent_run_completed rollups that re-concatenate >=80% after_act text are excluded (rollup_dup)"
stats["WhoWhenPro-mirror (text)"]["injection_located"] = {f"{a}/{b}/{c}": v for (a, b, c), v in wwp_loc.items()}

# ---------- MAST-clean vs MAST-Data ----------
mc_rows = [json.loads(l) for l in open(f"{R}/mascope__mascope-bench/MAST-clean.jsonl")]
exact = {}; normd = {}
for i, (mas, b, llm, tid, s) in enumerate(MAST_ROWS):
    exact.setdefault(h(s), []).append(i); normd.setdefault(h(norm(s)), []).append(i)
mpara = []; pidx = collections.defaultdict(set)
for i, (mas, b, llm, tid, s) in enumerate(MAST_ROWS):
    ps = {h(p) for p in re.split(r"\n\s*\n", s) if p.strip()}; mpara.append(ps)
    for k in ps: pidx[k].add(i)
res = collections.Counter(); best_list = []
for r in mc_rows:
    s = r["trajectory"] or ""
    if h(s) in exact: res["exact_string"] += 1; best_list.append(1.0); continue
    if h(norm(s)) in normd: res["exact_after_whitespace_norm"] += 1; best_list.append(1.0); continue
    ps = {h(p) for p in re.split(r"\n\s*\n", s) if p.strip()}
    cand = collections.Counter()
    for k in ps:
        if len(pidx.get(k, ())) <= 50:
            for i in pidx.get(k, ()): cand[i] += 1
    best = 0.0
    for i, _ in cand.most_common(10):
        jac = len(ps & mpara[i]) / max(1, len(ps | mpara[i])); best = max(best, jac)
    best_list.append(best)
    if best >= 0.9: res["near_jaccard_ge_0.9"] += 1
    elif best >= 0.5: res["partial_jaccard_0.5_0.9"] += 1
    elif best > 0: res["weak_jaccard_lt_0.5"] += 1
    else: res["no_match"] += 1
mcs = [t for t in TRAJ if t["ds"] == "MAScope/MAST-clean"]
stats["MAScope/MAST-clean"]["overlap_with_MAST_Data"] = dict(n=len(mc_rows), counts=dict(res),
    duplicates_exact_or_near=int(res["exact_string"] + res["exact_after_whitespace_norm"] + res["near_jaccard_ge_0.9"]),
    jaccard_p10_p50=[float(np.percentile(best_list, 10)), float(np.percentile(best_list, 50))],
    dedup_tokens=stats["MAScope/MAST-clean"]["overall"]["tokens_global_exact_dedup"],
    dedup_tokens_not_in_MAST_paragraphs=stats["MAScope/MAST-clean"]["overall"]["tokens_global_exact_dedup"] - stats["MAScope/MAST-clean"]["overall"]["dedup_tokens_in_old_by_ds"].get("MAST", 0),
    framework_counts_MAST_Data=dict(collections.Counter(x[0] for x in MAST_ROWS)), framework_counts_MAST_clean=dict(collections.Counter(r["framework"] for r in mc_rows)))
del MAST_ROWS, mpara, pidx, exact, normd; gc.collect()

# ---------- WWP mirror vs tmpxv7 real files ----------
w_text = [t for t in TRAJ if t["ds"] == "WhoWhenPro-mirror"]
old_by_q = collections.defaultdict(list)
for oid, (mod, b, th, qh) in OLD_WWP_TEXT.items(): old_by_q[(mod, qh)].append(th)
seg_old_cov = collections.Counter(); qmatch = collections.Counter(); full_eq = collections.Counter()
for t in w_text:
    if t["benchmark"] not in ("alfworld", "lvbench"): continue
    key = (t["modality"], h(norm(t["question"])) if t.get("question") else None)
    if key in old_by_q: qmatch[t["modality"]] += 1
    tot = sum(n for k, n, p in t["seghashes"]); inold = sum(n for k, n, p in t["seghashes"] if OLD_SEG.get(k) == "Who&When-Pro(tmpxv7)")
    if tot and inold / tot >= 0.95: full_eq[t["modality"]] += 1
stats["WhoWhenPro-mirror (text)"]["vs_tmpxv7_real_files"] = dict(
    tmpxv7_real=dict(collections.Counter(v[0] for v in OLD_WWP_TEXT.values())),
    mirror_traces_with_query_in_tmpxv7=dict(qmatch), mirror_traces_with_ge95pct_tokens_in_tmpxv7_segments=dict(full_eq),
    mirror_text_traces=sum(1 for t in w_text if t["modality"] == "text"), mirror_video_traces=sum(1 for t in w_text if t["modality"] == "video"))

# ---------- cross-dataset question overlap ----------
def qkeys(q):
    n = norm(q) if isinstance(q, str) else ""
    return n, n[:60]
QS = collections.OrderedDict()
for name, f in GROUPS.items(): QS[name] = {qkeys(t["question"])[0] for t in TRAJ if f(t) and t.get("question") and len(norm(t["question"])) >= 20}
for k, v in OLD_Q.items(): QS["OLD:" + k] = {x for x in v if len(x) >= 20}
pref = {k: {x[:60] for x in v} for k, v in QS.items()}
cross = {}
for a in GROUPS:
    row = {}
    for b in QS:
        if a == b: continue
        ex = len(QS[a] & QS[b]); px = len(pref[a] & pref[b])
        if ex or px: row[b] = dict(exact=ex, first60=px)
    cross[a] = dict(n_questions=len(QS[a]), overlaps=row)
# GAIA questions embedded inside other datasets' tasks (prefix-60 substring of old GAIA-type questions in new questions)
stats["cross_dataset_question_overlap"] = dict(method="normalized task question (>=20 chars): exact equality and equality of first 60 normalized chars; OLD:* = already-measured sets", per_dataset=cross)

# ---------- grand total ----------
INCLUDE = [n for n in GROUPS if n != "WhoWhenPro-mirror (video)"]
single_agent = {"AgentErrorBench", "ATBench/ATBench", "ATBench/ATBench500"}
def grand(names, excl_med=True):
    A = set(); B = set(); ta = tb = 0; per = collections.defaultdict(lambda: [0, 0]); excl_old = excl_medtok = 0
    for phase in ("nat", "inj"):
        for name in names:
            for t in (t for t in TRAJ if GROUPS[name](t)):
                if (t["cls"] == "injected") != (phase == "inj"): continue
                if excl_med and t["med"]: continue
                for k, n, p in t["seghashes"]:
                    if k in A or k in B: continue
                    if k in OLD_SEG: excl_old += n; A.add(k) if phase == "nat" else B.add(k); continue
                    if phase == "nat": A.add(k); ta += n; per[name][0] += n
                    else: B.add(k); tb += n; per[name][1] += n
    return dict(natural_or_clean=ta, injected=tb, total=ta + tb, excluded_as_old_dup=excl_old, per_dataset={k: dict(natural_or_clean=v[0], injected=v[1]) for k, v in per.items()})
stats["grand_total_new"] = dict(
    rule="union over r53 datasets (text only; WWP video excluded; AgentRx gated; RAISER has no text), exact segment dedup across all r53 sets, segments already present in the old 5 sets removed, trajectories flagged medical removed (ARIA MMLU core-medical subjects + keyword heuristic >=2 distinct medical terms in the task question elsewhere); a segment shared by a natural/clean and an injected trajectory is credited to natural/clean",
    all=grand(INCLUDE), mas_only=grand([n for n in INCLUDE if n not in single_agent]),
    medical_excluded_trajectories={n: dict(n=stats[n]["medical"]["n"], tokens=stats[n]["medical"]["tokens"]) for n in INCLUDE})
stats["tokenizer"] = "Qwen/Qwen3-8B (HF), add_special_tokens=False, per-segment counts summed"
json.dump(stats, open(f"{OUT}/stats_r53_measure.json", "w"), indent=1, ensure_ascii=False, default=str)

with open(f"{OUT}/samples_r53.txt", "w") as f:
    for name, fn in GROUPS.items():
        ts = [t for t in TRAJ if fn(t)]
        for i in np.linspace(0, len(ts) - 1, 2).astype(int):
            t = ts[i]
            f.write(f"===== {name} | id={t['id']} | cls={t['cls']} | fw={t['framework']} | bench={t['benchmark']} | steps={t['steps']} | tokens={t['tok_primary']} | parts={t['tok_by_part']}\n")
log("DONE")
