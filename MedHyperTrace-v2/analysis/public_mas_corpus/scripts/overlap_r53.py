# r53: overlap of new public datasets with the medical MAA corpus (same check as overlap_bruteforce.py):
# (1) exact normalized task-question match, (2) first 60 normalized chars of each MAA query (>=40 chars) substring-searched in the
# full normalized text of every row (all string values, JSON-in-string parsed recursively), (3) planted positive control per dataset.
import json, re, time, gc, glob, pandas as pd, numpy as np
def norm(s): return re.sub(r"\s+", " ", s).strip().lower()
R = "/home/claude/public_mas/raw"
maa = set()
for l in open("/home/claude/data_maa_v2/maa_mas_traj.jsonl"):
    q = json.loads(l)["task"]["query"]
    if isinstance(q, str) and q.strip(): maa.add(norm(q))
probes = sorted({q[:60] for q in maa if len(q) >= 40})
def allstr(x, out):
    if isinstance(x, str):
        if x[:1] in "[{":
            try: allstr(json.loads(x), out); return
            except Exception: pass
        out.append(x)
    elif isinstance(x, dict):
        for v in x.values(): allstr(v, out)
    elif isinstance(x, (list, tuple, np.ndarray)):
        for v in x: allstr(v, out)
def rowtext(r):
    out = []; allstr(r, out); return norm(" ".join(out))
def parquet_rows(paths):
    for p in paths:
        df = pd.read_parquet(p)
        for r in df.to_dict("records"): yield r
def jsonl_rows(paths):
    for p in paths:
        for l in open(p): yield json.loads(l)
def aeb_q(r):
    m = json.loads(r["full_trajectory"])["messages"][0]["content"]
    mm = re.search(r"Task:\s*(.*?)\n\s*\n", m, re.S) or re.search(r"[Yy]our task is:?\s*(?:to:?)?\s*(.*?)\n", m)
    return mm.group(1) if mm else None
DS = [
 ("CORRECT-Error", lambda: parquet_rows([f"{R}/yifanyu__CORRECT-Error/data/test-00000-of-00001.parquet"]), lambda r: r["question"]),
 ("AFTraj", lambda: parquet_rows([f"{R}/ZBox008003__AFTraj/aftraj_{s}.parquet" for s in ["safe", "unsafe"]]), lambda r: r["task"]),
 ("ARIA", lambda: parquet_rows([f"{R}/Edlison__ARIA/data/{s}.parquet" for s in ["train", "validation", "test"]]), lambda r: r["task"]),
 ("WhoWhenPro-mirror", lambda: jsonl_rows([f"{R}/Leoxx__whowhen_pro/data/{s}.jsonl" for s in ["text", "video"]]), lambda r: (json.loads(r["task"]) or {}).get("query")),
 ("AgentErrorBench", lambda: parquet_rows([f"{R}/davide221__agenterrorbench/data/{s}-00000-of-00001.parquet" for s in ["train", "validation", "test"]]), aeb_q),
 ("MAScope", lambda: jsonl_rows([f"{R}/mascope__mascope-bench/{c}.jsonl" for c in ["MAST-clean", "LG-Ctrl", "Inject-Mix"]]), lambda r: r.get("task_description")),
 ("ATBench", lambda: (x for f, k in [("ATBench/test.json", "contents"), ("ATBench500/test.json", "content")] for x in json.load(open(f"{R}/AI45Research__ATBench/{f}"))),
  lambda r: next((m.get("content") for conv in (r.get("contents") or r.get("content")) for m in conv if m.get("role") == "user"), None)),
 ("RAISER", lambda: jsonl_rows(glob.glob(f"{R}/RogerYao__RAISER/data/**/*.jsonl", recursive=True)), lambda r: None),
]
ctrl = sorted(maa)[0]
res = {}
for name, it, qf in DS:
    t = time.time(); texts = []; nq = 0; exact = 0
    for r in it():
        q = qf(r)
        if isinstance(q, str) and q.strip():
            nq += 1; exact += norm(q) in maa
        texts.append(rowtext(r))
    big = "\x00".join(texts); del texts
    hits = [p for p in probes if p in big]
    ctl_big = big[:200000] + "\x00xx " + ctrl + " yy"
    res[name] = dict(rows_questions_checked=nq, exact_question_matches=exact, probes=len(probes), probe_hits=len(hits), hit_examples=hits[:3],
                     chars_searched=len(big), planted_control_found=(ctrl[:60] in ctl_big), sec=round(time.time() - t, 1))
    print(name, res[name], flush=True)
    del big, ctl_big; gc.collect()
json.dump(dict(maa_unique_queries=len(maa), probes=len(probes), per_dataset=res), open("/home/claude/public_mas/overlap_r53.json", "w"), indent=1)
print("DONE")
