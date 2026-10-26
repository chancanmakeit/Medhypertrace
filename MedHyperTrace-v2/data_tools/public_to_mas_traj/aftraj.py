"""AFTraj-2K (ZBox008003/AFTraj) -> mas-traj/1.

Kept: the safe split (1,162 verified-safe runs) and the NATURAL failures of the unsafe split
(unsafe_source == "diagnosed", 386). Skipped: unsafe_source == "injected" (728; out of scope, they are
injected). One AFTraj trajectory = one run; the system is identified per conversation from its roles:
  MathSolver / CodeWriter (+ Verifier / CodeTester, transfer_to_* calls)  -> agents_handoff
  Manager + search_agent (delegate(...), python_interpreter final_answer) -> smolagents
  Manager / *_Expert / Verification_Expert / Computer_terminal            -> aftraj_expert_team (family groupchat)
  TaskSolver only                                                          -> single_tool_agent (single agent)
turns[0] (role user) is the task (task.query), not a step; role environment / Computer_terminal -> tool steps.
No per-step inputs: sources by protocol (README "AFTraj"). Model not stored -> unknown-model.
"""
import json
import os
import re
from collections import Counter

import pandas as pd

from .common import cli, make_record, make_step, merge_sources, proto, question_id, slug, tool_call

DATASET = "aftraj"


def bench_of(cid, domain):
    p = cid.split("_")
    if p[0] in ("math", "gaia", "hotpotqa"):
        return {"math": "MATH", "gaia": "GAIA", "hotpotqa": "HotpotQA"}[p[0]]
    if p[0] == "coding":
        return {"humaneval": "HumanEval", "mbpp": "MBPP"}.get(p[1], "coding/" + p[1])
    m = re.match(r"(?:safe_|unsafe_)?(.*?)_run\d+_idx\d+$", cid)
    return "agentic/" + (m.group(1) if m else cid)


def framework_of(roles):
    if roles & {"MathSolver", "CodeWriter", "Verifier", "CodeTester"}:
        return "agents_handoff"
    if "search_agent" in roles:
        return "smolagents"
    if any(r.endswith("_Expert") for r in roles) or "Computer_terminal" in roles:
        return "aftraj_expert_team"
    if roles <= {"TaskSolver", "environment", "user"}:
        return "single_tool_agent"
    if "Manager" in roles:
        return "smolagents"
    return None


def nonnull(x):
    return isinstance(x, str) and x.strip() and x.strip().lower() not in ("null", "none")


def parse_action(a):
    if not nonnull(a) or a.strip() == "[ThoughtEvent]":
        return []
    try:
        j = json.loads(a)
        if isinstance(j, list):
            out = []
            for c in j:
                if isinstance(c, dict):
                    args = c.get("arguments", c.get("args"))
                    try:
                        args = json.loads(args) if isinstance(args, str) else args
                    except Exception:
                        pass
                    out.append(dict(tool_call(c.get("name"), args), id=c.get("id")))
            return out
    except Exception:
        pass
    calls = re.findall(r"call (\w+)\((.*?)\)(?:;|$)", a, re.S)
    if calls:
        out = []
        for n, args in calls:
            try:
                args = json.loads(args)
            except Exception:
                pass
            out.append(tool_call(n, args))
        return out
    m = re.match(r"(\w+)\((.*)\)\s*$", a.strip(), re.S)
    if m:
        return [tool_call(m.group(1), m.group(2))]
    return [tool_call(None, a)]


def convert(raw):
    recs, rep = [], Counter()
    for split in ("safe", "unsafe"):
        df = pd.read_parquet(os.path.join(raw, "ZBox008003__AFTraj", f"aftraj_{split}.parquet"))
        for r in df.itertuples(index=False):
            if split == "unsafe" and r.unsafe_source != "diagnosed":
                rep[f"skipped_injected"] += 1
                continue
            turns = [dict(t) for t in r.turns]
            roles = {t["role"] for t in turns}
            fw = framework_of(roles)
            if fw is None:
                rep["skipped_unknown_system"] += 1
                continue
            msgs, idx2order = [], {}
            for i, t in enumerate(turns):
                if i == 0 and t["role"] == "user":
                    continue
                th, ct = (t.get("thought") or ""), (t.get("content") or "")
                if t["role"] in ("environment", "Computer_terminal"):
                    text = ct if ct.strip() else th
                    kind, phase = "tool", ("code_execution" if t["role"] == "Computer_terminal" else "tool_result")
                    calls = [tool_call(t["role"], None, text)]
                else:
                    parts = ([th] if nonnull(th) and th.strip() not in ct else []) + ([ct] if ct.strip() else [])
                    text = "\n".join(parts)
                    kind, phase = "llm", f"{slug(t['role'])}_turn"
                    calls = parse_action(t.get("action"))
                idx2order[i] = len(msgs)
                msgs.append(dict(role=t["role"], text=text, kind=kind, phase=phase, calls=calls))
            srcs = []
            for i, m in enumerate(msgs):
                prev_llm = [j for j in range(i) if msgs[j]["kind"] == "llm"]
                if m["kind"] == "tool":
                    how = "excerpt" if m["phase"] == "code_execution" else "structured_field"
                    srcs.append(proto([f"s{prev_llm[-1]}"], how) if prev_llm else [])
                elif fw == "smolagents" and m["role"] == "search_agent":
                    mgr = [j for j in prev_llm if msgs[j]["role"] == "Manager"]
                    srcs.append(proto([f"s{mgr[-1]}"], "structured_field") if mgr else [])
                else:
                    srcs.append(proto([f"s{j}" for j in range(i)]))
            if not msgs:
                rep["skipped_no_steps"] += 1
                continue
            steps = [make_step(i, m["kind"], (f"tool:{slug(m['role'])}" if m["kind"] == "tool" else slug(m["role"])),
                               m["role"], m["text"], phase=m["phase"], sources=s, tool_calls=m["calls"])
                     for i, (m, s) in enumerate(zip(msgs, srcs))]
            ext = {"dataset": "AFTraj", "taxonomy": "AFTraj decisive error (k*, a*)", "split": split,
                   "conv_id": r.conv_id, "domain": r.domain}
            if split == "unsafe":
                k = int(r.mistake_step)
                ext.update(mistake_step=k, mistake_step_id=(f"s{idx2order[k]}" if k in idx2order else None),
                           mistake_step_base="index into turns (turns[0] = user task, not a step)",
                           mistake_agent=r.mistake_agent, mistake_reason=r.mistake_reason, unsafe_source=r.unsafe_source)
            bench = bench_of(r.conv_id, r.domain)
            fsrc = [steps[-1]["step_id"]]
            recs.append(make_record(
                dataset=DATASET, benchmark=bench, framework=fw, model=None,
                qid=question_id(bench, None, r.task), query=r.task, steps=steps, final_source_step_ids=fsrc,
                labels={"gold": r.gold_answer or None, "is_correct": split == "safe", "external": ext,
                        "is_correct_source": "AFTraj split (safe = verified safe run; unsafe/diagnosed = natural failure)"},
                provenance={"source_record_id": r.conv_id, "tools_available": [dict(t) for t in r.tools]}))
            rep[f"kept/{split}/{fw}"] += 1
    return recs, dict(rep)


if __name__ == "__main__":
    cli(convert, DATASET)
