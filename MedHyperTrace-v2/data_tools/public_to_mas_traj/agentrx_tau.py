"""AgentRx tau_retail (microsoft/AgentRx) -> mas-traj/1.  SINGLE AGENT (+ LLM user simulator).

29 failed tau-bench retail conversations. steps[] index 1 is the agent's system policy -> task.observations
("obs:policy"), not a step; user turns are LLM user-simulator steps; assistant turns are agent steps (a JSON
tool-call list becomes tool_calls with empty output); tool turns are tool steps. instruction (the user
persona's goal, given to the user simulator) -> task.query.
AgentRx magentic is the same text as Who&When Hand-Crafted: not converted again; its labels are attached in
whowhen.py.
Sources (protocol): the agent reads the policy and the whole conversation incl. tool results; the user
simulator reads only the agent's text replies and its own turns (tau-bench user simulation); a tool result
reads its call.
"""
import json
import os
from collections import Counter

from .common import cli, make_record, make_step, proto, question_id, src, tool_call

DATASET = "agentrx_tau"


def convert(raw):
    p = os.path.join(raw, "microsoft__AgentRx")
    labs = {"tau_retail_" + r["trajectory_id"]: r for r in map(json.loads, open(os.path.join(p, "tau_retail.jsonl")))}
    recs, rep = [], Counter()
    for r in map(json.loads, open(os.path.join(p, "tau_retail_dataset.jsonl"))):
        subs = [(s["index"], ss) for s in r["steps"] for ss in s["substeps"]]
        obs, steps, idx2sid = [], [], {}
        for idx, ss in subs:
            role, c = ss["role"], ss.get("content") or ""
            if role == "system":
                obs.append({"id": "obs:policy", "type": "text", "text": c})
                continue
            o = len(steps)
            if role == "assistant":
                calls = None
                try:
                    j = json.loads(c)
                    if isinstance(j, list) and j and all(isinstance(x, dict) and "function" in x for x in j):
                        calls = []
                        for x in j:
                            a = (x.get("function") or {}).get("arguments")
                            try:
                                a = json.loads(a)
                            except Exception:
                                pass
                            calls.append(dict(tool_call((x.get("function") or {}).get("name"), a), id=x.get("id")))
                except Exception:
                    pass
                sources = ([src("task:obs:policy", "verbatim", "protocol")] if obs else []) + proto([s["step_id"] for s in steps])
                st = make_step(o, "llm", "retail_agent", "assistant", "" if calls else c, phase="agent_turn",
                               sources=sources, tool_calls=calls)
            elif role == "user":
                seen = [s for s in steps if s["agent_id"] == "user_simulator" or
                        (s["agent_id"] == "retail_agent" and not s["tool_calls"])]
                st = make_step(o, "llm", "user_simulator", "user (LLM simulator)", c, phase="user_turn", sources=proto(seen))
            else:
                prev = [s for s in steps if s["agent_id"] == "retail_agent"]
                st = make_step(o, "tool", "tool:retail_api", "tool", c, phase="tool_result",
                               sources=proto(prev[-1:], "structured_field"),
                               tool_calls=[tool_call((prev[-1]["tool_calls"] or [{}])[0].get("name") if prev else None, None, c)])
            steps.append(st)
            idx2sid[idx] = st["step_id"]
        lab = labs.get(r["trajectory_id"])
        ext = {"dataset": "AgentRx", "taxonomy": "AgentRx failure categories", "labeled": lab is not None}
        if lab:
            ext.update(failure_summary=lab.get("failure_summary"),
                       failures=[dict(f, step_id=idx2sid.get(f.get("step_number"))) for f in lab.get("failures") or []],
                       root_cause_failure_id=lab.get("root_cause_failure_id"), root_cause_reason=lab.get("root_cause_reason"),
                       step_number_base="AgentRx steps[].index (1-based; index 1 = system policy, not a step)")
        native = r["trajectory_id"].replace("tau_retail_", "")
        recs.append(make_record(
            dataset=DATASET, benchmark="tau_retail", framework="tau_bench_agent", model=None,
            qid=question_id("tau_retail", native), query=r["instruction"], steps=steps, observations=obs,
            final_source_step_ids=[steps[-1]["step_id"]],
            labels={"is_correct": False, "external": ext,
                    "is_correct_source": "AgentRx: failed trajectories"},
            provenance={"source_record_id": r["trajectory_id"], "single_agent": True}))
        rep["kept"] += 1
        rep["labeled"] += lab is not None
    return recs, dict(rep)


if __name__ == "__main__":
    cli(convert, DATASET)
