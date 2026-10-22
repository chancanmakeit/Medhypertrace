# r55: token statistics for microsoft/AgentRx and PatronusAI/TRAIL (gated; downloaded with download_r55.py).
# Same protocol as measure_r53.py: Qwen3-8B tokenizer (add_special_tokens=False), natural-language trajectory content
# only; helper functions (tokenizer, count_tokens, finalize, med_heuristic, ...) are taken verbatim from measure_r53.py.
# Cross-set dedup uses prior_segments_r55.pkl (old 5 + all r53 sets, built by prior_segments_r55.py).
# Run: python -I measure_r55.py
import os, sys, json, re, ast, glob, pickle, collections, time
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "measure_r53.py")).read()
exec(compile(src.split("# 2. CORRECT-Error", 1)[0], "measure_r53.py:head", "exec"))   # R, OUT, tok, CACHE, h, count_tokens, norm, J, ... finalize
import numpy as np, pandas as pd

def lj(s):
    """json.loads; TRAIL has one labels string with a trailing comma -> retry with trailing commas removed"""
    try: return json.loads(s)
    except Exception: return json.loads(re.sub(r",(\s*[\]}])", r"\1", s))

# =====================================================================
# 1. AgentRx (trajectories config: magentic_dataset.jsonl, tau_retail_dataset.jsonl; labels: magentic_one.jsonl, tau_retail.jsonl)
A = f"{R}/microsoft__AgentRx"
lab_m = {r["trajectory_id"]: r for r in map(json.loads, open(f"{A}/magentic_one.jsonl"))}
lab_t = {"tau_retail_" + r["trajectory_id"]: r for r in map(json.loads, open(f"{A}/tau_retail.jsonl"))}
def tau_assistant_texts(c):
    """assistant content is either plain text or a JSON list of tool calls -> argument values only"""
    j = J(c)
    if isinstance(j, list) and j and all(isinstance(x, dict) and "function" in x for x in j):
        out = []
        for x in j: out += strs_from_args((x.get("function") or {}).get("arguments"))
        return [(s, "toolcall_arg") for s in out]
    return [(c, "turn")] if c.strip() else []
for split, fn, labs in [("magentic", "magentic_dataset.jsonl", lab_m), ("tau_retail", "tau_retail_dataset.jsonl", lab_t)]:
    trajs = []
    for r in map(json.loads, open(f"{A}/{fn}")):
        segs = []; roles = collections.Counter()
        for st in r["steps"]:
            for ss in st["substeps"]:
                c = ss.get("content") or ""; role = ss.get("role"); roles[role] += 1
                if split == "tau_retail" and role == "assistant": segs += tau_assistant_texts(c)
                elif c.strip(): segs.append((c, {"tool": "tool_result", "system": "system"}.get(role, "turn")))
        add_task(segs, r["instruction"], [s for s, _ in segs[:3]])
        lab = labs.get(r["trajectory_id"])
        trajs.append(dict(ds="AgentRx", split=split, cls="natural_fail",
                          framework=("Magentic-One" if split == "magentic" else "tau-bench retail (agent + LLM user simulator)"),
                          benchmark=("magentic_one (GAIA/AssistantBench)" if split == "magentic" else "tau_retail"),
                          steps=len(r["steps"]), segs=segs, question=r["instruction"], id=r["trajectory_id"], labeled=lab is not None,
                          n_failures=(lab or {}).get("num_failures"), med=med_heuristic(r["instruction"]), med_source="heuristic",
                          agents=sorted({re.sub(r"\s*\(.*\)$", "", k) for k in roles})))
    finalize("AgentRx/" + split, trajs); del trajs

# =====================================================================
# 2. TRAIL (OpenTelemetry/OpenInference span trees; data/*.parquet == the per-trace JSON files, verified identical)
# Within a trace every LLM call re-sends the agent memory, and LLM/tool/step outputs are re-wrapped into later inputs
# ("[FACTS LIST]: ...", "Call id: ...\nObservation: ..."). Rule: segments = every LLM input message (tool-call messages ->
# argument values) + LLM output contents/tool-call argument values + TOOL span argument values/outputs + CHAIN step outputs +
# AGENT task/final output + exception messages. Per-trajectory primary tokens = within-trace UNIQUE segments, after
# dropping output-side segments whose text is contained (substring) in an input message of the same trace (= already
# counted as memory). raw_as_stored = all segments incl. repeated context. Excluded: span metadata, tool schemas/descriptions,
# invocation parameters, OTel logs (function args/outputs of main/get_examples_to_answer incl. GAIA gold answers and
# annotator metadata), stack traces, labels/scores.
T = f"{R}/PatronusAI__TRAIL"
def walk(s, f, d=0):
    f(s, d)
    for c in s.get("child_spans") or []: walk(c, f, d + 1)
