"""MAScope benchmark (mascope/mascope-bench) -> mas-traj/1, CLEAN runs only.

  LG-Ctrl     : anomaly_injected == False (80 of 408; LangGraph, 4 topologies)
  Inject-Mix  : anomaly_type None (180 of 961; v2_debate / v2_autogen / v2_crewai)
  MAST-clean  : skipped (a deduplicated subset of MAST-Data, converted from MAST-Data itself)
Trajectory text = "[speaker]\\ncontent" blocks; only the known speaker names of each framework start a
block (bracketed config sections such as "[labshare]" inside a message are content). The opening [system]
session line is not a step. Sources by protocol per topology (README "MAScope").
mast_annotation (synthetic, from anomaly injection per the dataset note) -> labels.external.
"""
import json
import os
import re
from collections import Counter

from .common import cli, make_record, make_step, proto, question_id, slug, src

DATASET = "mascope"
HDR = re.compile(r"(?:^|\n\n)\[([A-Za-z_][\w ]{0,40})\]\n")
LG_FW = {"Layered": "langgraph_layered", "Centralized": "langgraph_centralized",
         "Decentralized": "langgraph_decentralized", "Shared Message Pool": "langgraph_shared_pool"}
IM_FW = {"v2_debate": "mascope_debate", "v2_autogen": "mascope_autogen", "v2_crewai": "mascope_crewai"}


def blocks(text, allowed):
    hs = [m for m in HDR.finditer(text) if allowed(m.group(1))]
    out = []
    for k, m in enumerate(hs):
        body = text[m.end(): hs[k + 1].start() if k + 1 < len(hs) else len(text)]
        out.append((m.group(1), body.strip("\n")))
    return out


def sources_for(fw, msgs):
    n = len(msgs)
    res = []
    if fw == "langgraph_layered":
        return [proto([f"s{i - 1}"]) if i else [] for i in range(n)]
    if fw in ("langgraph_shared_pool", "mascope_autogen"):
        return [proto([f"s{j}" for j in range(i)]) for i in range(n)]
    if fw in ("langgraph_decentralized", "mascope_debate"):
        k = len({m[0] for m in msgs})           # agents per round
        for i in range(n):
            r = i // k
            res.append(proto([f"s{j}" for j in range((r - 1) * k, r * k)]) if r else [])
        return res
    if fw == "langgraph_centralized":
        hub = msgs[0][0] if msgs else None
        for i, (spk, txt) in enumerate(msgs):
            if spk == hub:
                res.append(proto([f"s{j}" for j in range(i)]))
            else:
                last = [j for j in range(i) if msgs[j][0] == hub]
                how = "structured_field" if last and '"task"' in msgs[last[-1]][1][:400] else "verbatim"
                res.append(proto([f"s{last[-1]}"], how) if last else [])
        return res
    if fw == "mascope_crewai":
        plan = None
        try:
            plan = json.loads(msgs[0][1]) if msgs and msgs[0][0] == "leader" else None
        except Exception:
            plan = None
        tasks = (plan or {}).get("tasks") or []
        workers = list(range(1, n))
        aligned = len(tasks) == len(workers) and all(msgs[w][0] == t.get("assignee") for w, t in zip(workers, tasks))
        res.append([])
        for pos, w in enumerate(workers):
            if aligned:
                dep = [workers[d - 1] for d in tasks[pos].get("depends_on") or [] if 1 <= d <= len(workers)]
                res.append(proto(["s0"], "structured_field") + proto([f"s{d}" for d in dep]))
            else:
                res.append(proto([f"s{j}" for j in range(w)]))
        return res
    raise ValueError(fw)


def convert(raw):
    recs, rep = [], Counter()
    base = os.path.join(raw, "mascope__mascope-bench")
    for cfg in ("LG-Ctrl", "Inject-Mix"):
        for line in open(os.path.join(base, f"{cfg}.jsonl")):
            r = json.loads(line)
            clean = (not r.get("anomaly_injected")) if cfg == "LG-Ctrl" else r.get("anomaly_type") in (None, "None", "")
            if not clean:
                rep[f"skipped_injected/{cfg}"] += 1
                continue
            if cfg == "LG-Ctrl":
                fw = LG_FW[r["guo_topology"]]
                allowed = lambda h: h == "system" or re.fullmatch(r"agent_[A-Z]", h) is not None
            else:
                fw = IM_FW[r["framework"]]
                m = re.search(r"roles=\[([^\]]*)\]", r["trajectory"][:2000])
                roles = set(re.findall(r"'([^']+)'", m.group(1))) if m else set()
                names = {"mascope_debate": None, "mascope_autogen": {"manager", "coder", "reviewer", "verifier"},
                         "mascope_crewai": roles | {"leader"}}[fw]
                allowed = (lambda h, names=names: h == "system" or (h.startswith("debater_") if names is None else h in names))
            bl = blocks(r["trajectory"], allowed)
            msgs = [(s, t) for s, t in bl if s != "system"]
            rep[f"system_blocks_dropped"] += len(bl) - len(msgs)
            if not msgs:
                rep["skipped_no_steps"] += 1
                continue
            srcs = sources_for(fw, msgs)
            steps = [make_step(i, "llm", slug(s), s, t, phase=("hub" if fw == "langgraph_centralized" and s == msgs[0][0]
                                                             else "leader_plan" if s == "leader" else
                                                             "manager" if s == "manager" else "agent_turn"),
                               round_=(i // len({m[0] for m in msgs}) + 1) if fw in ("langgraph_decentralized", "mascope_debate") else None,
                               sources=x)
                     for i, ((s, t), x) in enumerate(zip(msgs, srcs))]
            tid = r["task_id"].split(":", 1)[1] if ":" in r["task_id"] else r["task_id"]
            bench = f"mascope_{r['benchmark_name']}"
            recs.append(make_record(
                dataset=DATASET, benchmark=bench, framework=fw, model=r.get("llm_name"),
                qid=question_id(bench, tid), query=r.get("task_description"), steps=steps,
                final_source_step_ids=[steps[-1]["step_id"]],
                labels={"is_correct": None, "external": {
                    "dataset": "MAScope", "taxonomy": "MAST-14 (synthetic, anomaly-injection derived)", "corpus": cfg,
                    "codes": r.get("mast_annotation"), "anomaly_type": r.get("anomaly_type"),
                    "anomaly_injected": r.get("anomaly_injected"), "guo_topology": r.get("guo_topology"),
                    "note": r.get("note")}},
                provenance={"source_record_id": r["trace_id"], "corpus": cfg, "task_id": r["task_id"]}))
            rep[f"kept/{cfg}/{fw}"] += 1
    return recs, dict(rep)


if __name__ == "__main__":
    cli(convert, DATASET)
