"""Who&When (Kevin355/Who_and_When) -> mas-traj/1.

Hand-Crafted   = Magentic-One logs (58), Algorithm-Generated = CaptainAgent nested group chats (126).
No per-step inputs: sources by protocol (README "Who&When").
Labels: mistake_agent / mistake_step / mistake_reason (+ mistake_type, is_corrected) -> labels.external;
AgentRx (microsoft/AgentRx, magentic split) annotates the SAME Hand-Crafted trajectories: attached as
labels.external.agentrx when every AgentRx substep equals the Who&When message at the same position.

  python -m data_tools.public_to_mas_traj.whowhen --raw /home/claude/public_mas/raw --out who_and_when.jsonl.gz
"""
import json
import os
import re

import pandas as pd

from .common import (cli, make_record, make_step, merge_sources, proto, question_id, slug, src, tool_call)

DATASET = "who_and_when"
_FA = re.compile(r"FINAL ANSWER:\s*(.+)")


def bench_of(qid):
    if re.fullmatch(r"[0-9a-f-]{36}", qid):
        return "GAIA"
    if re.fullmatch(r"[0-9a-f]{64}", qid):
        return "AssistantBench"
    return "unknown"


THOUGHT_PHASE = [("Initial plan", "plan"), ("New plan", "replan"), ("Updated Ledger", "progress_ledger"),
                 ("Next speaker", "next_speaker"), ("Stalled", "stalled"), ("Request satisfied", "request_satisfied"),
                 ("Replan counter exceeded", "replan_limit")]


# ---------------------------------------------------------------- Magentic-One (Hand-Crafted)
def magentic_steps(hist):
    """hist[0] is the human task message (= task.query, not a step). Returns steps and the order of each
    history index."""
    steps, idx2order = [], {}
    broadcast = []          # broadcast messages since the last (re)plan
    last_ledger = None
    for i, m in enumerate(hist):
        role, text = m["role"], m.get("content") or ""
        if i == 0 and role == "human":
            continue
        order = len(steps)
        idx2order[i] = order
        if role.startswith("Orchestrator"):
            kind, aid = "llm", "orchestrator"
            if role == "Orchestrator (thought)":
                phase = next((p for k, p in THOUGHT_PHASE if text.startswith(k)), "orchestrator_thought")
            elif role.startswith("Orchestrator (->"):
                phase = "instruction"
            elif role == "Orchestrator (termination condition)":
                phase = "termination"
            else:
                phase = "unknown"
        elif role == "ComputerTerminal":
            kind, aid, phase = "tool", "tool:computer_terminal", "code_execution"
        else:
            kind, aid, phase = "llm", slug(role), "agent_response"
        if phase in ("plan", "replan"):
            sources = proto(broadcast) if phase == "replan" else []
        elif phase == "progress_ledger":
            sources = proto(broadcast)
        elif phase in ("next_speaker", "stalled", "request_satisfied", "replan_limit", "termination",
                       "instruction", "orchestrator_thought"):
            sources = proto([last_ledger], "structured_field") if last_ledger else []
        elif kind == "tool":
            prev = [s for s in broadcast if s["kind"] == "llm"]
            sources = proto(prev[-1:], "excerpt")
        else:   # agent reads the broadcast thread; it was selected by the latest progress ledger
            sources = merge_sources(proto(broadcast), proto([last_ledger], "control") if last_ledger else [])
        st = make_step(order, kind, aid, role, text, phase=phase, sources=sources,
                       tool_calls=[tool_call("execute_code", None, text)] if kind == "tool" else None)
        steps.append(st)
        if phase in ("plan", "replan"):
            broadcast = [st]
        elif phase == "progress_ledger":
            last_ledger = st
        elif phase == "instruction" or phase == "agent_response" or kind == "tool":
            broadcast.append(st)
    return steps, idx2order


# ---------------------------------------------------------------- CaptainAgent (Algorithm-Generated)
def captain_steps(hist):
    steps, idx2order = [], {}
    for i, m in enumerate(hist):
        name, text = m.get("name") or m.get("role"), m.get("content") or ""
        order = len(steps)
        idx2order[i] = order
        if name == "Computer_terminal":
            st = make_step(order, "tool", "tool:computer_terminal", name, text, phase="code_execution",
                           sources=proto(steps[-1:], "excerpt"), tool_calls=[tool_call("execute_code", None, text)])
        else:
            first = i == 0 and text.startswith("You are given: (1) a task and advises from your manager")
            st = make_step(order, "llm", slug(name), name, text,
                           phase="task_assignment" if first else "expert_turn",
                           sources=[] if first else proto(steps))
        steps.append(st)
    return steps, idx2order


def final_answer(steps):
    for s in reversed(steps):
        m = _FA.findall(s["output"] or "")
        if m:
            return m[-1].strip(), [s["step_id"]]
    return None, []