def toolcall_msg_values(c):
    body = c.split("\n", 1)[1] if c.startswith("Calling tools:") and "\n" in c else c
    try: calls = ast.literal_eval(body)
    except Exception: return None
    out = []
    for x in calls if isinstance(calls, list) else []:
        if isinstance(x, dict): out += strs_from_args((x.get("function") or {}).get("arguments"))
    return out
trail_stats = collections.Counter()
def trail_question(task, split):
    if split == "swe_bench":
        m = re.search(r"<issue>\s*(.*?)\s*</issue>", task, re.S); return m.group(1) if m else task
    m = re.search(r"Here is the task:\s*\n(.*)$", task, re.S); return m.group(1).strip() if m else task
for split in ["gaia", "swe_bench"]:
    df = pd.read_parquet(glob.glob(f"{T}/data/{split}-*.parquet")[0])
    trajs = []
    for tr_s, lb_s in df[["trace", "labels"]].values:
        tr = lj(tr_s); lb = lj(lb_s)
        Z = dict(inp=[], outp=[], nllm=0, nstep=0, agents=[], task=None, final=None)
        def f(s, d):
            a = s.get("span_attributes") or {}; kind = a.get("openinference.span.kind"); name = s.get("span_name") or ""
            if kind == "LLM":
                Z["nllm"] += 1; i = 0; msgs = []
                while f"llm.input_messages.{i}.message.role" in a or f"llm.input_messages.{i}.message.content" in a:
                    msgs.append((a.get(f"llm.input_messages.{i}.message.role"), a.get(f"llm.input_messages.{i}.message.content"))); i += 1
                if not msgs and nonnull(a.get("input.value")):
                    trail_stats["llm_input_from_input_value"] += 1
                    for m in (J(a["input.value"]) or {}).get("messages", []) if isinstance(J(a["input.value"]), dict) else []:
                        msgs.append((m.get("role"), "\n".join(content_text(m.get("content")))))
                for role, c in msgs:
                    if not isinstance(c, str) or not c.strip(): continue
                    if role == "tool-call":
                        v = toolcall_msg_values(c)
                        if v is None: trail_stats["toolcall_msg_unparsed"] += 1; Z["inp"].append((c, "input_toolcall"))
                        else: Z["inp"] += [(x, "input_toolcall") for x in v]
                    else: Z["inp"].append((c, {"system": "system", "tool-response": "input_tool_result"}.get(role, "input_message")))
                oc = a.get("llm.output_messages.0.message.content")
                if nonnull(oc): Z["outp"].append((oc, "output"))
                j = 0
                while f"llm.output_messages.0.message.tool_calls.{j}.tool_call.function.arguments" in a:
                    Z["outp"] += [(x, "output_toolcall") for x in strs_from_args(a[f"llm.output_messages.0.message.tool_calls.{j}.tool_call.function.arguments"])]; j += 1
            elif kind == "TOOL":
                iv = J(a.get("input.value"))
                if isinstance(iv, dict): Z["outp"] += [(x, "tool_arg") for x in strs_from_args([iv.get("args"), iv.get("kwargs")])]
                if nonnull(a.get("output.value")): Z["outp"].append((a["output.value"], "tool_result"))
            elif kind == "CHAIN":
                if name.startswith("Step"): Z["nstep"] += 1
                if nonnull(a.get("output.value")): Z["outp"].append((a["output.value"], "step_output"))
            elif kind == "AGENT":
                Z["agents"].append(name); iv = J(a.get("input.value"))
                t = iv.get("task") if isinstance(iv, dict) else None
                if Z["task"] is None and isinstance(t, str): Z["task"] = t
                if isinstance(t, str) and t.strip(): Z["outp"].append((t, "agent_task"))
                if nonnull(a.get("output.value")):
                    Z["outp"].append((a["output.value"], "agent_output"))
                    if d <= 2 and name == "CodeAgent.run": Z["final"] = a["output.value"]
            for e in s.get("events") or []:
                at = e.get("Attributes") or e.get("attributes") or {}
                if nonnull(at.get("exception.message")): Z["outp"].append((at["exception.message"], "exception_msg"))
        for s in tr["spans"]: walk(s, f)
        inp, outp, nllm, nstep, agents, task = Z["inp"], Z["outp"], Z["nllm"], Z["nstep"], Z["agents"], Z["task"]
        inp_text = "\x00".join(dict.fromkeys(x for x, _ in inp))
        kept = []; dropped = 0
        for x, p in outp:
            if x in inp_text: dropped += 1; continue
            kept.append((x, p))
        trail_stats["output_segments_contained_in_inputs"] += dropped; trail_stats["output_segments_kept"] += len(kept)
        segs = inp + kept
        q = trail_question(task or "", split)
        multi = "ToolCallingAgent.run" in agents
        errs = lb.get("errors") or []
        trajs.append(dict(ds="TRAIL", split=split, cls=("natural_fail" if errs else "no_annotated_error"),
                          framework=("smolagents OpenDeepResearch (CodeAgent manager + search_agent)" if split == "gaia" else "smolagents CodeAgent (single agent)"),
                          benchmark=("GAIA" if split == "gaia" else "SWE-bench Lite"), steps=nstep, n_llm_calls=nllm, segs=segs, question=q,
                          id=tr.get("trace_id"), cumulative=True, n_errors=len(errs), subagent_ran=multi,
                          impacts=dict(collections.Counter(e.get("impact") for e in errs)), categories=dict(collections.Counter(e.get("category") for e in errs)),
                          model=("o3-mini-2025-01-31" if split == "gaia" else "claude-3-7-sonnet-20250219"),
                          med=med_heuristic(q), med_source="heuristic"))
    finalize("TRAIL/" + split, trajs); del trajs, df
