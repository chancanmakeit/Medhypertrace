"""TraceElephant (TraceElephant/TraceElephant, data.zip) -> mas-traj/1.

220 traces with full LLM-call records (input messages, output, tool calls): CaptainAgent (GAIA 73,
AssistantBench 12), Magentic-One (GAIA 74, AssistantBench 17), SWE-agent (SWE-bench 44; single agent).

Steps: one `llm` step per step record. One `tool` step per tool message (role "tool" with tool_call_id(s))
that answers a call of that record (found in a later record's input; SWE-agent, CaptainAgent's
seek_agent_help); Magentic-One tool results are not logged as tool messages (WebSurfer's page text enters
later inputs as an agent message), so its tool calls stay on the llm step only.
agent_id = the agent that MADE the call, derived from the prompt (Magentic-One ledger / plan / final-answer
prompts are Orchestrator calls even where TraceElephant's `agent_name` names the agent being steered; that
dataset attribution is kept in labels.external.step_agent_names).
Sources: text_match on the per-step input (common.infer_text_sources); tool steps read their issuing call
(protocol, structured_field); a CaptainAgent expert turn also gets a `control` source from the speaker-
selection call that picked it.
"""
import ast
import json
import os
import re
import zipfile
from collections import Counter

from .common import (cli, infer_text_sources, make_record, make_step, merge_sources, msg_text, proto,
                     question_id, slug, src, tool_call)

DATASET = "traceelephant"
FW = {"captain": "captainagent", "magentic": "magentic_one", "swe-agent": "swe_agent"}
BENCH = {"assistantbench": "AssistantBench", "assistant-bench": "AssistantBench", "gaia": "GAIA",
         "swe-bench": "SWE-bench"}
MAG_SIG = [("Recall we are working on the following request", "orchestrator", "progress_ledger"),
           ("Below I will present you a request", "orchestrator", "facts"),
           ("As a reminder, we are working to solve", "orchestrator", "update_facts"),
           ("Fantastic. To address this request", "orchestrator", "plan"),
           ("Please briefly explain what went wrong", "orchestrator", "replan"),
           ("We are working on the following task", "orchestrator", "final_answer"),
           ("We are visiting the webpage", "websurfer", "summarize_page")]
FILE_TOOLS = {"open_path", "find_on_page_ctrl_f", "find_next", "page_up", "page_down"}
ROLE_NAME = {"orchestrator": "MagenticOneOrchestrator", "websurfer": "WebSurfer", "filesurfer": "FileSurfer",
             "coder": "Coder", "computerterminal": "ComputerTerminal"}


def lit(x):
    if isinstance(x, str) and x[:1] in "[{":
        try:
            return ast.literal_eval(x)
        except Exception:
            try:
                return json.loads(x)
            except Exception:
                return x
    return x


def jarg(a):
    if isinstance(a, str):
        try:
            return json.loads(a)
        except Exception:
            return a
    return a


def clean_msg(m):
    out = {"role": m.get("role")}
    if m.get("name") is not None:
        out["name"] = m["name"]
    out["content"] = m.get("content")
    if "tool_calls" in m:
        out["tool_calls"] = lit(m["tool_calls"])
    for k in ("tool_call_id", "tool_call_ids"):
        if k in m:
            out[k] = lit(m[k])
    return out


def arg_values(a):
    a = jarg(a)
    out = []

    def rec(x):
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                rec(v)
        elif isinstance(x, list):
            for v in x:
                rec(v)
    rec(a)
    return out


def input_text(msgs):
    parts = []
    for m in msgs or []:
        parts.append(msg_text(m.get("content")))
        for tc in (m.get("tool_calls") if isinstance(m.get("tool_calls"), list) else []) or []:
            if isinstance(tc, dict):
                parts += arg_values((tc.get("function") or {}).get("arguments"))
    return "\n".join(parts)


