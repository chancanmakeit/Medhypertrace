# r55: overlap of AgentRx and TRAIL with the medical MAA corpus (same check as overlap_r53.py / overlap_bruteforce.py):
# (1) exact normalized task-question match, (2) first 60 normalized chars of each MAA query (>=40 chars) substring-searched in the
# full normalized text of every row (all string values, JSON-in-string parsed recursively; for TRAIL the full raw trace + labels),
# (3) planted positive control per dataset.
# MAA source: public repo GuihaiChen1998/nature-sub-record, 'MedAgentAudit-datasets_and_logs-9.2 - 1.zip.00{1,2,3}' cat-merged and
# unzipped twice -> github_release_files/ -> python -m data_tools.maa_to_mas_traj -> /home/claude/data_maa_v2/maa_mas_traj.jsonl
# (steps 1-2 of MedHyperTrace-v2/scripts/prepare_maa.sh; 14,370 rows, as in r51/r53).
import os, json, re, time, gc, glob, pandas as pd, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "overlap_r53.py")).read()
exec(compile(src.split("DS = [", 1)[0], "overlap_r53.py:head", "exec"))   # norm, R, maa, probes, allstr, rowtext, parquet_rows, jsonl_rows
def lj(s):
    try: return json.loads(s)
    except Exception: return json.loads(re.sub(r",(\s*[\]}])", r"\1", s))
def trail_rows():
    for sp in ["gaia", "swe_bench"]:
        for tr, lb in pd.read_parquet(glob.glob(f"{R}/PatronusAI__TRAIL/data/{sp}-*.parquet")[0])[["trace", "labels"]].values:
            yield dict(split=sp, trace=lj(tr), labels=lj(lb))
def trail_q(r):
    for s in r["trace"]["spans"]:
        st = [s]
        while st:
            x = st.pop(); a = x.get("span_attributes") or {}
            if a.get("openinference.span.kind") == "AGENT":
                iv = a.get("input.value")
                try: t = json.loads(iv).get("task")
                except Exception: t = None
                if isinstance(t, str):
                    if r["split"] == "swe_bench":
                        m = re.search(r"<issue>\s*(.*?)\s*</issue>", t, re.S); return m.group(1) if m else t
                    m = re.search(r"Here is the task:\s*\n(.*)$", t, re.S); return m.group(1).strip() if m else t
            st += x.get("child_spans") or []
    return None
A = f"{R}/microsoft__AgentRx"
DS = [
 ("AgentRx", lambda: jsonl_rows([f"{A}/{f}" for f in ["magentic_dataset.jsonl", "tau_retail_dataset.jsonl", "magentic_one.jsonl", "tau_retail.jsonl"]]), lambda r: r.get("instruction")),
 ("TRAIL", trail_rows, trail_q),
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
json.dump(dict(maa_unique_queries=len(maa), probes=len(probes), per_dataset=res), open("/home/claude/public_mas/overlap_r55.json", "w"), indent=1)
print("DONE")