log("TRAIL parse stats", dict(trail_stats))

# =====================================================================
# prior sets (old 5 + r53) for cross-set dedup
PRI = pickle.load(open(f"{OUT}/prior_segments_r55.pkl", "rb"))
ORDER = ["OLD:Who&When", "OLD:TraceElephant", "OLD:MAST", "OLD:AEGIS", "OLD:Who&When-Pro(tmpxv7)"] + [k for k in PRI["seg"] if not k.startswith("OLD:")]
PRIOR_FIRST = {}
for k in ORDER:
    for x in PRI["seg"][k]: PRIOR_FIRST.setdefault(x, k)
log("prior hashes", len(PRIOR_FIRST), "from", ORDER)

def pct(a, q): return int(np.percentile(a, q)) if len(a) else None
def summarize(ts):
    a = np.array([t["tok_primary"] for t in ts]); st = [t["steps"] for t in ts if t.get("steps") is not None]
    seen = set(); g = 0; old = 0; oldby = collections.Counter(); oldany = collections.Counter()
    for t in ts:
        for k, n, p in t["seghashes"]:
            if k in seen: continue
            seen.add(k); g += n
            if k in PRIOR_FIRST:
                old += n; oldby[PRIOR_FIRST[k]] += n
                for s in ORDER:
                    if k in PRI["seg"][s]: oldany[s] += n
    parts = collections.Counter()
    for t in ts: parts.update(t["tok_by_part"])
    return dict(n=len(ts), steps_total=(int(sum(st)) if st else None), steps_p50=(pct(st, 50) if st else None),
                tokens_total=int(a.sum()) if len(a) else 0, tokens_raw_as_stored=int(sum(t["tok_raw_incl_excluded"] for t in ts)),
                tokens_global_exact_dedup=int(g), dedup_tokens_also_in_prior_sets=int(old), dedup_tokens_in_prior_first_match=dict(oldby),
                dedup_tokens_in_prior_any=dict(oldany), p50=pct(a, 50), p90=pct(a, 90), p99=pct(a, 99), max=int(a.max()) if len(a) else None,
                n_gt_8k=int((a > 8192).sum()), n_gt_32k=int((a > 32768).sum()), tokens_by_part=dict(parts))
def by(ts, key):
    g = collections.defaultdict(list)
    for t in ts: g[key(t) if callable(key) else t.get(key)].append(t)
    return {str(k): summarize(v) for k, v in sorted(g.items(), key=lambda kv: -sum(x["tok_primary"] for x in kv[1]))}