def classify(system, msgs, out_msg, te_agent):
    first = msg_text(msgs[0].get("content")) if msgs else ""
    last = msg_text(msgs[-1].get("content")).strip() if msgs else ""
    tools = {(t.get("function") or {}).get("name") for t in out_msg.get("tool_calls") or []}
    if system == "magentic":
        for pre, aid, ph in MAG_SIG:
            if last.startswith(pre):
                return aid, ph
        if tools:
            if tools <= FILE_TOOLS:
                return "filesurfer", "file_action"
            if not (tools & FILE_TOOLS):
                return "websurfer", "browser_action"
            return slug(te_agent), "tool_action"
        if first.startswith("You are a helpful AI assistant.\nSolve tasks using your coding"):
            return "coder", "coder_response"
        a = slug(te_agent)
        return ("orchestrator" if a == "magenticoneorchestrator" else a), "agent_response"
    if system == "captain":
        if first.startswith("# Your goal\nMatch roles"):
            return "captain", "role_matching"
        if first.startswith("# Your task\nYou are in a role play game"):
            return "chat_manager", "speaker_selection"
        if first.startswith("# Your task\nBriefly summarize"):
            return "captain", "chat_summary"
        if first.startswith("# Your role\nYou are a perfect manager"):
            return "captain", "captain"
        if first.lstrip().startswith("# Group chat instruction"):
            return slug(te_agent), "expert_turn"
        return slug(te_agent), "unknown"
    return "swe_agent", "agent_step"