def agentrx_index(raw):
    p = os.path.join(raw, "microsoft__AgentRx")
    data = {r["trajectory_id"]: r for r in map(json.loads, open(os.path.join(p, "magentic_dataset.jsonl")))}
    labs = {r["trajectory_id"]: r for r in map(json.loads, open(os.path.join(p, "magentic_one.jsonl")))}
    return data, labs


def convert(raw):
    recs, rep = [], {"agentrx_attached": 0, "agentrx_text_mismatch": [], "agentrx_trajectory_without_label": 0, "skipped": 0}
    arx_data, arx_lab = agentrx_index(raw)
    for cfg, fw in (("Hand-Crafted", "magentic_one"), ("Algorithm-Generated", "captainagent")):
        df = pd.read_parquet(os.path.join(raw, "Kevin355__Who_and_When", cfg, "train", "0000.parquet"))
        for _, r in df.iterrows():
            hist = [dict(m) for m in r["history"]]
            qid_native = r["question_ID"]
            bench = bench_of(qid_native)
            steps, idx2order = magentic_steps(hist) if fw == "magentic_one" else captain_steps(hist)
            ms = int(r["mistake_step"]) if str(r["mistake_step"]).strip().lstrip("-").isdigit() else None
            ext = {"dataset": "Who&When", "taxonomy": "who_when_mistake", "subset": cfg,
                   "mistake_agent": r["mistake_agent"], "mistake_step": r["mistake_step"],
                   "mistake_step_index_base": "index into the dataset's history list"
                   + (" (history[0] = human task message, not a step)" if fw == "magentic_one" else ""),
                   "mistake_step_id": (f"s{idx2order[ms]}" if ms in idx2order else None),
                   "mistake_reason": r["mistake_reason"]}
            if fw == "magentic_one":
                ext["mistake_type"] = None if pd.isna(r["mistake_type"]) else r["mistake_type"]
                ext["is_corrected"] = bool(r["is_corrected"])
                gold = r["groundtruth"]
                # AgentRx magentic = same trajectories; attach only if text-identical position by position
                a = arx_data.get(qid_native)
                if a is not None:
                    subs = [ss for s in a["steps"] for ss in s["substeps"]]
                    same = len(subs) == len(hist) and all(ss["content"] == m["content"] for ss, m in zip(subs, hist))
                    lab = arx_lab.get(qid_native)
                    if same and lab:
                        def sid(k):   # AgentRx step index k (1-based over history) -> our step id
                            o = idx2order.get(int(k) - 1) if str(k).isdigit() else None
                            return f"s{o}" if o is not None else None
                        ext["agentrx"] = {
                            "taxonomy": "AgentRx failure categories", "failure_summary": lab.get("failure_summary"),
                            "failures": [dict(f, step_id=sid(f.get("step_number"))) for f in lab.get("failures") or []],
                            "root_cause_failure_id": lab.get("root_cause_failure_id"),
                            "root_cause_reason": lab.get("root_cause_reason"),
                            "step_number_base": "AgentRx steps[].index (1-based over the same history list)"}
                        rep["agentrx_attached"] += 1
                    elif not same:
                        rep["agentrx_text_mismatch"].append(qid_native)
                    else:
                        rep["agentrx_trajectory_without_label"] += 1
            else:
                gold = r["ground_truth"]
            msid = ext["mistake_step_id"]
            ext["mistake_agent_id"] = next((s["agent_id"] for s in steps if s["step_id"] == msid), None)   # converted naming
            if ms is not None and msid is None:
                ext["mistake_step_unmapped"] = f"mistake_step {ms} outside the history ({len(hist)} entries)"
            fa, fsrc = final_answer(steps)
            if not fsrc and steps:
                fsrc = [steps[-1]["step_id"]]
            rec = make_record(
                dataset=DATASET, benchmark=bench, framework=fw,
                model="gpt-4o" if fw == "magentic_one" else None,
                qid=question_id(bench, qid_native), query=r["question"], steps=steps,
                final_answer=fa, final_source_step_ids=fsrc,
                labels={"gold": gold, "is_correct": False, "external": ext,
                        "is_correct_source": "dataset: every trajectory is a failed run with a mistake annotation"
                        + (" (is_correct field = False)" if fw == "captainagent" else "")},
                provenance={"source_record_id": f"{cfg}/{qid_native}",
                            "model_source": ("log lines name gpt-4o-2024-08-06 (resolved 2024-05-13)"
                                             if fw == "magentic_one" else "not stored in the dataset")})
            recs.append(rec)
    rep["agentrx_magentic_total"] = len(arx_data)
    return recs, rep


if __name__ == "__main__":
    cli(convert, DATASET)