GROUPS = collections.OrderedDict([
    ("AgentRx", lambda t: t["ds"] == "AgentRx"),
    ("AgentRx/magentic", lambda t: t["ds"] == "AgentRx" and t["split"] == "magentic"),
    ("AgentRx/tau_retail", lambda t: t["ds"] == "AgentRx" and t["split"] == "tau_retail"),
    ("TRAIL", lambda t: t["ds"] == "TRAIL"),
    ("TRAIL/gaia", lambda t: t["ds"] == "TRAIL" and t["split"] == "gaia"),
    ("TRAIL/swe_bench", lambda t: t["ds"] == "TRAIL" and t["split"] == "swe_bench"),
    ("TRAIL/gaia (search_agent ran)", lambda t: t["ds"] == "TRAIL" and t["split"] == "gaia" and t["subagent_ran"]),
])
stats = {}
for name, fn in GROUPS.items():
    ts = [t for t in TRAJ if fn(t)]
    e = dict(overall=summarize(ts), by_class=by(ts, "cls"), by_benchmark=by(ts, "benchmark"), by_framework=by(ts, "framework"), by_split=by(ts, "split"))
    if name.startswith("TRAIL"): e["by_model"] = by(ts, "model")
    e["unique_questions"] = len({norm(t["question"]) for t in ts if t.get("question")})
    e["medical"] = dict(n=sum(t["med"] for t in ts), tokens=int(sum(t["tok_primary"] for t in ts if t["med"])),
                        sources=dict(collections.Counter(t["med_source"] for t in ts if t["med"])), examples=[t["question"][:160] for t in ts if t["med"]][:5])
    stats[name] = e
    log("summary", name, e["overall"]["n"], e["overall"]["tokens_total"], e["overall"]["tokens_global_exact_dedup"])

ax = [t for t in TRAJ if t["ds"] == "AgentRx"]
stats["AgentRx"]["labels"] = dict(magentic_traj=sum(t["split"] == "magentic" for t in ax), magentic_with_label=sum(t["labeled"] for t in ax if t["split"] == "magentic"),
                                  tau_traj=sum(t["split"] == "tau_retail" for t in ax), tau_with_label=sum(t["labeled"] for t in ax if t["split"] == "tau_retail"),
                                  failures_total=int(sum(t["n_failures"] or 0 for t in ax)))
stats["AgentRx"]["agents_per_split"] = {sp: dict(collections.Counter(a for t in ax if t["split"] == sp for a in t["agents"])) for sp in ("magentic", "tau_retail")}
# AgentRx magentic vs Who&When Hand-Crafted (same questions? same messages?)
ww = pd.read_parquet(f"{R}/Kevin355__Who_and_When/Hand-Crafted/train/0000.parquet")
wwq = {norm(q) for q in ww["question"]}; wwm = {h(m["content"]) for hist in ww["history"] for m in hist if isinstance(m.get("content"), str)}
md = [json.loads(l) for l in open(f"{A}/magentic_dataset.jsonl")]
nsub = sum(len(s["substeps"]) for r in md for s in r["steps"]); nin = sum(h(ss["content"]) in wwm for r in md for s in r["steps"] for ss in s["substeps"])
full = sum(all(h(ss["content"]) in wwm for s in r["steps"] for ss in s["substeps"]) for r in md)
stats["AgentRx"]["magentic_vs_WhoWhen_HandCrafted"] = dict(ww_hc_rows=len(ww), agentrx_magentic=len(md), instruction_exact_in_ww_hc=sum(norm(r["instruction"]) in wwq for r in md),
                                                           substeps=nsub, substeps_exact_in_ww_hc_messages=nin, trajectories_fully_contained=full)
tt = [t for t in TRAJ if t["ds"] == "TRAIL"]
stats["TRAIL"]["parse_stats"] = dict(trail_stats)
stats["TRAIL"]["labels"] = dict(errors_total=int(sum(t["n_errors"] for t in tt)), traces_with_errors=sum(t["n_errors"] > 0 for t in tt),
                                impacts=dict(sum((collections.Counter(t["impacts"]) for t in tt), collections.Counter())),
                                top_categories=dict(sum((collections.Counter(t["categories"]) for t in tt), collections.Counter()).most_common(12)),
                                gaia_traces_where_search_agent_ran=sum(t["subagent_ran"] for t in tt if t["split"] == "gaia"),
                                llm_calls_total=int(sum(t["n_llm_calls"] for t in tt)))

# ---------- cross-dataset question overlap ----------
QS = collections.OrderedDict()
for name in ["AgentRx/magentic", "AgentRx/tau_retail", "TRAIL/gaia", "TRAIL/swe_bench"]:
    QS[name] = {norm(t["question"]) for t in TRAJ if GROUPS[name](t) and t.get("question") and len(norm(t["question"])) >= 20}