def convert_trace(z, path):
    sub = path.split("/")[1]
    system, bench_raw = sub.split("-runs-")
    meta = json.loads(z.read(path.replace("step_records.json", "trace_metadata.json")))
    recs = json.loads(z.read(path))
    fw, bench = FW[system], BENCH[bench_raw]
    # ---- pass 1: llm steps (+ the tool messages that answer them)
    llm, n_img, n_from_logs = [], 0, 0
    for r in recs:
        msgs = [clean_msg(m) for m in r["input"].get("messages") or []]
        n_img += sum(1 for m in msgs if isinstance(m.get("content"), list)
                     for p in m["content"] if isinstance(p, dict) and p.get("type") == "image")
        ch = (r["output"].get("choices") or [{}])[0]
        om = ch.get("message") or {}
        aid, phase = classify(system, msgs, om, r["agent_name"])
        # round 61 (medical-aegis spot check, issue round 43, item A): some records keep the model's calls only in
        # tool_logs (message.tool_calls empty) -> fall back to tool_logs, same {id, function{name, arguments}} layout
        raw_calls = om.get("tool_calls") or [t for t in (r.get("tool_logs") or []) if isinstance(t, dict) and t.get("function")]
        from_logs = bool(raw_calls) and not om.get("tool_calls")
        tcs = [dict(tool_call((t.get("function") or {}).get("name"), jarg((t.get("function") or {}).get("arguments"))),
                    id=t.get("id")) for t in raw_calls]
        if from_logs:
            n_from_logs += 1
            if aid == "swe_agent" or (system == "magentic" and phase == "agent_response"):
                aid, phase = classify(system, msgs, {"tool_calls": raw_calls}, r["agent_name"])
        llm.append(dict(native=str(r["step_id"]), te_agent=r["agent_name"], msgs=msgs, out=om.get("content") or "",
                        aid=aid, phase=phase, tcs=tcs, finish=ch.get("finish_reason"), from_logs=from_logs,
                        model=(r["output"] or {}).get("model")))
    # tool messages: first occurrence of each tool_call_id(s) group in any input
    tool_msgs = {}
    for L in llm:
        for m in L["msgs"]:
            if m.get("role") != "tool":
                continue
            ids = m.get("tool_call_ids") or ([m["tool_call_id"]] if m.get("tool_call_id") else [])
            ids = tuple(ids if isinstance(ids, (list, tuple)) else [ids])
            if ids and ids not in tool_msgs:
                tool_msgs[ids] = m
    # ---- pass 2: build steps in order
    steps, native2sid, used = [], {}, set()
    for L in llm:
        order = len(steps)
        st = make_step(order, "llm", L["aid"], ROLE_NAME.get(L["aid"], L["te_agent"]) if system == "magentic"
                       else ("CaptainAgent" if L["aid"] == "captain" else
                             "GroupChatManager" if L["aid"] == "chat_manager" else
                             "SWE-agent" if system == "swe-agent" else L["te_agent"]),
                       L["out"], phase=L["phase"], input_messages=L["msgs"], sources=None,
                       tool_calls=L["tcs"], finish_reason=L["finish"])
        st["_in"] = input_text(L["msgs"])
        st["_probe"] = L["out"] if L["out"].strip() else "\n".join(v for t in L["tcs"] for v in arg_values(t["arguments"]))
        if L["phase"] == "speaker_selection":
            st["_probe"] = ""   # output is an agent name, which every group-chat prompt contains anyway
        native2sid[L["native"]] = st["step_id"]
        steps.append(st)
        call_ids = [t["id"] for t in L["tcs"] if t.get("id")]
        for ids, m in tool_msgs.items():
            if ids in used or not set(ids) & set(call_ids):
                continue
            used.add(ids)
            names = [t["name"] for t in L["tcs"] if t.get("id") in ids]
            text = msg_text(m.get("content"))
            ts = make_step(len(steps), "tool", f"tool:{slug(names[0] if names else 'tool')}", names[0] if names else "tool",
                           text, phase="tool_result",
                           sources=[src(st["step_id"], "structured_field", "protocol")],
                           tool_calls=[dict(tool_call(t["name"], t["arguments"], text), id=t.get("id"))
                                       for t in L["tcs"] if t.get("id") in ids])
            ts["_in"], ts["_probe"] = None, text
            steps.append(ts)
    stats = infer_text_sources(steps, lambda s: s["_in"], lambda s: s["_probe"], exclude_text=meta.get("task_instruction") or "")
    # control: a CaptainAgent expert turn was selected by the preceding speaker-selection call
    for i, s in enumerate(steps):
        if s["kind"] == "llm" and s["phase"] == "expert_turn":
            prev = [p for p in steps[:i] if p["kind"] == "llm"]
            if prev and prev[-1]["phase"] == "speaker_selection" and prev[-1]["output"].strip() == s["agent_role"]:
                s["sources"] = merge_sources(s["sources"], [src(prev[-1]["step_id"], "control", "protocol")])
    for s in steps:
        s.pop("_in"), s.pop("_probe")
    # final answer
    fa, fsrc = None, []
    for s in reversed(steps):
        m = re.search(r"##\s*ANSWER\s*\n(.*?)(?:\n\s*\n|\n##|$)", s["output"] or "", re.S)
        if s["kind"] == "llm" and m:
            fa, fsrc = m.group(1).strip(), [s["step_id"]]
            break
    if not fsrc and steps:
        fsrc = [steps[-1]["step_id"]]
    ms = str(meta.get("mistake_step"))
    ext = {"dataset": "TraceElephant", "taxonomy": "who_when_mistake", "mistake_agent": meta.get("mistake_agent"),
           "mistake_step": meta.get("mistake_step"), "mistake_step_id": native2sid.get(ms),
           "mistake_step_base": "TraceElephant step_records[].step_id (1-based over llm calls)",
           "mistake_reason": meta.get("mistake_reason"),
           "step_agent_names": {native2sid[L["native"]]: L["te_agent"] for L in llm}}
    msid = ext["mistake_step_id"]
    ext["mistake_agent_id"] = next((s["agent_id"] for s in steps if s["step_id"] == msid), None)   # converted naming
    ext["mistake_agent_naming_note"] = ("mistake_agent uses TraceElephant agent_name (for Magentic-One orchestrator "
                                        "calls the directed agent, for SWE-agent the tool name); mistake_agent_id is the "
                                        "converted agent_id of the labelled step")
    if meta.get("tests_status") is not None:
        ext["tests_status"] = meta["tests_status"]
    model = Counter(L["model"] for L in llm if L["model"]).most_common(1)
    rec = make_record(
        dataset=DATASET, benchmark=bench, framework=fw, model=model[0][0] if model else None,
        qid=question_id(bench, meta.get("task_id")), query=meta.get("task_instruction"), steps=steps,
        final_answer=fa, final_source_step_ids=fsrc,
        labels={"gold": meta.get("ground_truth"), "is_correct": False, "external": ext,
                "is_correct_source": "dataset: every trace is a failed run with a mistake annotation"
                                     + ("; SWE-bench tests_status has failures" if system == "swe-agent" else "")},
        provenance={"source_record_id": path.rsplit("/", 1)[0], "n_input_images": n_img,
                    "llm_steps_tool_calls_from_tool_logs": n_from_logs,
                    "images_note": "screenshots referenced in input_messages ({'type':'image','image_file':...}) live in data.zip and are not exported"})
    return rec, stats


def convert(raw):
    z = zipfile.ZipFile(os.path.join(raw, "TraceElephant__TraceElephant", "data.zip"))
    paths = sorted(n for n in z.namelist() if n.endswith("step_records.json"))
    recs, tot = [], Counter()
    for p in paths:
        r, st = convert_trace(z, p)
        recs.append(r)
        tot.update(st)
    return recs, {"traces": len(paths), "text_match": dict(tot)}


if __name__ == "__main__":
    cli(convert, DATASET)