for k, v in PRI["questions"].items(): QS[k] = v
pref = {k: {x[:60] for x in v} for k, v in QS.items()}
cross = {}
for a in ["AgentRx/magentic", "AgentRx/tau_retail", "TRAIL/gaia", "TRAIL/swe_bench"]:
    row = {}
    for b in QS:
        if a == b or (a.split("/")[0] == b.split("/")[0]): continue
        ex = len(QS[a] & QS[b]); px = len(pref[a] & pref[b])
        if ex or px: row[b] = dict(exact=ex, first60=px)
    cross[a] = dict(n_questions=len(QS[a]), overlaps=dict(sorted(row.items(), key=lambda kv: -kv[1]["first60"])))
stats["cross_dataset_question_overlap"] = dict(method="normalized task question (>=20 chars): exact equality and equality of first 60 normalized chars; OLD:* = r51 sets, others = r53 sets", per_dataset=cross)

# ---------- grand total of new tokens ----------
INCLUDE = ["AgentRx/magentic", "AgentRx/tau_retail", "TRAIL/gaia", "TRAIL/swe_bench"]
SINGLE = {"AgentRx/tau_retail", "TRAIL/swe_bench"}
def grand(names, excl_med=True):
    Aset = set(); Bset = set(); ta = tb = 0; per = collections.defaultdict(lambda: [0, 0]); excl_old = 0; exby = collections.Counter()
    for phase in ("nat", "inj"):
        for name in names:
            for t in (t for t in TRAJ if GROUPS[name](t)):
                if (t["cls"] == "injected") != (phase == "inj"): continue
                if excl_med and t["med"]: continue
                for k, n, p in t["seghashes"]:
                    if k in Aset or k in Bset: continue
                    if k in PRIOR_FIRST:
                        excl_old += n; exby[PRIOR_FIRST[k]] += n; (Aset if phase == "nat" else Bset).add(k); continue
                    if phase == "nat": Aset.add(k); ta += n; per[name][0] += n
                    else: Bset.add(k); tb += n; per[name][1] += n
    return dict(natural_or_clean=ta, injected=tb, total=ta + tb, excluded_as_prior_dup=excl_old, excluded_by_prior_set_first_match=dict(exby),
                per_dataset={k: dict(natural_or_clean=v[0], injected=v[1]) for k, v in per.items()})
stats["grand_total_new"] = dict(
    rule=("union over AgentRx + TRAIL (all trajectory text), exact segment dedup between them, segments already present in ANY previously measured set removed "
          "(old 5 from r51: AEGIS, MAST-Data, Who&When, TraceElephant, Who&When-Pro tmpxv7 real files; all r53 sets: CORRECT-Error, AFTraj, ARIA, Who&When-Pro mirror text+video, "
          "AgentErrorBench, MAScope MAST-clean/LG-Ctrl/Inject-Mix, ATBench, ATBench500; segmentation identical to r53), trajectories flagged medical removed "
          "(keyword heuristic >=2 distinct medical terms in the task question); a segment shared by a natural/clean and an injected trajectory is credited to natural/clean"),
    prior_sets_deduped_against=ORDER, prior_hashes=len(PRIOR_FIRST),
    all=grand(INCLUDE), mas_only=grand([n for n in INCLUDE if n not in SINGLE]),
    mas_only_strict=grand(["AgentRx/magentic", "TRAIL/gaia (search_agent ran)"]),
    mas_only_strict_definition="as mas_only, but TRAIL/gaia restricted to the traces in which the manager actually delegated to search_agent (ToolCallingAgent.run span present)", mas_only_definition="AgentRx/magentic (Magentic-One) + TRAIL/gaia (manager CodeAgent + search_agent); drops AgentRx/tau_retail (single agent + LLM user simulator) and TRAIL/swe_bench (single CodeAgent)",
    medical_excluded_trajectories={n: dict(n=sum(t["med"] for t in TRAJ if GROUPS[n](t)), tokens=int(sum(t["tok_primary"] for t in TRAJ if GROUPS[n](t) and t["med"]))) for n in INCLUDE})
stats["tokenizer"] = "Qwen/Qwen3-8B (HF), add_special_tokens=False, per-segment counts summed"
OUTF = sys.argv[1] if len(sys.argv) > 1 else f"{OUT}/stats_r55_measure.json"
json.dump(stats, open(OUTF, "w"), indent=1, ensure_ascii=False, default=str)
log("DONE", OUTF)
